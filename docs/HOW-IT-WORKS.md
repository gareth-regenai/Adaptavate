# How The Python Wrapper Actually Works

Every step, in order, with the real measured results from a working build.

Everything in this folder runs. The numbers in this document were produced by
running it, not estimated.

---

## The thing to understand first

There are two completely separate ideas people muddle together:

**Idea 1, which we are NOT doing:** read Adaptavate's formulas, retype each one
as a line of Python. The spreadsheet gets thrown away. Any future change to the
model needs a developer.

**Idea 2, which we ARE doing:** leave the formulas exactly where they are, inside
the spreadsheet. Write Python that opens the file, types numbers into the input
cells, presses the equivalent of F9, and reads the answers back out. The
spreadsheet does the maths. Python is just a pair of hands.

Python never knows what the formulas say. It knows only which cells to write to
and which cells to read from.

---

## The five steps, concretely

Here is what happens between a partner moving a slider and a number changing on
their screen.

### Step 1, the browser sends eight numbers

The partner's browser sends a small message to our server. It contains only the
eight values from the form:

```json
{ "feedstock": "wheat", "feedstockCost": 180, "plantCapacity": 5000000,
  "gasConsumption": 9.5, "lineConversion": 40, "biocharRate": 15,
  "carbonPrice": 120, "creditMode": "Offset" }
```

Notice what is NOT in there. No factors, no coefficients. When the partner picks
"wheat" from the dropdown, the browser sends the word "wheat". The server is the
only thing that knows wheat means a carbon factor of 1.00. That lookup lives in
`app/calc/engine.py`, server-side, where a partner cannot reach it.

### Step 2, the server checks the numbers are sane

Before touching the spreadsheet, the server rejects rubbish. This is not
politeness, it is necessary. The sliders stop a partner entering a negative plant
capacity in the browser, but anyone can bypass the browser entirely and send
whatever they like straight to the server.

Real results from the test run:

```
"plantCapacity":-5000000  ->  HTTP 400  plantCapacity must be between 0 and 500000000
"gasConsumption":-10      ->  HTTP 400  gasConsumption must be between 0 and 1000
"lineConversion":150      ->  HTTP 400  lineConversion must be between 10 and 100
"plantCapacity":"abc"     ->  HTTP 400  plantCapacity must be a number
```

### Step 3, Python writes the numbers into the spreadsheet's input cells

This is the step people imagine is complicated. It is two lines of code per
value: find the cell, put the number in it.

The important part is **how** we find the cell. We do not say "cell B5". We say
"the cell called `in_plant_capacity`". See the section below on named ranges,
this is the single most important technical decision in the build.

### Step 4, the spreadsheet recalculates itself

Here is the gotcha that catches everyone, and it is worth seeing rather than
being told.

The standard Python library for handling Excel files, openpyxl, **cannot do
maths**. It can read and write cells perfectly well, but it has no calculation
engine. Ask it for the value of a formula cell and you get nothing at all.

Proven, from the actual test run:

```
Reading Outputs with data_only=True (asking for calculated values):
   Gas displacement pct => None
   Gas displacement MWh => None
   Net embodied carbon  => None
   Capex                => None
   NPV 10yr at 8pct     => None
```

Twelve outputs, twelve `None`s. If a developer builds on openpyxl alone and does
not test this properly, they get a tool that returns blanks or zeros and does not
obviously look broken.

So something has to actually do the sums. Two options, both built and tested:

**Option A, the `formulas` library.** Pure Python. Reads the workbook once at
startup, builds a map of which cell depends on which, then does the arithmetic
itself in Python. Fast.

**Option B, headless LibreOffice.** Install a real spreadsheet program on the
server with no screen attached, and drive it from Python. Slower, but it is a
genuine spreadsheet engine, so it copes with far more of Excel's awkward corners.

### Step 5, Python reads the answers and sends them back

Python reads the twelve output cells and sends only those twelve numbers to the
browser.

