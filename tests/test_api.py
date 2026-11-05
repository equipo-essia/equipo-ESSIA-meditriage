import logging
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from main import STORE, app

client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer token-de-prueba"}
RUT_OK = "12345678-5"


# --- helpers ---------------------------------------------------------------
def _headers():
    """Auth + una Idempotency-Key nueva en cada llamada."""
    return {**AUTH_HEADER, "Idempotency-Key": str(uuid.uuid4())}


def _slug(res):
    return res.json()["type"].rsplit("/", 1)[-1]


def _assert_problem(res, status, slug):
    """Todo error debe ser RFC 7807 con trace_id."""
    assert res.status_code == status
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["status"] == status
    assert body["trace_id"]
    assert _slug(res) == slug


def _create_patient(rut=RUT_OK, name="Ana Perez"):
    res = client.post(
        "/patients", json={"rut": rut, "fullName": name, "consentGiven": True}, headers=_headers()
    )
    assert res.status_code == 201
    return res.json()["id"]


def _create_evaluation(patient_id, symptoms=None, vitals=None):
    res = client.post(
        "/triage-evaluations",
        json={"patientId": patient_id, "symptoms": symptoms or [], "vitalSigns": vitals or {}},
        headers=_headers(),
    )
    assert res.status_code == 202
    return res.json()


# --- operación -------------------------------------------------------------
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_require_auth():
    assert client.get("/health").status_code == 200


def test_root_returns_service_info():
    body = client.get("/").json()
    assert body["service"] == "meditriage-api"
    assert body["version"] == "1.0.0"


def test_unknown_route_returns_problem_404():
    _assert_problem(client.get("/no-existe"), 404, "http-error")


def test_wrong_method_returns_problem_405():
    _assert_problem(client.delete("/health"), 405, "http-error")


# --- autenticación ---------------------------------------------------------
def test_audit_logs_unauthorized():
    response = client.get("/audit-logs")
    assert response.status_code == 401


def test_unauthorized_is_problem_with_www_authenticate():
    res = client.get("/triage-board")
    _assert_problem(res, 401, "unauthorized")
    assert res.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("value", ["Token abc", "Bearer", "abc"])
def test_malformed_authorization_header_rejected(value):
    res = client.get("/triage-board", headers={"Authorization": value})
    assert res.status_code == 401


