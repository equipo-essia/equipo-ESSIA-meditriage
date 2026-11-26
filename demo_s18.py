"""Demo en vivo S18 de MediTriage.

Uso:
    python demo_s18.py                       # contra http://127.0.0.1:8000
    BASE_URL=http://<ingress> python demo_s18.py   # contra staging

Ejecuta el flujo completo e imprime cada paso con su respuesta JSON.
"""

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("DEMO_TOKEN", "demo-token")


def call(method, path, body=None, idem=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if idem is not None:
        headers["Idempotency-Key"] = str(idem)
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        print(f"  !! HTTP {e.code}: {raw.decode('utf-8', errors='replace')}")
        raise


def show(step, title, status, payload):
    print(f"\n{'=' * 68}")
    print(f"PASO {step} — {title}   [HTTP {status}]")
    print("=" * 68)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    print(f"Objetivo: {BASE}")
    print("Requisito: la API debe estar corriendo (ver instrucciones del guion).")

    status, payload = call("GET", "/health")
    show(0, "Health (lo usan los probes de Kubernetes)", status, payload)

    status, patient = call(
        "POST",
        "/patients",
        {
            "rut": "12.345.678-5",
            "fullName": "Paciente Demo",
            "consentGiven": True,
            "vitalSigns": {"heartRate": 85, "oxygenSaturationPercentage": 96},
        },
        uuid.uuid4(),
    )
    show(1, "Registrar paciente (RUT validado + consentimiento + idempotencia)", status, patient)

    status, evaluation = call(
        "POST",
        "/triage-evaluations",
        {
            "patientId": patient["id"],
            "symptoms": ["dolor torácico"],
            "vitalSigns": {"heartRate": 120, "oxygenSaturationPercentage": 92},
        },
        uuid.uuid4(),
    )
    show(2, "Sugerencia ESI (rules-v0, sin LLM)", status, evaluation)

    status, confirmed = call(
        "PATCH",
        f"/triage-evaluations/{evaluation['id']}",
        {"confirmedByNurse": True},
        uuid.uuid4(),
    )
    show(3, "Enfermera confirma (humano en el loop)", status, confirmed)

    status, board = call("GET", "/triage-board")
    show("4a", "Tablero ordenado por ESI", status, board)

    status, audit = call("GET", "/audit-logs")
    show("4b", "Registro de auditoría (creación + confirmación)", status, audit)

    print(f"\n{'=' * 68}")
    print("RESUMEN PARA DECIR EN VOZ ALTA")
    print("=" * 68)
    print(f"  Paciente creado ........ {patient['id']}")
    print(f"  Categoría sugerida ..... ESI {evaluation['esiCategory']}")
    print(f"  Justificación .......... {evaluation['justification']}")
    print(f"  Estado final ........... {confirmed['status']}")
    print(f"  Confirmado por enfermera {confirmed['confirmedByNurse']}")
    print(f"  Eventos de auditoría ... {len(audit)}")
    print(f"  Tablero ................ {len(board)} evaluación(es)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"\nERROR: no se pudo conectar con {BASE}", file=sys.stderr)
        print(f"Detalle: {exc}", file=sys.stderr)
        print("\nLevántala con: uvicorn main:app --host 127.0.0.1 --port 8000", file=sys.stderr)
        raise SystemExit(1) from exc
