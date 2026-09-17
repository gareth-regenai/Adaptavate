# Adaptavate Biomass-to-Board Engine

A partner-facing web tool. A prospective Adaptavate licensee enters their own
plasterboard plant's figures and sees the technical, carbon and financial case
for converting a production line to GypBlack.

**Client:** Adaptavate · **Delivered by:** RegenAI · **Deadline:** 7 October 2026

---

## Quick start

```bash
git clone <this repo> && cd adaptavate-bbe
pip install -r requirements-dev.txt

python tools/make_test_model.py        # builds the stand-in workbook
cp .env.example .env                   # then edit it

uvicorn app.main:app --reload
```

Open <http://localhost:8000>. With no tokens set it runs in open development
mode and logs a warning saying so.

Or, if you would rather not install Python locally:

```bash
docker compose up
```

Run the tests:

```bash
pytest -q                              # 71 tests
pytest tests/test_security.py -v       # the ones that must never fail
```

---

## The one constraint that shapes everything

The client brief states it as mandatory, not preferred:

> The solution must enforce strict server-side evaluation so external clients
> only receive computed output values.

Adaptavate's formulation and pyrolysis model is the company's core IP. A partner
must be able to use this tool without being able to reconstruct the model behind
it.

**What that means in this codebase:**

- All arithmetic happens in `app/calc/`. There is none in `web/index.html`, and
  `tests/test_security.py` fails the build if any appears.
