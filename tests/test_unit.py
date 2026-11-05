import pytest

from main import classify_esi, compute_dv, is_valid_rut, mask_rut, normalize_rut


# --- RUT -------------------------------------------------------------------
def test_rut_normalization():
    assert normalize_rut(" 12.345.678-5 ") == "123456785"


def test_rut_normalization_uppercases_k():
    assert normalize_rut("12.000.008-k") == "12000008K"


@pytest.mark.parametrize(
    "body, dv",
    [
        ("12345678", "5"),
        ("12000002", "0"),  # resto 11 -> "0"
        ("12000008", "K"),  # resto 10 -> "K"
    ],
)
def test_compute_dv(body, dv):
    assert compute_dv(body) == dv


@pytest.mark.parametrize("rut", ["12345678-5", "12.000.002-0", "12000008-K", "12000008-k"])
def test_rut_validation_valid(rut):
    assert is_valid_rut(rut) is True


@pytest.mark.parametrize(
    "rut",
    [
        "12345678-K",  # dígito verificador incorrecto
        "5",  # demasiado corto
        "",  # vacío
        "RUT-INVALIDO",  # no numérico
        "1-9",  # cuerpo de largo fuera de rango (7 a 8 dígitos)
        "123456789012-3",  # cuerpo demasiado largo
    ],
)
def test_rut_validation_invalid(rut):
    assert is_valid_rut(rut) is False


def test_rut_masking_keeps_only_last_char():
    assert mask_rut("12345678-5") == "********5"


def test_rut_masking_empty():
    assert mask_rut("") == "***"


# --- ESI: una prueba por regla --------------------------------------------
@pytest.mark.parametrize(
    "symptoms, vitals",
    [
        ([], {"oxygenSaturationPercentage": 85}),
        ([], {"heartRate": 160}),
        ([], {"heartRate": 30}),
        ([], {"bloodPressureSystolic": 70}),
        (["paro cardiorrespiratorio"], {}),
        ([], {"oxygenSaturationPercentage": 85, "heartRate": 160}),
    ],
)
def test_classify_esi_level_1(symptoms, vitals):
    assert classify_esi(symptoms, vitals)[0] == 1


@pytest.mark.parametrize(
    "symptoms, vitals",
    [
        ([], {"oxygenSaturationPercentage": 92}),
        ([], {"heartRate": 140}),
        ([], {"heartRate": 45}),
        ([], {"bloodPressureSystolic": 85}),
        ([], {"temperatureCelsius": 40.5}),
        ([], {"temperatureCelsius": 34}),
        (["dolor torácico"], {"heartRate": 80}),
        (["DIFICULTAD PARA RESPIRAR"], {}),  # no distingue mayúsculas
    ],
)
def test_classify_esi_level_2(symptoms, vitals):
    assert classify_esi(symptoms, vitals)[0] == 2


@pytest.mark.parametrize(
    "symptoms, vitals",
    [
        ([], {"heartRate": 110}),
        ([], {"temperatureCelsius": 38.5}),
        ([], {"bloodPressureSystolic": 190}),
        (["tos", "dolor de cabeza"], {}),
        (["malestar"], {"heartRate": 120, "temperatureCelsius": 39}),
    ],
)
def test_classify_esi_level_3(symptoms, vitals):
    assert classify_esi(symptoms, vitals)[0] == 3


def test_classify_esi_level_4():
    assert classify_esi(["dolor de dedo"], {"heartRate": 80})[0] == 4


def test_classify_esi_level_5():
    assert classify_esi([], {"oxygenSaturationPercentage": 98, "heartRate": 80})[0] == 5


def test_classify_esi_ignores_missing_vitals():
    assert classify_esi(["tos"], {"heartRate": None, "temperatureCelsius": None})[0] == 4


# --- ESI: límites exactos (donde suelen estar los bugs) --------------------
@pytest.mark.parametrize(
    "vitals, expected",
    [
        ({"oxygenSaturationPercentage": 89}, 1),
        ({"oxygenSaturationPercentage": 90}, 2),
        ({"oxygenSaturationPercentage": 93}, 2),
        ({"oxygenSaturationPercentage": 94}, 5),
        ({"heartRate": 100}, 5),
        ({"heartRate": 101}, 3),
        ({"heartRate": 130}, 3),
        ({"heartRate": 131}, 2),
        ({"heartRate": 150}, 2),
        ({"heartRate": 151}, 1),
        ({"heartRate": 40}, 2),
        ({"heartRate": 39}, 1),
        ({"bloodPressureSystolic": 79}, 1),
        ({"bloodPressureSystolic": 80}, 2),
        ({"bloodPressureSystolic": 90}, 5),
        ({"bloodPressureSystolic": 180}, 3),
        ({"temperatureCelsius": 35}, 5),
        ({"temperatureCelsius": 38}, 3),
        ({"temperatureCelsius": 40}, 2),
    ],
)
def test_classify_esi_boundaries(vitals, expected):
    assert classify_esi([], vitals)[0] == expected


# --- ESI: prioridad y explicabilidad --------------------------------------
def test_classify_esi_higher_severity_wins():
    cat, _ = classify_esi(["dolor torácico"], {"oxygenSaturationPercentage": 85})
    assert cat == 1


def test_classify_esi_justification_explains_the_reason():
    cat, msg = classify_esi([], {"oxygenSaturationPercentage": 85})
    assert f"ESI {cat}" in msg
    assert "saturación" in msg
    assert "confirmación de la enfermera" in msg


def test_classify_esi_level_2_also_lists_level_3_reasons():
    _, msg = classify_esi(["dolor torácico"], {"heartRate": 120})
    assert "alto riesgo" in msg
    assert "taquicardia" in msg
