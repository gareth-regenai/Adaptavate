# 04, Input and Output Contract

Taken directly from the client brief's prescriptive variable tables. These are
not suggestions. The brief specifies the inputs, their ranges, the outputs and
their units.

## Inputs, the control panel

Eight inputs. All are required, all are sent on every calculation request.

| Key | Label | Control | Type | Range | Unit | Default |
|---|---|---|---|---|---|---|
| `feedstock` | Biomass feedstock type | Dropdown | enum | `wheat`, `miscanthus`, `hemp`, `forestry` | n/a | `wheat` |
| `feedstockCost` | Feedstock delivered cost | Slider | integer | 50 to 500, step 5 | GBP per tonne | 180 |
| `plantCapacity` | Annual plant capacity | Number field | integer | 0 or greater, step 50,000 | m² per year | 5,000,000 |
| `gasConsumption` | Current gas consumption | Number field | float | 0 or greater, step 0.1 | kWh per m² | 9.5 |
| `lineConversion` | Line conversion level | Slider | integer | 10 to 100, step 1 | percent | 40 |
| `biocharRate` | Biochar inclusion rate | Slider | integer | 5 to 30, step 1 | percent | 15 |
| `carbonPrice` | Carbon credit price | Slider | integer | 50 to 500, step 5 | GBP per tCO₂e | 120 |
| `creditMode` | Carbon credit accumulation | Segmented toggle | enum | `Inset`, `Offset`, `Hybrid` | n/a | `Offset` |

### Validation rules

**Validate server-side, always.** Client-side validation is a convenience, not a
control. Never trust the payload.

- Reject any value outside the stated range with a 400 and a generic message
- Reject non-numeric values for numeric fields
- **Negative values must be rejected.** This was a real bug found in the
  prototype: negative plant capacity and gas consumption produced nonsense
  outputs throughout the dashboard. The prototype now clamps these at zero on
  input. The server must reject them outright
- Clamp or reject absurd magnitudes. A plant capacity of 999,999,999,999 is not a
  real facility and produces meaningless figures
- An empty or missing field is a 400, not a silent default

### Confirm with Adaptavate

The `creditMode` toggle needs its commercial meaning confirmed before build. The
prototype applies a simple multiplier to carbon revenue (Offset full value, Inset
reduced, Hybrid between). That was invented for the demo. Adaptavate must tell us
what these three modes actually mean financially in their model.

## Outputs, the results dashboard

Six output modules from the brief, plus the financial series the dashboard needs
to draw its charts.

| Key | Module | Type | Unit | Notes |
|---|---|---|---|---|
| `gasDisplacementPct` | Energy Security | float | percent | Share of plant gas demand displaced |
| `gasDisplacementMWh` | Energy Security | float | MWh per year | Absolute gas displacement |
| `gypsumPct` | Resource Security | float | percent | Share of virgin gypsum displaced |
| `gypsumTonnes` | Resource Security | float | tonnes per year | Absolute gypsum saved |
| `netCarbon` | Carbon Impact | float | kg CO₂e per m² | May be negative, this is the headline "carbon negative" moment |
| `cdrTonnes` | Carbon Removal | float | tonnes CO₂ per year | Quantified removal potential |
| `capex` | Commercial Case | float | GBP | Total conversion capital cost |
| `opex` | Commercial Case | float | GBP per year | Annual running cost |
| `unitCost` | Financial Return | float | GBP per m² | Running cost per unit of converted output |
| `paybackYears` | Financial Return | float or null | years | Null when the scenario never pays back |
| `npv` | Financial Return | float | GBP | 10 year, discounted |
| `netAnnualCashFlow` | Financial Return | float | GBP per year | After running costs |
| `cashFlowSeries` | Chart data | array of float | GBP | 11 values, year 0 through year 10, cumulative |

### Output handling rules

- **`netCarbon` can legitimately be negative.** Negative means carbon negative,
  which is the product's headline claim. The dashboard styles this state
  differently. Do not clamp it at zero
- **`paybackYears` must handle the never-pays-back case.** When annual cash flow
  is zero or negative, return null. The dashboard renders "10+ yrs". Do not
  return infinity, a negative number, or a divide-by-zero error
- **Do not round in the API.** Return full precision, let the front end format.
  The front end currently formats to 1 decimal place for carbon, 2 for unit cost,
  whole numbers with thousand separators for everything else

### Fixed model assumptions, confirm with Adaptavate

The prototype displays these in the control panel as stated assumptions. All four
were invented for the demo and need Adaptavate's real values, or confirmation
that these are acceptable.

| Assumption | Prototype value | Status |
|---|---|---|
| Appraisal period | 10 years | Confirm |
| Discount rate | 8 percent | Confirm |
| Reference gas price | GBP 38 per MWh | Confirm, and decide whether it should be a user input |
| Traditional board carbon benchmark | 6.4 kg CO₂e per m² | **Must be sourced and cited**, this is a comparative marketing claim |

The benchmark figure in particular is a public comparative claim against
competitors' products. It needs a defensible published source, not an internal
estimate.
