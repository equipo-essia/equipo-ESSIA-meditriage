"""MediTriage API - servicio mínimo para la entrega S07 (contenedor + Kubernetes + HPA).

Qué es esto:
  Implementación mínima del contrato api/openapi.yaml, con datos EN MEMORIA.
  Sirve para demostrar el despliegue (imagen, probes, HPA); NO es el motor
  clínico definitivo. El "motor de IA" es un conjunto de reglas simples
  (rules-v0) y su resultado siempre requiere confirmación de la enfermera.

Limitaciones conocidas (documentar en el README / ADR):
  - El estado vive en memoria de cada pod: con 2+ réplicas, cada una tiene su
    propio estado y se pierde al reiniciar. En producción irían PostgreSQL + SQS.
  - La autenticación Bearer solo verifica que el header exista (stub); no valida
    la firma del JWT.


Compatibilidad con el despliegue:
  - Objeto ASGI `app` en main.py  ->  `uvicorn main:app`
  - /health sin auth y sin dependencias externas (probes de Kubernetes)
  - No escribe en disco (el Deployment usa readOnlyRootFilesystem)
  - Configuración por variables de entorno (ConfigMap: APP_ENV, LOG_LEVEL)
"""

import json
import logging
import os
import threading
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

# --------------------------------------------------------------------------
# Configuración (12-Factor: todo por entorno)
# --------------------------------------------------------------------------
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
PORT = int(os.getenv("PORT", "8000"))
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("meditriage")


# --- LÓGICA PURA (sin FastAPI: se puede probar sola) -----------------------
def normalize_rut(rut: str) -> str:
    return rut.replace(".", "").replace("-", "").replace(" ", "").upper()


def compute_dv(body: str) -> str:
    """Dígito verificador del RUT chileno (módulo 11)."""
    total, factor = 0, 2
    for ch in reversed(body):
        total += int(ch) * factor
        factor = 2 if factor == 7 else factor + 1
    r = 11 - (total % 11)
    if r == 11:
        return "0"
    if r == 10:
        return "K"
    return str(r)


def is_valid_rut(rut: str) -> bool:
    n = normalize_rut(rut)
    if len(n) < 2:
        return False
    body, dv = n[:-1], n[-1]
    if not body.isdigit() or not (7 <= len(body) <= 8):
        return False
    return compute_dv(body) == dv


def mask_rut(rut: str) -> str:
    """Para logs: nunca se escribe el RUT completo (Ley 19.628 / DoD del equipo)."""
    n = normalize_rut(rut)
    return ("*" * (len(n) - 1) + n[-1]) if n else "***"


_CRITICAL_SYMPTOMS = ("paro cardio", "paro respiratorio", "inconsciente", "sin pulso")
_HIGH_RISK_SYMPTOMS = (
    "dolor torácico",
    "dolor toracico",
    "dificultad para respirar",
    "disnea",
    "sangrado",
    "convulsi",
    "confusión",
    "confusion",
    "déficit neurológico",
)