The Calculations sheet, the one standing in for Adaptavate's real model, is never
read, never sent, never mentioned. The browser receives this and nothing else:

```json
{ "gasDisplacementPct": 24.8, "gasDisplacementMWh": 8550.0,
  "gypsumPct": 21.75, "gypsumTonnes": 15600.0, "netCarbon": 5.08,
  "cdrTonnes": 2730.0, "capex": 1976000.0, "opex": 200100.0,
  "unitCost": 0.10005, "netAnnualCashFlow": 452400.0,
  "paybackYears": 4.37, "npv": 1059640.82, "cashFlowSeries": [ ... ] }
```

---

## Which option, and the measured difference

Both were built and run against the same workbook, same inputs.

| | `formulas` (pure Python) | Headless LibreOffice |
|---|---|---|
| Startup | 0.8s | 1.2s |
| **Per calculation** | **16ms** | **991ms** |
| Handles macros | No | Mostly yes |
| Handles external data links | No | Partly |
| Server weight | Light | Heavy, needs LibreOffice installed |
| Same numbers? | Yes, identical | Yes, identical |

**That 16ms against 991ms is the finding that matters.** A partner dragging a
slider expects numbers to move as they drag. At 16ms that feels instant. At
991ms every slider nudge has a visible one second lag, which on a conference
stand feels broken.

So the pure Python route is strongly preferred, and the decision rests entirely
on whether Adaptavate's real workbook is simple enough for it. That is the day
one question in `docs/03-excel-integration.md`, and it cannot be answered until
we have their file.

Both are implemented behind the same interface. Switching is one line:

```python
engine = build_engine(WORKBOOK_PATH, backend="formulas")      # preferred
engine = build_engine(WORKBOOK_PATH, backend="libreoffice")   # fallback
```

---

## Named ranges, the most important decision in the build

We must ask Adaptavate to label their input and output cells with names, rather
than us pointing at coordinates like `Inputs!B5`.

This sounds like housekeeping. It is not. Here is the failure it prevents,
demonstrated by actually doing it.

Adaptavate insert one row at the top of their Inputs sheet, perhaps to add a
version number. Entirely reasonable, and something they would never think to
mention. Everything below shuffles down one row.

**With named ranges,** which is what this build uses:

```
Named range in_plant_capacity now points at: 'Inputs'!$B$6
   that cell's label is: Annual plant capacity
   -> correct cell. Tool keeps working.
```

Running the same engine against the edited workbook, with no code change at all:

```
npv       = 1059641
capex     = 1976000
cdrTonnes = 2730
```

Identical. Nobody needs to be told the workbook changed.

**With hard-coded cell coordinates,** which is what a rushed build does:

```
HARD-CODED wrapper writes plant capacity to: Inputs!B5
   that cell's label is now: Feedstock delivered cost
   -> WRONG cell. Plant capacity is being written into feedstock cost.
```

Five million gets written into the feedstock cost cell. The spreadsheet
obediently calculates a feedstock bill of nine hundred billion pounds and the
dashboard renders it with total confidence. No error. No warning. A partner sees
a number that is wrong by a factor of thirty thousand.

Asking Adaptavate to add named ranges is about five minutes of their time and it
removes this entire category of silent failure. It is the first thing in
`docs/06-blockers.md` for a reason.

---

## The second safety net: the startup self-test

Named ranges handle cells moving. They do not handle Adaptavate deliberately
changing a coefficient, which they are entitled to do at any time.

So on every startup, before accepting a single request, the service runs one
known set of inputs through the workbook and checks the answers against known
expected values. If they do not match, the service refuses to start.

Tested by changing one coefficient in the hidden Calculations sheet:

```
REFUSED TO START: STARTUP SELF-TEST FAILED. The workbook no longer produces
the expected result for 'opex': expected 200100.0, got 230100.0. Refusing to
start. Check whether the workbook has been changed.
```

And with a named range deleted:

```
REFUSED TO START: Named range 'out_npv' is missing from the workbook.
Ask Adaptavate to add it, do not substitute a cell reference.
```

