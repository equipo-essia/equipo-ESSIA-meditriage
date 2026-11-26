"""Contract tests: las respuestas reales de la API deben cumplir api/openapi.yaml.

Valida (subconjunto de JSON Schema): type, required, enum, minimum/maximum,
properties, items y $ref. No valida `format` (ver nota en ENTREGA.md).
Requiere: pip install pyyaml
"""
import pathlib
import re
import uuid

import yaml
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
SPEC = yaml.safe_load(
    (pathlib.Path(__file__).resolve().parent.parent / "api" / "openapi.yaml").read_text(
        encoding="utf-8"
    )
)
AUTH = {"Authorization": "Bearer token-de-prueba"}
TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
}


def _h():
    return {**AUTH, "Idempotency-Key": str(uuid.uuid4())}


def _resolve(schema):
    while isinstance(schema, dict) and "$ref" in schema:
        node = SPEC
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


def validate(schema, value, where="$"):
    schema = _resolve(schema or {})
    t = schema.get("type")
    if t:
        ok = isinstance(value, TYPES[t]) and not (
            t in ("integer", "number") and isinstance(value, bool)
        )
        assert ok, f"{where}: el contrato exige {t} y llegó {type(value).__name__} ({value!r})"
    if "enum" in schema:
        assert value in schema["enum"], f"{where}: {value!r} fuera de {schema['enum']}"
    if "minimum" in schema:
        assert value >= schema["minimum"], f"{where}: {value} < minimo {schema['minimum']}"
    if "maximum" in schema:
        assert value <= schema["maximum"], f"{where}: {value} > maximo {schema['maximum']}"
    if t == "object":
        for campo in schema.get("required", []):
            assert campo in value, f"{where}: falta el campo requerido '{campo}'"
        for nombre, sub in schema.get("properties", {}).items():
            if nombre in value:
                validate(sub, value[nombre], f"{where}.{nombre}")
    if t == "array":
        for i, item in enumerate(value):
            validate(schema.get("items", {}), item, f"{where}[{i}]")


def _declared(path, method):
    return {str(k) for k in SPEC["paths"][path][method]["responses"]}


def _schema(path, method, status, media="application/json"):
    resp = SPEC["paths"][path][method]["responses"][str(status)]
    return resp.get("content", {}).get(media, {}).get("schema")


def _paciente():
    res = client.post(
        "/patients",
        json={
            "rut": "12.345.678-5",
            "fullName": "Paciente Demo",
            "consentGiven": True,
            "vitalSigns": {"heartRate": 85, "oxygenSaturationPercentage": 96},
        },
        headers=_h(),
    )
    return res


def _evaluacion(patient_id):
    return client.post(
        "/triage-evaluations",
        json={
            "patientId": patient_id,
            "symptoms": ["dolor torácico"],
            "vitalSigns": {"heartRate": 120, "oxygenSaturationPercentage": 92},
        },
        headers=_h(),
    )


def test_todas_las_rutas_del_contrato_existen_en_la_app():
    norm = lambda p: re.sub(r"\{[^}]+\}", "{}", p)  # noqa: E731
    rutas_app = {norm(r.path) for r in app.routes if hasattr(r, "methods")}
    for ruta in SPEC["paths"]:
        assert norm(ruta) in rutas_app, f"{ruta} está en el contrato y no en la API"


def test_registro_paciente_cumple_contrato():
    res = _paciente()
    assert str(res.status_code) in _declared("/patients", "post")
    validate(_schema("/patients", "post", res.status_code), res.json())


def test_evaluacion_cumple_contrato():
    pid = _paciente().json()["id"]
    res = _evaluacion(pid)
    assert str(res.status_code) in _declared("/triage-evaluations", "post")
    validate(_schema("/triage-evaluations", "post", res.status_code), res.json())


def test_confirmacion_cumple_contrato():
    pid = _paciente().json()["id"]
    ev = _evaluacion(pid).json()
    res = client.patch(
        f"/triage-evaluations/{ev['id']}", json={"confirmedByNurse": True}, headers=_h()
    )
    assert str(res.status_code) in _declared("/triage-evaluations/{id}", "patch")
    esquema = _schema("/triage-evaluations/{id}", "patch", res.status_code)
    if esquema:
        validate(esquema, res.json())


def test_tablero_cumple_contrato():
    _evaluacion(_paciente().json()["id"])
    res = client.get("/triage-board", headers=AUTH)
    assert str(res.status_code) in _declared("/triage-board", "get")
    validate(_schema("/triage-board", "get", res.status_code), res.json())
    assert len(res.json()) >= 1


def test_auditoria_cumple_contrato():
    _evaluacion(_paciente().json()["id"])
    res = client.get("/audit-logs", headers=AUTH)
    assert str(res.status_code) in _declared("/audit-logs", "get")
    validate(_schema("/audit-logs", "get", res.status_code), res.json())


def test_sin_token_devuelve_401_rfc7807_declarado():
    res = client.get("/triage-board")
    assert str(res.status_code) in _declared("/triage-board", "get")
    assert res.headers["content-type"].startswith("application/problem+json")
    validate({"$ref": "#/components/schemas/RFC7807Error"}, res.json())


def test_rut_invalido_devuelve_error_declarado_y_rfc7807():
    res = client.post(
        "/patients",
        json={"rut": "RUT-INVALIDO", "fullName": "Ana Perez", "consentGiven": True},
        headers=_h(),
    )
    assert str(res.status_code) in _declared("/patients", "post")
    assert res.headers["content-type"].startswith("application/problem+json")
    validate({"$ref": "#/components/schemas/RFC7807Error"}, res.json())
