# 03, Excel Integration

This is the highest-risk part of the build. Read it before writing any code, and
validate the approach against the real workbook on day one.

## The principle: wrapping, not rewriting

We are **not** translating Adaptavate's formulas into Python. The workbook stays
the calculation engine. Python's job is to operate it automatically.

Why this matters commercially: Adaptavate can continue to edit their own model in
Excel, as they do today, and the tool picks up the change with no code
deployment. If we rewrite the formulas in code, every future model change becomes
a developer ticket. The original brief flags this concern explicitly.

Why it matters for this timeline: hand-translating formulas is slow and every
translated formula is an opportunity to introduce a silent error in a
partner-facing number.

## The flow

1. Partner submits inputs
2. Server loads the workbook (held securely, never served)
3. Server writes the eight input values into the model's designated input cells
4. Server triggers a full recalculation
5. Server reads the designated output cells
6. Server returns only those output values

## Day one validation task, do this first

Before estimating anything, open the real workbook and answer these questions.
The answers determine which implementation route is viable.

| Question | Why it matters |
|---|---|
| Does it contain VBA macros? | Most lightweight Python libraries cannot execute these |
| Does it use external data connections or links to other workbooks? | These will not resolve on a server |
| Does it use array formulas, `OFFSET`, `INDIRECT`, or volatile functions? | Common source of recalculation failures in headless tools |
| Are the input cells clearly identifiable and stable? | We need named ranges, not fragile coordinates |
| Are the output cells clearly identifiable and stable? | Same |
| How long does a full recalculation take in Excel itself? | Sets the performance floor |
| Is there one scenario per sheet, or one model recalculated? | Affects how we drive it |

**Report the answers to Gareth before proceeding.** If the workbook is heavy on
macros or external links, the approach changes and the estimate may change with
it. That conversation needs to happen in week one.

## Implementation routes, in order of preference

**Route 1: a formula-evaluating Python library.** Loads the workbook, sets input
cells, recalculates the dependency graph in Python, reads outputs. Fast, no Excel
installation required, deploys cleanly to Render. Works only if the workbook uses
standard formulas. Preferred if viable.

**Route 2: headless LibreOffice on the server.** Install LibreOffice in the
container, drive the workbook through it. Handles far more Excel features
including most macros. Heavier container, slower per calculation, more moving
parts in deployment, but far more faithful to how the workbook behaves on
Adaptavate's own machines. The fallback when Route 1 cannot handle the workbook.

**Route 3: pre-computed result grid.** If the workbook proves impossible to drive
reliably, and only then: have Adaptavate export a dense grid of pre-computed
results across the realistic input ranges, and interpolate between them
server-side. This loses precision and is a genuine compromise, so escalate before
going anywhere near it. Noted here only so the option exists if week one goes
badly.

## Non-negotiables whichever route is used

- **Ask Adaptavate for named ranges.** Do not hard-code cell coordinates like
  `Sheet1!D14`. A single inserted row in Adaptavate's workbook would then
  silently corrupt every number the tool produces, with no error. Named ranges
  survive edits. If the workbook does not have them, ask Adaptavate to add them,
  this is a five minute job for them and removes an entire class of silent
  failure
- **Validate on load.** On server start, run a known input set through the
  workbook and assert the outputs match known expected values. If Adaptavate
  swaps in an updated workbook that has moved something, the service should fail
  loudly at deploy time, not produce quietly wrong numbers for a partner
- **Never mutate and save the source workbook.** Load it, write to an in-memory
  copy, read results, discard. The file on disk stays pristine
- **Guard concurrency.** If a warm workbook instance is reused across requests,
  two partners calculating simultaneously must not interleave writes. Lock
  around the write-recalculate-read cycle, or keep a small pool of instances

## Verification against the source model, required

Before this ships, produce a comparison sheet:

- Pick at least 20 input combinations spanning the realistic range, including
  both extremes of every slider
- Run each through Adaptavate's workbook manually
- Run each through the deployed tool
- Every output must match

Any discrepancy is a blocker, not a rounding note. Hand this sheet to Gareth as
the evidence Tier 1 is complete, it is the deliverable that proves the tool
tells the truth.
