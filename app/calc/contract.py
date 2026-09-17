"""Single source of truth for what the tool reads, writes and returns.

Everything that knows about Adaptavate's workbook layout lives here. When their
model arrives, this is usually the only file that needs editing.

Named ranges, never cell coordinates. See docs/FOLLOWING-THE-STRING.md for the
demonstration of why: one inserted row and a coordinate-based build writes plant
capacity into the feedstock cost cell, with no error.
"""

from __future__ import annotations

# Form field -> named range in the workbook's Inputs sheet.
INPUT_RANGES: dict[str, str] = {
    "feedstockCarbonFactor": "in_feedstock_carbon",
    "feedstockYieldFactor": "in_feedstock_yield",
    "feedstockCost": "in_feedstock_cost",
    "plantCapacity": "in_plant_capacity",
    "gasConsumption": "in_gas_consumption",
    "lineConversion": "in_line_conversion",
    "biocharRate": "in_biochar_rate",
    "carbonPrice": "in_carbon_price",
    "creditMultiplier": "in_credit_multiplier",
}

# API response key -> named range in the workbook's Outputs sheet.
# These twelve are the ONLY cells ever read. The Calcs sheet is never touched.
OUTPUT_RANGES: dict[str, str] = {
    "gasDisplacementPct": "out_gas_pct",
    "gasDisplacementMWh": "out_gas_mwh",
    "gypsumPct": "out_gypsum_pct",
    "gypsumTonnes": "out_gypsum_tonnes",
    "netCarbon": "out_net_carbon",
    "cdrTonnes": "out_cdr_tonnes",
    "capex": "out_capex",
    "opex": "out_opex",
    "unitCost": "out_unit_cost",
    "netAnnualCashFlow": "out_net_cash",
    "paybackYears": "out_payback",
    "npv": "out_npv",
}

# Internal-only outputs. Returned ONLY to an internal (Adaptavate) token, never
# to a partner. This is what makes Adaptavate Mode a real server-side boundary
# rather than a CSS toggle: a partner's browser is never sent these values, so
# there is nothing in the payload to inspect.
INTERNAL_RANGES: dict[str, str] = {
    "feedstockTonnes": "int_feedstock_tonnes",
    "convertedOutput": "int_converted_output",
    "gasSavingsValue": "int_gas_savings",
    "carbonRevenue": "int_carbon_revenue",
}

# Model parameters, deliberately server-side. The browser sends the word
# "wheat"; it never learns that wheat means a carbon factor of 1.00.
FEEDSTOCK_FACTORS: dict[str, dict[str, float]] = {
    "wheat": {"carbon": 1.00, "yield": 1.00},
    "miscanthus": {"carbon": 1.15, "yield": 0.95},
    "hemp": {"carbon": 1.25, "yield": 0.90},
    "forestry": {"carbon": 0.90, "yield": 1.05},
}

# Inset: credits retained against own footprint. Offset: sold at market.
# Hybrid: a split. CONFIRM THE REAL COMMERCIAL MEANING WITH ADAPTAVATE, these
# multipliers were invented for the stand-in model.
CREDIT_MULTIPLIERS: dict[str, float] = {
    "Offset": 1.00,
    "Hybrid": 0.80,
    "Inset": 0.60,
}

# Slider and field bounds, enforced server-side regardless of the UI.
# Adaptavate must confirm these against the model's real validity envelope,
# see the Limits tab of the workbook locator.
BOUNDS: dict[str, tuple[float, float]] = {
    "feedstockCost": (50, 500),
    "plantCapacity": (0, 500_000_000),
    "gasConsumption": (0, 1_000),
    "lineConversion": (10, 100),
    "biocharRate": (5, 30),
    "carbonPrice": (50, 500),
}

APPRAISAL_YEARS = 10

# Known-good result for the default inputs, asserted at startup. Replace with
# Adaptavate's real figures once their workbook is wired in, so the service
# refuses to boot if their model changes underneath us.
SELF_TEST_INPUT = {
    "feedstock": "wheat",
    "feedstockCost": 180,
    "plantCapacity": 5_000_000,
    "gasConsumption": 9.5,
    "lineConversion": 40,
    "biocharRate": 15,
    "carbonPrice": 120,
    "creditMode": "Offset",
}
SELF_TEST_EXPECTED = {
    "gasDisplacementMWh": 8_550.0,
    "gypsumTonnes": 15_600.0,
    "cdrTonnes": 2_730.0,
    "capex": 1_976_000.0,
    "opex": 200_100.0,
    "netAnnualCashFlow": 452_400.0,
}
