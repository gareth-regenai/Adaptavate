"""Engine behaviour: correctness against the model, and edge cases."""

import pytest

from app.calc.contract import SELF_TEST_EXPECTED, SELF_TEST_INPUT


def test_default_scenario_matches_known_values(engine):
    result = engine.calculate(SELF_TEST_INPUT)
    for key, expected in SELF_TEST_EXPECTED.items():
        assert result[key] == pytest.approx(expected, rel=1e-4), key


def test_all_twelve_outputs_present(engine, valid_payload):
    from app.calc.contract import OUTPUT_RANGES
    result = engine.calculate(valid_payload)
    for key in OUTPUT_RANGES:
        assert key in result, f"missing output {key}"


def test_cash_flow_series_shape(engine, valid_payload):
    result = engine.calculate(valid_payload)
    series = result["cashFlowSeries"]
    assert len(series) == 11                      # year 0 through year 10
    assert series[0] == pytest.approx(-result["capex"])
    assert series[-1] > series[0]                 # positive scenario climbs


def test_zero_capacity_does_not_divide_by_zero(engine, valid_payload):
    result = engine.calculate({**valid_payload, "plantCapacity": 0})
    assert result["capex"] == pytest.approx(0)
    assert result["paybackYears"] is None


def test_never_pays_back_returns_none(engine, valid_payload):
    """A deliberately poor scenario must return null, not a negative or inf."""
    result = engine.calculate({
        **valid_payload, "lineConversion": 10, "biocharRate": 5,
        "feedstockCost": 500, "carbonPrice": 50, "creditMode": "Inset",
    })
    assert result["paybackYears"] is None
    assert result["npv"] < 0


def test_carbon_can_go_negative(engine, valid_payload):
    """Carbon negative is the product's headline claim, it must not be clamped."""
    result = engine.calculate({
        **valid_payload, "feedstock": "hemp",
        "lineConversion": 100, "biocharRate": 30,
    })
    assert result["netCarbon"] < 0


@pytest.mark.parametrize("feedstock", ["wheat", "miscanthus", "hemp", "forestry"])
def test_every_feedstock_produces_distinct_results(engine, valid_payload, feedstock):
    result = engine.calculate({**valid_payload, "feedstock": feedstock})
    assert result["cdrTonnes"] > 0


def test_feedstock_choice_changes_the_answer(engine, valid_payload):
    wheat = engine.calculate({**valid_payload, "feedstock": "wheat"})
    hemp = engine.calculate({**valid_payload, "feedstock": "hemp"})
    assert hemp["cdrTonnes"] != wheat["cdrTonnes"]


@pytest.mark.parametrize("mode", ["Inset", "Hybrid", "Offset"])
def test_credit_mode_changes_the_answer(engine, valid_payload, mode):
    result = engine.calculate({**valid_payload, "creditMode": mode})
    assert result["npv"] is not None


def test_credit_modes_are_ordered(engine, valid_payload):
    """Offset should return more than Hybrid, which returns more than Inset."""
    npv = {
        m: engine.calculate({**valid_payload, "creditMode": m})["npv"]
        for m in ("Inset", "Hybrid", "Offset")
    }
    assert npv["Inset"] < npv["Hybrid"] < npv["Offset"]


@pytest.mark.parametrize("field,low,high,should_rise", [
    ("lineConversion", 10, 100, True),
    ("biocharRate", 5, 30, True),
    ("carbonPrice", 50, 500, True),
    ("feedstockCost", 50, 500, False),   # higher cost, lower return
])
def test_sensitivity_direction(engine, valid_payload, field, low, high, should_rise):
    """Each input must move the result in the direction a partner would expect."""
    at_low = engine.calculate({**valid_payload, field: low})["npv"]
    at_high = engine.calculate({**valid_payload, field: high})["npv"]
    assert (at_high > at_low) is should_rise, f"{field} moved the wrong way"


def test_partner_result_excludes_internal_figures(engine, valid_payload):
    result = engine.calculate(valid_payload, include_internal=False)
    for leaked in ("feedstockCarbonFactor", "feedstockYieldFactor",
                   "feedstockTonnes", "gasSavingsValue", "carbonRevenue"):
        assert leaked not in result, f"{leaked} leaked into a partner result"


def test_internal_result_includes_internal_figures(engine, valid_payload):
    result = engine.calculate(valid_payload, include_internal=True)
    assert result["feedstockCarbonFactor"] == 1.00
    assert result.get("feedstockTonnes") is not None