- The browser posts nine values to `/api/calculate` and receives twelve
  finished numbers. Nothing else. (`energyType` is the ninth, added after the
  brief's original eight; see `docs/04-io-contract.md`.)
- Feedstock type is sent as the word `"wheat"`. The browser never learns that
  wheat means a carbon factor of 1.00; that lookup is server-side in
  `app/calc/contract.py`.
- The workbook is mounted read-only at run time and never copied into a Docker
  image, so it cannot leak through a pushed image or a registry cache.
- Errors return a flat `"Calculation failed"`. The detail goes to the server log,
  because a stack trace can name a sheet or a cell.

**Adaptavate Mode is a real server-side boundary, not a UI toggle.** An internal
token receives four extra internal figures and the feedstock factors; a partner
token does not, so there is nothing extra in a partner's payload to inspect.

---

## Architecture

```
Browser  ──POST /api/calculate──▶  FastAPI  ──▶  CalculationEngine
  ▲          { 8 inputs }             │              │
  │                                   │              ├─ validate, reject rubbish
  └──────── { 12 outputs } ───────────┘              ├─ translate name → factors
                                                     └─ Backend
                                                          ├─ formulas (16ms)
                                                          └─ libreoffice (991ms)
                                                               │
                                                     Adaptavate's workbook
                                                     (never leaves the server)
```

Open `docs/architecture-animation.html` in a browser and press Play for a
ninety-second visual walkthrough of one round trip.

### Layout

| Path | What it is |
|---|---|
| `app/main.py` | HTTP layer: routes, auth, error handling |
| `app/config.py` | Settings, all from environment variables |
| `app/auth.py` | Bearer tokens, partner vs internal |
| `app/calc/contract.py` | **Named ranges, factors, bounds. Usually the only file to edit when the real workbook arrives.** |
| `app/calc/engine.py` | Validation, output shaping, startup self-test |
| `app/calc/backends/` | The two calculation backends behind one interface |
| `web/index.html` | The front end. Draws numbers, never produces them |
| `tools/` | Workbook inspection, dependency tracing, test-model generator |
| `tests/` | 71 tests, including the security suite |
| `model/` | Where Adaptavate's workbook goes. Gitignored |
| `docs/` | Build brief, spec, runbook, and the explainers |

---

## Which backend, and why it matters

Measured on the stand-in workbook, both producing identical numbers:

| | Per calculation |
|---|---|
| `formulas` (pure Python) | **16ms** |
| `libreoffice` (real spreadsheet engine) | **991ms** |

A partner dragging a slider expects the figures to move as they drag. At 16ms
that is instant; at 991ms every nudge lags visibly, which on a conference stand
reads as broken. So the pure-Python route is strongly preferred.

Whether it is usable depends entirely on Adaptavate's workbook. Run
`tools/inspect_workbook.py` against their file and it will tell you, in about
two minutes, whether macros, external links or volatile functions rule it out.

Switching is one environment variable: `CALC_BACKEND=libreoffice`.

---

## When Adaptavate's workbook arrives

This is the critical path. Follow `docs/WORKBOOK-INTAKE-RUNBOOK.md` from Stage 0.
In summary:

```bash
# 1. Structural profile. Macros? External links? Risky functions?
python tools/inspect_workbook.py model/Adaptavate-BBE-model.xlsx

# 2. Does every output actually trace back to one of our inputs?
python tools/trace_dependencies.py model/Adaptavate-BBE-model.xlsx --slice slice.json

# 3. Inspect one output's chain in detail
python tools/explain_trace.py model/Adaptavate-BBE-model.xlsx out_npv
```

Then update `app/calc/contract.py` with their named ranges and their real
expected values for `SELF_TEST_EXPECTED`, and build the twenty-combination
validation sheet described in the runbook. That sheet is the Tier 1 sign-off
deliverable.

**Named ranges, not cell coordinates.** `docs/FOLLOWING-THE-STRING.md`
demonstrates why: one inserted row and a coordinate-based build writes plant
capacity into the feedstock cost cell, producing a confidently wrong number with
no error at all. `tests/test_selftest.py` proves named ranges survive that edit.

---

## Safety nets built in

**Startup self-test.** Every boot runs one known input set through the workbook
and compares against `SELF_TEST_EXPECTED`. Mismatch means the process refuses to
start. A deploy that would serve wrong numbers fails in front of a developer
rather than quietly in front of a partner. Better down for an hour than
confidently wrong for a week.

**Server-side validation.** Every bound in `contract.py` is enforced on the
server, not just in the UI. Negative plant capacity is rejected with a 400; this
was a real bug found in the prototype, where it produced negative capex and
nonsense throughout the dashboard.

**Security tests in CI.** `tests/test_security.py` searches real HTTP responses
for model coefficients, checks the front-end source contains no formulas,
confirms errors reveal nothing, and confirms the workbook is not reachable by
URL. CI runs it twice, once in the suite and once on its own, so a failure is
unmistakable.

---

## Deployment

Render, via the checked-in `render.yaml` blueprint. Two services, staging and
production, from separate branches, `frankfurt` region, auto-deploy on push.
No separate CI/CD tooling is needed; that comes with the platform.

Two things to get right:

- **Do not use Render's free instance type.** It idles after inactivity and cold
  starts take 30 to 60 seconds, which is unacceptable when a partner opens the
  link at a conference. `starter` is about 7 USD a month.
- **The workbook goes in as a Render Secret File**, not in the repo and not in
  the image. `WORKBOOK_PATH` points at `/etc/secrets/`.

Set `ACCESS_TOKENS` and `INTERNAL_TOKENS` as dashboard secrets. They are marked
`sync: false` in the blueprint so they are never committed.

---

## Status, honestly

**Working and tested:** the API, both backends, validation, the self-test, the
security boundary, the front end wired to the server, the inspection and tracing
tools, 71 passing tests.

**Written but not yet run:** the Docker build and the Render deploy. Docker was
unavailable in the environment this was assembled in, so the `Dockerfile`,
`docker-compose.yml` and `render.yaml` are structurally validated but unproven.
First task for whoever picks this up: `docker compose up` and confirm
`/api/health` answers.

**Blocked on Adaptavate:** the real workbook, the source for the 6.4 kg CO₂e/m²
benchmark, the certified carbon-removal factor, the commercial meaning of
Inset/Offset/Hybrid, and confirmation of the four fixed assumptions. See
`docs/06-blockers.md`. Everything currently runs on a stand-in model with
invented formulas.
