"""Input validation. Enforced server-side regardless of what the UI allows."""

import pytest

from app.calc import ValidationError, prepare_inputs


def test_valid_payload_passes(valid_payload):
    result = prepare_inputs(valid_payload)
    assert result["plantCapacity"] == 5_000_000
    # The feedstock name is translated into factors server-side.
    assert result["feedstockCarbonFactor"] == 1.00
    assert result["creditMultiplier"] == 1.00


@pytest.mark.parametrize("field,value", [
    ("plantCapacity", -500_000),      # the bug found in the prototype
    ("gasConsumption", -10),
    ("plantCapacity", 999_999_999_999),
    ("lineConversion", 150),
    ("lineConversion", 5),
    ("biocharRate", 1),
    ("biocharRate", 45),
    ("feedstockCost", 10),
    ("carbonPrice", 5_000),
])
def test_out_of_range_rejected(valid_payload, field, value):
    with pytest.raises(ValidationError):
        prepare_inputs({**valid_payload, field: value})


@pytest.mark.parametrize("field", [
    "feedstockCost", "plantCapacity", "gasConsumption",
    "lineConversion", "biocharRate", "carbonPrice",
])
def test_missing_field_rejected(valid_payload, field):
    payload = {k: v for k, v in valid_payload.items() if k != field}
    with pytest.raises(ValidationError):
        prepare_inputs(payload)


@pytest.mark.parametrize("bad", ["abc", "", None, float("nan"), float("inf")])
def test_non_numeric_rejected(valid_payload, bad):
    with pytest.raises(ValidationError):
        prepare_inputs({**valid_payload, "plantCapacity": bad})


def test_unknown_feedstock_rejected(valid_payload):
    with pytest.raises(ValidationError):
        prepare_inputs({**valid_payload, "feedstock": "bananas"})


def test_unknown_credit_mode_rejected(valid_payload):
    with pytest.raises(ValidationError):
        prepare_inputs({**valid_payload, "creditMode": "Freebie"})


def test_injected_model_parameters_are_ignored(valid_payload):
    """A partner cannot smuggle a factor in through the payload."""
    result = prepare_inputs({
        **valid_payload,
        "feedstockCarbonFactor": 99,
        "in_feedstock_carbon": 99,
        "creditMultiplier": 99,
    })
    assert result["feedstockCarbonFactor"] == 1.00
    assert result["creditMultiplier"] == 1.00
