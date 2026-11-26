"""Demo end-to-end de MediTriage (Windows / Linux / macOS, solo libreria estandar).

python demo/demo.py                                   # API local en :8000
$env:BASE_URL="http://127.0.0.1:8080"; python demo/demo.py   # API en Kubernetes via port-forward
"""

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ.get("TOKEN", "demo-token")


def call(method, path, body=None, write=False):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if write:
        headers["Idempotency-Key"] = str(uuid.uuid4())
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code} en {method} {path}: {e.read().decode('utf-8')}")
        sys.exit(1)


print("== Paso 0  health:", call("GET", "/health"))
s, p = call(
    "POST",
    "/patients",
    {
        "rut": "12.345.678-5",
        "fullName": "Paciente Demo",
        "consentGiven": True,
        "vitalSigns": {"heartRate": 85, "oxygenSaturationPercentage": 96},
    },
    write=True,
)
print("== Paso 1  paciente registrado:", s, p["id"])
s, ev = call(
    "POST",
    "/triage-evaluations",
    {
        "patientId": p["id"],
        "symptoms": ["dolor torácico"],
        "vitalSigns": {"heartRate": 120, "oxygenSaturationPercentage": 92},
    },
    write=True,
)
print("== Paso 2  sugerencia:", s, "ESI", ev["esiCategory"], "|", ev["justification"])
s, c = call("PATCH", f"/triage-evaluations/{ev['id']}", {"confirmedByNurse": True}, write=True)
print("== Paso 3  confirmada:", s, c["status"], c["confirmedByNurse"])
print("== Paso 4  tablero:", json.dumps(call("GET", "/triage-board")[1], ensure_ascii=False))
print("== Paso 4  eventos de auditoría:", len(call("GET", "/audit-logs")[1]))