def classify_esi(symptoms: list, vitals: dict) -> tuple:
    """Reglas simples (rules-v0) para sugerir categoría ESI 1-5 con justificación.

    Es un PLACEHOLDER para la demo de despliegue, no criterio clínico validado.
    """
    text = " ".join(symptoms).lower()
    hr = vitals.get("heartRate")
    sys_bp = vitals.get("bloodPressureSystolic")
    temp = vitals.get("temperatureCelsius")
    spo2 = vitals.get("oxygenSaturationPercentage")

    level1, level2, level3 = [], [], []

    if spo2 is not None and spo2 < 90:
        level1.append(f"saturación de oxígeno crítica ({spo2}%)")
    if hr is not None and (hr < 40 or hr > 150):
        level1.append(f"frecuencia cardíaca extrema ({hr} lpm)")
    if sys_bp is not None and sys_bp < 80:
        level1.append(f"hipotensión severa (sistólica {sys_bp} mmHg)")
    if any(s in text for s in _CRITICAL_SYMPTOMS):
        level1.append("síntoma de compromiso vital inmediato")

    if spo2 is not None and 90 <= spo2 < 94:
        level2.append(f"desaturación ({spo2}%)")
    if hr is not None and (130 < hr <= 150 or 40 <= hr < 50):
        level2.append(f"frecuencia cardíaca alterada ({hr} lpm)")
    if sys_bp is not None and 80 <= sys_bp < 90:
        level2.append(f"hipotensión (sistólica {sys_bp} mmHg)")
    if temp is not None and (temp >= 40 or temp < 35):
        level2.append(f"temperatura de riesgo ({temp} °C)")
    if any(s in text for s in _HIGH_RISK_SYMPTOMS):
        level2.append("síntoma de alto riesgo reportado")

    if hr is not None and 100 < hr <= 130:
        level3.append(f"taquicardia ({hr} lpm)")
    if temp is not None and 38 <= temp < 40:
        level3.append(f"fiebre ({temp} °C)")
    if sys_bp is not None and sys_bp >= 180:
        level3.append(f"presión sistólica elevada ({sys_bp} mmHg)")
    if len(symptoms) >= 2:
        level3.append("múltiples síntomas reportados")

    if level1:
        category, reasons = 1, level1
    elif level2:
        category, reasons = 2, level2 + level3
    elif level3:
        category, reasons = 3, level3
    elif len(symptoms) == 1:
        category, reasons = 4, ["un único síntoma sin signos vitales de alarma"]
    else:
        category, reasons = 5, ["sin síntomas reportados ni signos vitales de alarma"]

    justification = (
        f"Categoría ESI {category} sugerida (motor rules-v0): "
        + "; ".join(reasons)
        + ". Sugerencia de apoyo: requiere confirmación de la enfermera de triage."
    )
    return category, justification


# --- FIN LÓGICA PURA -------------------------------------------------------


# --------------------------------------------------------------------------
# Modelos de entrada (coinciden con api/openapi.yaml)
# --------------------------------------------------------------------------
class VitalSigns(BaseModel):
    heartRate: Optional[int] = Field(None, ge=0, le=300)
    bloodPressureSystolic: Optional[int] = Field(None, ge=0, le=400)
    bloodPressureDiastolic: Optional[int] = Field(None, ge=0, le=300)
    temperatureCelsius: Optional[float] = Field(None, ge=25, le=45)
    oxygenSaturationPercentage: Optional[int] = Field(None, ge=0, le=100)


class PatientIn(BaseModel):
    rut: str
    fullName: str = Field(min_length=1, max_length=200)
    consentGiven: bool
    consentTimestamp: Optional[datetime] = None
    vitalSigns: Optional[VitalSigns] = None


class TriageIn(BaseModel):
    patientId: str
    symptoms: list[str] = Field(default_factory=list, max_length=50)
    vitalSigns: VitalSigns


class TriageUpdateIn(BaseModel):
    confirmedByNurse: Optional[bool] = None
    manualEsiCategory: Optional[int] = Field(None, ge=1, le=5)


# --------------------------------------------------------------------------
# Errores RFC 7807 con trace_id
# --------------------------------------------------------------------------
class Problem(Exception):
    def __init__(
        self, status: int, title: str, detail: str, slug: str, headers: Optional[dict] = None
    ):
        self.status, self.title, self.detail, self.slug = status, title, detail, slug
        self.headers = headers


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: str,
    slug: str,
    headers: Optional[dict] = None,
) -> JSONResponse:
    body = {
        "type": f"https://meditriage.example.com/errors/{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "trace_id": str(uuid4()),
    }
    return JSONResponse(
        status_code=status, content=body, media_type="application/problem+json", headers=headers
    )


app = FastAPI(
    title="MediTriage API",
    version="1.0.0",
    description="Servicio mínimo de MediTriage (S07). Estado en memoria; motor ESI por reglas.",
)


