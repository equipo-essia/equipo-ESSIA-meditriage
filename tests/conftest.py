import pytest

from main import STORE


@pytest.fixture(autouse=True)
def clean_store():
    # Properly reset the store without deleting the root keys
    STORE["patients"] = {}
    STORE["evaluations"] = {}
    STORE["audit"] = []
    STORE["idempotency"] = {}
    yield
    STORE["patients"] = {}
    STORE["evaluations"] = {}
    STORE["audit"] = []
    STORE["idempotency"] = {}
