"""HTTP behaviour: auth, validation surfacing, and the response contract."""

import pytest

from tests.conftest import INTERNAL, PARTNER


def test_health_needs_no_auth(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_calculate_requires_a_token(client, valid_payload):
    res = client.post("/api/calculate", json=valid_payload)
    assert res.status_code == 401
    assert res.json()["error"] == "Not authorised"


def test_calculate_rejects_a_wrong_token(client, valid_payload):
    res = client.post("/api/calculate", json=valid_payload,
                      headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401


def test_partner_token_gets_results(client, valid_payload):
    res = client.post("/api/calculate", json=valid_payload, headers=PARTNER)
    assert res.status_code == 200
    assert res.json()["cdrTonnes"] == pytest.approx(2730, rel=1e-4)


@pytest.mark.parametrize("field,value", [
    ("plantCapacity", -5_000_000),
    ("gasConsumption", -10),
    ("lineConversion", 150),
    ("plantCapacity", "abc"),
])
def test_bad_input_returns_400_not_500(client, valid_payload, field, value):
    res = client.post("/api/calculate", json={**valid_payload, field: value},
                      headers=PARTNER)
    assert res.status_code == 400
    assert "error" in res.json()


def test_malformed_body_returns_400(client):
    res = client.post("/api/calculate", content=b"not json", headers=PARTNER)
    assert res.status_code == 400


def test_non_object_body_returns_400(client):
    res = client.post("/api/calculate", json=[1, 2, 3], headers=PARTNER)
    assert res.status_code == 400


def test_config_exposes_bounds_but_not_factors(client):
    res = client.get("/api/config", headers=PARTNER)
    assert res.status_code == 200
    body = res.json()
    assert "bounds" in body and "feedstocks" in body
    # the browser learns the NAMES of feedstocks, never what they do to the maths
    assert "wheat" in body["feedstocks"]
    serialised = res.text
    for factor in ("1.25", "0.9", "1.15", "carbonFactor"):
        assert factor not in serialised
    assert body["internal"] is False


def test_internal_token_is_flagged_as_internal(client):
    res = client.get("/api/config", headers=INTERNAL)
    assert res.json()["internal"] is True


def test_front_end_is_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Biomass-to-Board Engine" in res.text