@app.exception_handler(Problem)
async def _problem_handler(request: Request, exc: Problem):
    return problem_response(request, exc.status, exc.title, exc.detail, exc.slug, exc.headers)


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    return problem_response(
        request, 400, "Datos de solicitud inválidos", detail, "validation-error"
    )


@app.exception_handler(StarletteHTTPException)
async def _http_handler(request: Request, exc: StarletteHTTPException):
    titles = {404: "Recurso no encontrado", 405: "Método no permitido"}
    return problem_response(
        request,
        exc.status_code,
        titles.get(exc.status_code, "Error HTTP"),
        str(exc.detail),
        "http-error",
    )


# --------------------------------------------------------------------------
# Autenticación (stub) e idempotencia
# --------------------------------------------------------------------------
def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
    if not AUTH_ENABLED:
        return
    parts = (authorization or "").split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise Problem(
            401,
            "No autenticado",
            "Falta o es inválido el token Bearer.",
            "unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


STORE: dict[str, Any] = {"patients": {}, "evaluations": {}, "audit": [], "idempotency": {}}
LOCK = threading.Lock()  # los endpoints sync corren en un threadpool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _fingerprint(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True)


def _idem_replay(scope: str, key: UUID, fp: str) -> Optional[JSONResponse]:
    rec = STORE["idempotency"].get((scope, str(key)))
    if rec is None:
        return None
    if rec["fp"] != fp:
        raise Problem(
            409,
            "Conflicto de idempotencia",
            "El Idempotency-Key ya se usó con datos distintos.",
            "idempotency-conflict",
        )
    return JSONResponse(status_code=rec["status"], content=rec["body"])


def _idem_save(scope: str, key: UUID, fp: str, status: int, body: Any) -> None:
    STORE["idempotency"][(scope, str(key))] = {"fp": fp, "status": status, "body": body}


def _audit(evaluation_id: str, esi: int, justification: str) -> None:
    """Registro append-only: nunca se modifica ni se borra una entrada."""
    STORE["audit"].append(
        {
            "evaluationId": evaluation_id,
            "esiCategory": esi,
            "justification": justification,
            "timestamp": _now_iso(),
        }
    )


# --------------------------------------------------------------------------
# Endpoints de operación (sin auth: los usa Kubernetes y la prueba del HPA)
# --------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health():
    """Probes de Kubernetes. Sin autenticación y sin dependencias externas."""
    return {"status": "ok"}


@app.get("/", tags=["ops"])
async def root():
    return {"service": "meditriage-api", "version": app.version, "env": APP_ENV}


# --------------------------------------------------------------------------
# Endpoints del contrato (api/openapi.yaml)
# --------------------------------------------------------------------------
@app.post("/patients", status_code=201, dependencies=[Depends(require_auth)], tags=["patients"])
def register_patient(payload: PatientIn, idempotency_key: UUID = Header(...)):
    scope, fp = "POST /patients", _fingerprint(payload)
    with LOCK:
        replay = _idem_replay(scope, idempotency_key, fp)
        if replay:
            return replay
        if not payload.consentGiven:
            raise Problem(
                422,
                "Consentimiento requerido",
                "consentGiven debe ser true para procesar datos clínicos.",
                "consent-required",
            )
        if not is_valid_rut(payload.rut):
            raise Problem(
                422,
                "RUT inválido",
                "El RUT no cumple el formato o su dígito verificador es incorrecto.",
                "invalid-rut",
            )
        patient = {
            "id": _new_id("pt"),
            "rut": payload.rut,
            "fullName": payload.fullName,
            "consentGiven": True,
            "consentTimestamp": (
                payload.consentTimestamp.isoformat() if payload.consentTimestamp else _now_iso()
            ),
            "vitalSigns": payload.vitalSigns.model_dump(mode="json")
            if payload.vitalSigns
            else None,
        }
        STORE["patients"][patient["id"]] = patient
        _idem_save(scope, idempotency_key, fp, 201, patient)
    log.info("Paciente registrado id=%s rut=%s", patient["id"], mask_rut(payload.rut))
    return JSONResponse(status_code=201, content=patient)


@app.post(
    "/triage-evaluations", status_code=202, dependencies=[Depends(require_auth)], tags=["triage"]
)
def create_triage_evaluation(payload: TriageIn, idempotency_key: UUID = Header(...)):
    scope, fp = "POST /triage-evaluations", _fingerprint(payload)
    with LOCK:
        replay = _idem_replay(scope, idempotency_key, fp)
        if replay:
            return replay
        if payload.patientId not in STORE["patients"]:
            raise Problem(
                400,
                "Paciente no registrado",
                f"No existe el paciente '{payload.patientId}'. Regístrelo primero en POST /patients.",
                "unknown-patient",
            )
        esi, justification = classify_esi(payload.symptoms, payload.vitalSigns.model_dump())
        evaluation = {
            "id": _new_id("tr"),
            "patientId": payload.patientId,
            "esiCategory": esi,
            "justification": justification,
            "confirmedByNurse": False,
            "status": "ai_suggested",
        }
        STORE["evaluations"][evaluation["id"]] = evaluation
        _audit(evaluation["id"], esi, justification)
        _idem_save(scope, idempotency_key, fp, 202, evaluation)
    log.info("Evaluación creada id=%s esi=%s", evaluation["id"], esi)
    return JSONResponse(status_code=202, content=evaluation)


@app.patch("/triage-evaluations/{id}", dependencies=[Depends(require_auth)], tags=["triage"])
def update_triage_evaluation(
    id: str,
    payload: TriageUpdateIn,  # noqa: A002
    idempotency_key: UUID = Header(...),
):
    scope, fp = f"PATCH /triage-evaluations/{id}", _fingerprint(payload)
    with LOCK:
        replay = _idem_replay(scope, idempotency_key, fp)
        if replay:
            return replay
        evaluation = STORE["evaluations"].get(id)
        if evaluation is None:
            raise Problem(
                404,
                "Evaluación no encontrada",
                f"No existe la evaluación '{id}'.",
                "evaluation-not-found",
            )
        if payload.manualEsiCategory is not None:
            evaluation["esiCategory"] = payload.manualEsiCategory
            evaluation["status"] = "manual_fallback"
            evaluation["confirmedByNurse"] = True
            note = f"Fallback manual: la enfermera asignó la categoría ESI {payload.manualEsiCategory}."
        elif payload.confirmedByNurse is True:
            evaluation["status"] = "confirmed"
            evaluation["confirmedByNurse"] = True
            note = "Sugerencia de la IA confirmada por la enfermera de triage."
        else:
            raise Problem(
                400,
                "Solicitud sin cambios",
                "Indique confirmedByNurse=true o manualEsiCategory (1-5).",
                "validation-error",
            )
        _audit(id, evaluation["esiCategory"], note)
        _idem_save(scope, idempotency_key, fp, 200, evaluation)
    return JSONResponse(status_code=200, content=evaluation)


@app.get("/triage-board", dependencies=[Depends(require_auth)], tags=["triage"])
def triage_board():
    """Pacientes priorizados: ESI 1 primero."""
    with LOCK:
        items = list(STORE["evaluations"].values())
    return sorted(items, key=lambda e: (e["esiCategory"], e["id"]))


@app.get("/audit-logs", dependencies=[Depends(require_auth)], tags=["audit"])
def audit_logs(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
):
    if date_from and date_to and date_from > date_to:
        raise Problem(
            400,
            "Rango de fechas inválido",
            "'from' no puede ser posterior a 'to'.",
            "validation-error",
        )
    with LOCK:
        entries = list(STORE["audit"])

    def in_range(e: dict) -> bool:
        d = datetime.fromisoformat(e["timestamp"]).date()
        return (not date_from or d >= date_from) and (not date_to or d <= date_to)

    return [e for e in entries if in_range(e)]


if __name__ == "__main__":  # ejecución local: python main.py
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