def test_post_patients_without_auth_is_401():
    res = client.post(
        "/patients",
        json={"rut": RUT_OK, "fullName": "Ana", "consentGiven": True},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 401


def test_auth_can_be_disabled_by_env(monkeypatch):
    monkeypatch.setattr("main.AUTH_ENABLED", False)
    res = client.get("/triage-board")
    assert res.status_code == 200
    assert res.json() == []


# --- POST /patients --------------------------------------------------------
def test_post_patients_201():
    response = client.post(
        "/patients",
        json={"rut": RUT_OK, "fullName": "Ana Perez", "consentGiven": True},
        headers=_headers(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("pt-")
    assert body["consentGiven"] is True
    assert body["consentTimestamp"]
    assert len(STORE["patients"]) == 1


def test_post_patients_sin_consentimiento():
    response = client.post(
        "/patients",
        json={"rut": RUT_OK, "fullName": "Ana Perez", "consentGiven": False},
        headers=_headers(),
    )
    _assert_problem(response, 422, "consent-required")
    assert STORE["patients"] == {}


def test_post_patients_rut_invalido():
    response = client.post(
        "/patients",
        json={"rut": "RUT-INVALIDO", "fullName": "Ana Perez", "consentGiven": True},
        headers=_headers(),
    )
    _assert_problem(response, 422, "invalid-rut")


def test_post_patients_rut_con_dv_incorrecto():
    response = client.post(
        "/patients",
        json={"rut": "12345678-K", "fullName": "Ana Perez", "consentGiven": True},
        headers=_headers(),
    )
    _assert_problem(response, 422, "invalid-rut")


def test_post_patients_missing_field_is_400():
    response = client.post(
        "/patients", json={"rut": RUT_OK, "consentGiven": True}, headers=_headers()
    )
    _assert_problem(response, 400, "validation-error")


def test_post_patients_requires_idempotency_key():
    response = client.post(
        "/patients",
        json={"rut": RUT_OK, "fullName": "Ana", "consentGiven": True},
        headers=AUTH_HEADER,
    )
    _assert_problem(response, 400, "validation-error")


def test_post_patients_invalid_idempotency_key_is_400():
    response = client.post(
        "/patients",
        json={"rut": RUT_OK, "fullName": "Ana", "consentGiven": True},
        headers={**AUTH_HEADER, "Idempotency-Key": "no-es-uuid"},
    )
    _assert_problem(response, 400, "validation-error")


def test_post_patients_idempotency_replay():
    payload = {"rut": RUT_OK, "fullName": "Ana Perez", "consentGiven": True}
    headers = {**AUTH_HEADER, "Idempotency-Key": str(uuid.uuid4())}

    res1 = client.post("/patients", json=payload, headers=headers)
    assert res1.status_code == 201

    res2 = client.post("/patients", json=payload, headers=headers)
    assert res2.status_code == 201
    assert res1.json() == res2.json()
    assert len(STORE["patients"]) == 1  # no duplica el paciente


def test_post_patients_idempotency_conflict():
    key = {**AUTH_HEADER, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/patients", json={"rut": RUT_OK, "fullName": "Ana", "consentGiven": True}, headers=key
    )
    res = client.post(
        "/patients",
        json={"rut": RUT_OK, "fullName": "Otra Persona", "consentGiven": True},
        headers=key,
    )
    _assert_problem(res, 409, "idempotency-conflict")


def test_rut_is_masked_in_logs(caplog):
    caplog.set_level(logging.INFO, logger="meditriage")
    _create_patient()
    assert "12345678" not in caplog.text
    assert "********5" in caplog.text


# --- POST /triage-evaluations ---------------------------------------------
def test_post_triage_evaluations():
    patient_id = _create_patient(name="Juan")
    response = client.post(
        "/triage-evaluations",
        json={
            "patientId": patient_id,
            "symptoms": ["Dolor de pecho"],
            "vitalSigns": {"heartRate": 80},
        },
        headers=_headers(),
    )
    assert response.status_code == 202
    body = response.json()
    assert body["patientId"] == patient_id
    assert 1 <= body["esiCategory"] <= 5
    assert body["status"] == "ai_suggested"
    assert body["confirmedByNurse"] is False
    assert "ESI" in body["justification"]  # explicabilidad
    assert len(STORE["audit"]) == 1  # cada decisión IA queda auditada


def test_post_triage_unknown_patient():
    res = client.post(
        "/triage-evaluations",
        json={"patientId": "pt-inexistente", "symptoms": [], "vitalSigns": {}},
        headers=_headers(),
    )
    _assert_problem(res, 400, "unknown-patient")
    assert STORE["audit"] == []


def test_post_triage_requires_vital_signs():
    patient_id = _create_patient()
    res = client.post(
        "/triage-evaluations", json={"patientId": patient_id, "symptoms": []}, headers=_headers()
    )
    _assert_problem(res, 400, "validation-error")


def test_post_triage_idempotency_replay():
    patient_id = _create_patient()
    headers = _headers()
    body = {"patientId": patient_id, "symptoms": ["tos"], "vitalSigns": {"heartRate": 80}}

    res1 = client.post("/triage-evaluations", json=body, headers=headers)
    res2 = client.post("/triage-evaluations", json=body, headers=headers)

    assert res1.status_code == res2.status_code == 202
    assert res1.json() == res2.json()
    assert len(STORE["evaluations"]) == 1  # el reintento no duplica
    assert len(STORE["audit"]) == 1


# --- PATCH /triage-evaluations/{id} ---------------------------------------
def test_patch_triage_evaluations():
    response = client.patch(
        "/triage-evaluations/tr-12345",
        json={"confirmedByNurse": True},
        headers=_headers(),
    )
    _assert_problem(response, 404, "evaluation-not-found")


def test_patch_confirm_by_nurse():
    ev = _create_evaluation(_create_patient(), ["dolor torácico"])
    res = client.patch(
        f"/triage-evaluations/{ev['id']}", json={"confirmedByNurse": True}, headers=_headers()
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "confirmed"
    assert body["confirmedByNurse"] is True
    assert body["esiCategory"] == ev["esiCategory"]  # confirmar no cambia la categoría


def test_patch_manual_fallback_overrides_category():
    ev = _create_evaluation(_create_patient(), [], {})  # la IA sugiere ESI 5
    res = client.patch(
        f"/triage-evaluations/{ev['id']}", json={"manualEsiCategory": 2}, headers=_headers()
    )
    assert res.status_code == 200
    body = res.json()
    assert body["esiCategory"] == 2
    assert body["status"] == "manual_fallback"
    assert body["confirmedByNurse"] is True


def test_patch_manual_category_out_of_range_is_400():
    ev = _create_evaluation(_create_patient())
    res = client.patch(
        f"/triage-evaluations/{ev['id']}", json={"manualEsiCategory": 6}, headers=_headers()
    )
    _assert_problem(res, 400, "validation-error")


@pytest.mark.parametrize("body", [{}, {"confirmedByNurse": False}])
def test_patch_without_changes_is_400(body):
    ev = _create_evaluation(_create_patient())
    res = client.patch(f"/triage-evaluations/{ev['id']}", json=body, headers=_headers())
    _assert_problem(res, 400, "validation-error")


def test_patch_idempotency_replay_does_not_duplicate_audit():
    ev = _create_evaluation(_create_patient())
    headers = _headers()
    url = f"/triage-evaluations/{ev['id']}"

    res1 = client.patch(url, json={"confirmedByNurse": True}, headers=headers)
    res2 = client.patch(url, json={"confirmedByNurse": True}, headers=headers)

    assert res1.status_code == res2.status_code == 200
    assert res1.json() == res2.json()
    assert len(STORE["audit"]) == 2  # creación + una sola confirmación


def test_patch_idempotency_conflict():
    ev = _create_evaluation(_create_patient())
    headers = _headers()
    url = f"/triage-evaluations/{ev['id']}"
    client.patch(url, json={"confirmedByNurse": True}, headers=headers)
    res = client.patch(url, json={"manualEsiCategory": 3}, headers=headers)
    _assert_problem(res, 409, "idempotency-conflict")


# --- GET /triage-board -----------------------------------------------------
def test_triage_board_empty():
    res = client.get("/triage-board", headers=AUTH_HEADER)
    assert res.status_code == 200
    assert res.json() == []


def test_triage_board_ordering():
    patient_id = _create_patient()
    _create_evaluation(patient_id, ["dolor de dedo"], {"heartRate": 80})  # ESI 4
    _create_evaluation(patient_id, [], {"oxygenSaturationPercentage": 85})  # ESI 1
    _create_evaluation(patient_id, ["dolor torácico"], {})  # ESI 2

    res = client.get("/triage-board", headers=AUTH_HEADER)
    assert res.status_code == 200
    assert [e["esiCategory"] for e in res.json()] == [1, 2, 4]  # ESI 1 primero


# --- GET /audit-logs -------------------------------------------------------
def test_audit_log_records_each_decision():
    ev = _create_evaluation(_create_patient(), ["dolor torácico"])
    client.patch(
        f"/triage-evaluations/{ev['id']}", json={"confirmedByNurse": True}, headers=_headers()
    )

    res = client.get("/audit-logs", headers=AUTH_HEADER)
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) == 2
    assert all(entry["evaluationId"] == ev["id"] for entry in logs)
    assert "ESI" in logs[0]["justification"]
    assert "confirmada" in logs[1]["justification"]


def test_audit_log_is_append_only():
    ev = _create_evaluation(_create_patient())
    first_entry = client.get("/audit-logs", headers=AUTH_HEADER).json()[0]

    client.patch(
        f"/triage-evaluations/{ev['id']}", json={"manualEsiCategory": 1}, headers=_headers()
    )
    logs = client.get("/audit-logs", headers=AUTH_HEADER).json()

    assert len(logs) == 2
    assert logs[0] == first_entry  # la entrada original no se modifica


def test_audit_logs_date_filter_includes_today():
    _create_evaluation(_create_patient())
    today = datetime.now(timezone.utc).date().isoformat()
    res = client.get("/audit-logs", params={"from": today, "to": today}, headers=AUTH_HEADER)
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_audit_logs_date_filter_excludes_other_dates():
    _create_evaluation(_create_patient())
    future = client.get("/audit-logs", params={"from": "2999-01-01"}, headers=AUTH_HEADER)
    past = client.get("/audit-logs", params={"to": "2000-01-01"}, headers=AUTH_HEADER)
    assert future.json() == []
    assert past.json() == []


def test_audit_logs_invalid_range_is_400():
    res = client.get(
        "/audit-logs", params={"from": "2026-12-31", "to": "2026-01-01"}, headers=AUTH_HEADER
    )
    _assert_problem(res, 400, "validation-error")


def test_audit_logs_invalid_date_format_is_400():
    res = client.get("/audit-logs", params={"from": "hola"}, headers=AUTH_HEADER)
    _assert_problem(res, 400, "validation-error")
