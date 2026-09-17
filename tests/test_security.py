"""The brief's mandatory requirement: the model must not reach the browser.

These are the tests that matter most. If any of them fail, the build is not
shippable regardless of whether the numbers are right.
"""

import json
import re
from pathlib import Path

from tests.conftest import INTERNAL, PARTNER

ROOT = Path(__file__).resolve().parent.parent

# Coefficients and internal references from the stand-in model. Replace these
# with Adaptavate's real coefficients once their workbook is wired in.
MODEL_SECRETS = [
    "0.00065", "0.0091", "0.052", "0.45", "165000", "2600000",
    "6.4", "22", "62", "145", "38",
]
INTERNAL_REFERENCES = [
    "Calculations", "Internal", "in_feedstock", "out_npv", "int_gas_savings",
    ".xlsx", "openpyxl", "formulas",
]


def _flatten(payload) -> str:
    return json.dumps(payload)


def test_partner_response_contains_no_model_coefficients(client, valid_payload):
    res = client.post("/api/calculate", json=valid_payload, headers=PARTNER)
    body = _flatten(res.json())
    # Values legitimately appear in results (e.g. a capex of 1976000), so search
    # for the coefficients as standalone tokens rather than substrings.
    for secret in MODEL_SECRETS:
        assert not re.search(rf'"{re.escape(secret)}"', body), f"leaked {secret}"


def test_partner_response_contains_no_internal_references(client, valid_payload):
    res = client.post("/api/calculate", json=valid_payload, headers=PARTNER)
    body = res.text
    for ref in INTERNAL_REFERENCES:
        assert ref not in body, f"leaked internal reference: {ref}"


def test_partner_response_keys_are_exactly_the_contract(client, valid_payload):
    """No debug fields, no working, no extras creeping in over time."""
    from app.calc.contract import OUTPUT_RANGES

    res = client.post("/api/calculate", json=valid_payload, headers=PARTNER)
    allowed = set(OUTPUT_RANGES) | {"cashFlowSeries"}
    assert set(res.json()) == allowed


def test_internal_response_adds_only_expected_extras(client, valid_payload):
    from app.calc.contract import INTERNAL_RANGES, OUTPUT_RANGES

    res = client.post("/api/calculate", json=valid_payload, headers=INTERNAL)
    allowed = (
        set(OUTPUT_RANGES) | set(INTERNAL_RANGES)
        | {"cashFlowSeries", "feedstockCarbonFactor", "feedstockYieldFactor"}
    )
    assert set(res.json()) <= allowed


def test_server_error_reveals_nothing(client, monkeypatch, valid_payload):
    """A crash must not surface a sheet name, cell reference or stack trace."""
    from app import main

    def explode(*args, **kwargs):
        raise RuntimeError("Calculations!B8 formula =in_plant_capacity*0.00065 failed")

    monkeypatch.setattr(main.engine, "calculate", explode)
    res = client.post("/api/calculate", json=valid_payload, headers=PARTNER)
    assert res.status_code == 500
    assert res.json()["error"] == "Calculation failed"
    for leak in ("Calculations", "B8", "0.00065", "in_plant_capacity"):
        assert leak not in res.text


def test_front_end_source_contains_no_model_maths():
    """The browser bundle must not contain the formulas, in any form."""
    source = (ROOT / "web" / "index.html").read_text()
    for secret in ("0.00065", "0.0091", "0.052", "feedstockFactors",
                   "CREDIT_MULTIPLIERS", "1.15", "1.25"):
        assert secret not in source, f"model maths present in front end: {secret}"


def test_front_end_calls_the_api(client):
    """Confirms the front end is server-driven, not calculating locally."""
    source = (ROOT / "web" / "index.html").read_text()
    assert "/api/calculate" in source
    assert "fetch(" in source


def test_workbook_is_not_served(client):
    """The workbook must not be reachable over HTTP by any obvious path."""
    for path in [
        "/model/Adaptavate-BBE-TEST-model.xlsx",
        "/Adaptavate-BBE-TEST-model.xlsx",
        "/model/",
        "/app/calc/contract.py",
    ]:
        res = client.get(path)
        assert res.status_code in (403, 404), f"{path} was reachable ({res.status_code})"
