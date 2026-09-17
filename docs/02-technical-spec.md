# 02, Technical Specification

## The security requirement, first

The client brief states this as mandatory, not preferred:

> The solution must enforce strict server-side evaluation so external clients
> only receive computed output values.

Everything else in this document follows from that sentence. Adaptavate's
formulation ratios, carbon factors and pyrolysis assumptions are the company's
core IP. A partner evaluating a licence must be able to use the tool without
being able to reconstruct the model behind it.

**This means, concretely:**

- No formula, coefficient, factor or constant from Adaptavate's model appears in
  client-side code, in any form
- The browser sends inputs and receives finished numbers, nothing else
- The API response contains only the values rendered on screen, no intermediate
  working, no debug fields, no "explain" payload
- The Excel workbook itself is never served, never placed in a public directory,
  never reachable by URL
- Source maps are disabled in the production build
- Errors returned to the client are generic, a stack trace must never surface a
  cell reference, sheet name or formula

**Test for this explicitly.** Open the deployed tool, open browser dev tools, and
try to find a single Adaptavate coefficient in the network tab, the sources tab,
or memory. If you can find one, the build is not done.

## Recommended stack

The original brief names two routes and prefers the first. We are taking the
first.

**Option A, chosen: Python web wrapper around the existing model.** The Excel
workbook remains the calculation engine. Python drives it. See
`docs/03-excel-integration.md`.

**Option B, rejected: native code translation.** Rewriting every formula in
Python or JavaScript. Rejected because it is slower, introduces a translation
error risk on every formula, and removes Adaptavate's ability to change their own
model without a developer. Do not drift into this without talking to Gareth.

**Suggested components, open to your judgement:**

| Layer | Suggestion | Notes |
|---|---|---|
| Language | Python 3.11+ | Required by the Excel approach |
| Web framework | FastAPI, or Streamlit | See note below |
| Front end | Reuse the prototype's HTML/CSS/JS | Already built and tested |
| Hosting | Render | See hosting section |
| Auth | Simple shared-secret or admin-issued credentials | No public sign-up |

**On Streamlit versus FastAPI.** The original brief names Streamlit. Streamlit is
faster to stand up and handles the server-side calculation boundary for free,
but you inherit its UI conventions and the finished thing looks like a Streamlit
app. We already have a designed, tested front end in `prototype/`. If keeping
that design matters (it does, this is a partner-facing sales instrument), prefer
FastAPI serving the existing static front end, with a single calculation
endpoint. Your call, but flag it to Gareth before committing either way.

## Architecture

```
Browser (partner's device)
  |
  |  POST /api/calculate
  |  { feedstock, feedstockCost, plantCapacity, gasConsumption,
  |    lineConversion, biocharRate, carbonPrice, creditMode }
  |
  v
Server (Render)
  |
  |-- Auth check (is this an invited partner?)
  |-- Input validation (see docs/04)
  |-- Calculation service
  |     |-- loads Adaptavate workbook (held server-side, never served)
  |     |-- writes inputs to the model's input cells
  |     |-- triggers recalculation
  |     |-- reads the output cells
  |
  |  200 OK
  |  { netCarbon, gasDisplacementPct, gasDisplacementMWh, gypsumPct,
  |    gypsumTonnes, cdrTonnes, capex, opex, unitCost, paybackYears,
  |    npv, netAnnualCashFlow, cashFlowSeries[] }
  |
  v
Browser renders the dashboard
```

**Keep the calculation service behind an interface.** Do not let Excel-specific
code leak into the route handler. If the Excel approach has to change (see
`docs/03`), or if Adaptavate later wants the model ported natively, only the
implementation behind that interface should change.

## Performance

A partner moving a slider expects the numbers to move. The prototype recalculates
instantly because the maths is local. Once calculation is server-side, every
change is a round trip.

- Target: under 400ms from input change to updated figures
- Debounce slider input on the client, roughly 250ms, so dragging a slider does
  not fire fifty requests
- If opening and recalculating the workbook per request is slow, keep a warm
  pre-loaded workbook instance in memory and reuse it, guarding against
  concurrent access
- Measure this early. If the Excel round trip is inherently slow, we need to know
  in week one, not week three

## Hosting

**Render**, chosen for speed of setup and built-in automated deployment.

- **Workspace plan:** the free Hobby tier is sufficient for a single service
- **Compute:** do not use the free instance type. It idles after inactivity and
  cold starts take 30 to 60 seconds, which is unacceptable when a partner opens
  the link at a conference. Use the cheapest always-on tier, around 7 USD per
  month, or the next tier up for the event window
- **Environments:** a staging service and a live service, deploying from separate
  branches
- **Deployment:** connect the GitHub repository once. Render rebuilds and
  redeploys automatically on push. No separate CI/CD tooling is needed or
  budgeted, this comes with the platform
- **Secrets:** the workbook and any credentials go in Render's environment and
  secret file handling, never committed to the repository

## Access control

The brief requires admin-issued access, not public sign-up.

- A small set of credentials issued by Adaptavate to named partners
- No registration flow, no password reset flow, no email verification
- Keep it simple. This is a gate to stop the public and competitors wandering in,
  it is not protecting financial data
- Log which credential was used and when, so Adaptavate knows which partners
  actually engaged with the tool. This is genuinely useful sales intelligence

## Repository hygiene

- The Adaptavate workbook must never be committed to the repository, even a
  private one. Treat it as a secret
- Add a `.gitignore` entry for it on day one, before it is ever placed in the
  working directory
- If it has already been committed at any point, tell Gareth immediately, history
  will need rewriting