The point of this: a deploy that would serve wrong numbers fails loudly at deploy
time, in front of a developer, rather than quietly in front of a partner. It is
better for the tool to be down for an hour than to be confidently wrong for a
week.

---

## Proving the IP is actually protected

The brief's mandatory requirement is that a partner cannot extract the model. The
way to check this is not to reason about it, it is to look at what crosses the
wire.

A real HTTP response was captured and searched for every coefficient and internal
reference in the test model:

```
Searching the HTTP response for model secrets:
   clean: 0.00065      clean: 0.0091       clean: 0.052
   clean: 0.45         clean: 165000       clean: 2600000
   clean: 1.25         clean: 0.90         clean: 62
   clean: 145          clean: 22           clean: Calculations
   clean: in_feedstock clean: out_npv      clean: B8
   clean: xlsx
```

Sixteen searches, nothing leaked. Only the twelve finished numbers come back.

Two other leak paths worth knowing about, both handled in `api.py`:

- **Error messages.** A stack trace can name a sheet or a cell. Input errors
  return a specific message because they are about the partner's own typing.
  Everything else returns a flat "Calculation failed" and the detail goes to the
  server log where only we can see it.
- **The file itself.** The workbook must never sit in a folder the web server
  serves, and must never be committed to the repository. Treat it as a password.

---

## Performance and concurrency, measured

Fifteen real HTTP requests:

```
min 15ms   median 17ms   max 44ms
acceptance target under 400ms -> PASS
```

Eight partners calculating different scenarios at the same moment, checked for
crossed wires:

```
conversion  10% -> cdr    682.5t (expected    682.5) ok
conversion  20% -> cdr   1365.0t (expected   1365.0) ok
conversion  40% -> cdr   2730.0t (expected   2730.0) ok
conversion 100% -> cdr   6825.0t (expected   6825.0) ok
no interleaving of concurrent requests -> PASS
```

The concurrency point is not theoretical. There is one workbook in memory. If two
requests write their inputs into it at the same moment, one partner gets the
other partner's numbers. The fix is a lock around the write-calculate-read cycle,
which is in `app/calc/engine.py`, and the test above is what proves it works.

---

## The cross-check that matters most

The prototype's JavaScript and this spreadsheet wrapper were written separately,
from the same intended maths. They agree to the penny:

| Output | Prototype (JavaScript) | Wrapper (spreadsheet) |
|---|---|---|
| Gas displacement | 8,550 MWh | 8,550 MWh |
| Gypsum saved | 15,600 t | 15,600 t |
| CO2 removed | 2,730 t | 2,730 t |
| Capex | £1,976,000 | £1,976,000 |
| Opex | £200,100 | £200,100 |
| Net annual cash flow | £452,400 | £452,400 |
| Payback | 4.4 years | 4.37 years |
| NPV | £1,059,641 | £1,059,641 |

This is exactly the comparison exercise that has to be repeated against
Adaptavate's real workbook to sign off Tier 1, except with their formulas instead
of our stand-ins, and across at least twenty input combinations rather than one.
The method is proven. Only their file is missing.

---

## Running it yourself

```bash
pip install openpyxl formulas fastapi uvicorn

python3 tools/make_test_model.py     # builds the stand-in model
pytest -q               # runs both backends, prints the numbers
python3 test_safety.py            # validation and edge cases
python3 test_tamper.py            # proves the self-test catches changes
./full_http_test.sh               # starts the API, runs HTTP tests
```

## What this does not prove

Being straight about the limits of this exercise:

- It proves the **method** works. It does not prove Adaptavate's actual workbook
  will work with the fast route, because we have not seen it
- The stand-in model uses simple arithmetic. A real model with lookups across
  multiple sheets, array formulas or macros is a different proposition
- The 16ms figure is for a small workbook. A large one will be slower, though
  the difference between the two routes will hold
- Nothing here is Adaptavate's maths. Every formula in the test workbook is
  invented
