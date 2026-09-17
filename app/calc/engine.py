"""The calculation engine the API talks to.

Responsibilities, in order:
  1. Validate the partner's submitted inputs and refuse anything unusable
  2. Translate form values into model inputs (feedstock name -> factors)
  3. Hand off to a backend
  4. Shape the raw outputs into what the dashboard expects

Nothing above this layer knows a spreadsheet is involved.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.calc.backends.base import Backend
from app.calc.contract import (
    APPRAISAL_YEARS,
    BOUNDS,
    ENUM_FIELDS,
    SELF_TEST_EXPECTED,
    SELF_TEST_INPUT,
)

log = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Submitted inputs are unusable. Surfaces as a 400."""


class SelfTestFailed(RuntimeError):
    """The workbook no longer produces expected results. Refuse to start."""


def prepare_inputs(payload: dict[str, Any]) -> dict[str, float]:
    """Validate every form field, then translate to model inputs.

    Never trust the browser. Sliders constrain the UI, but anyone can POST
    straight to the API. Field-by-field rules live in app/calc/contract.py
    (BOUNDS for numeric fields, ENUM_FIELDS for enum ones) so adding a new
    input is a contract.py edit, not a change here.
    """
    def number(field: str) -> float:
        if field not in payload or payload[field] is None or payload[field] == "":
            raise ValidationError(f"{field} is required")
        try:
            value = float(payload[field])
        except (TypeError, ValueError):
            raise ValidationError(f"{field} must be a number") from None
        if value != value or value in (float("inf"), float("-inf")):
            raise ValidationError(f"{field} must be a real number")
        low, high = BOUNDS[field]
        if not low <= value <= high:
            raise ValidationError(f"{field} must be between {low:g} and {high:g}")
        return value

    result: dict[str, float] = {field: number(field) for field in BOUNDS}

    for field, spec in ENUM_FIELDS.items():
        value = payload.get(field)
        if value not in spec.options:
            raise ValidationError(f"{field} is not a recognised option")
        if spec.resolve:
            result.update(spec.resolve(value))

    return result


def shape_outputs(raw: dict[str, float | None]) -> dict[str, Any]:
    """Tidy raw model output into the API response.

    Only these keys reach the browser. No intermediate working, no debug fields,
    nothing from the Calcs sheet.
    """
    out: dict[str, Any] = dict(raw)

    # The workbook returns -1 for "never pays back". Return null so the front end
    # can render "10+ yrs" rather than a nonsensical negative.
    payback = out.get("paybackYears")
    if payback is not None and payback < 0:
        out["paybackYears"] = None

    # Cumulative cash flow for the chart, derived here rather than in the sheet.
    capex = out.get("capex") or 0.0
    annual = out.get("netAnnualCashFlow") or 0.0
    series = [-capex]
    running = -capex
    for _ in range(APPRAISAL_YEARS):
        running += annual
        series.append(running)
    out["cashFlowSeries"] = series
    return out


class CalculationEngine:
    def __init__(self, backend: Backend):
        self.backend = backend

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def calculate(
        self, payload: dict[str, Any], include_internal: bool = False
    ) -> dict[str, Any]:
        model_inputs = prepare_inputs(payload)
        raw = self.backend.compute(model_inputs, include_internal=include_internal)
        result = shape_outputs(raw)
        if include_internal:
            # The feedstock factors are model parameters. They go out only on an
            # authorised internal request, never to a partner.
            result["feedstockCarbonFactor"] = model_inputs["feedstockCarbonFactor"]
            result["feedstockYieldFactor"] = model_inputs["feedstockYieldFactor"]
        return result


def build_engine(workbook_path: str | Path, backend: str = "formulas") -> CalculationEngine:
    """Create the engine and prove the workbook still behaves as expected.

    The self-test is the safety net for Adaptavate changing their model. A deploy
    that would serve wrong numbers fails here, in front of a developer, rather
    than quietly in front of a partner.
    """
    path = Path(workbook_path)
    if not path.exists():
        raise RuntimeError(
            f"Workbook not found at {path}. Place Adaptavate's file in model/ "
            "and set WORKBOOK_PATH. See model/README.md."
        )

    if backend == "formulas":
        from app.calc.backends.formulas_backend import FormulasBackend
        impl: Backend = FormulasBackend(path)
    elif backend == "libreoffice":
        from app.calc.backends.libreoffice_backend import LibreOfficeBackend
        impl = LibreOfficeBackend(path)
    else:
        raise ValueError("backend must be 'formulas' or 'libreoffice'")

    engine = CalculationEngine(impl)
    result = engine.calculate(SELF_TEST_INPUT)
    for key, expected in SELF_TEST_EXPECTED.items():
        actual = result.get(key)
        tolerance = max(1.0, abs(expected) * 0.0001)
        if actual is None or abs(actual - expected) > tolerance:
            raise SelfTestFailed(
                f"Startup self-test failed on '{key}': expected {expected}, "
                f"got {actual}. Refusing to start. The workbook has probably "
                "changed; check with Adaptavate and update SELF_TEST_EXPECTED "
                "in app/calc/contract.py if the change is intended."
            )
    log.info("Startup self-test passed on %s backend", impl.name)
    return engine
