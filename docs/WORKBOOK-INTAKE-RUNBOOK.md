# Workbook Intake Runbook

What to do, in order, from the moment Adaptavate's spreadsheet lands to the point
where the tool is running on their real numbers.

Work through the stages in sequence. Each ends with a decision or a message to
Gareth. Do not skip ahead, the early stages exist to stop you building on a bad
assumption for a fortnight.

---

## Stage 0, before you open it

**Handle it as a secret from the first second.**

- [ ] Save it outside any git repository. A folder like `~/adaptavate-model/`
- [ ] Confirm `model/` is in `.gitignore` before the file goes anywhere near the
      project directory
- [ ] Do not email it onward, do not put it in a shared Slack channel, do not
      drop it in a cloud folder that syncs to personal devices
- [ ] Keep the original untouched. Work on copies. If anything ever looks wrong
      you need a pristine reference to compare against

If it has already been committed to a repository at any point, tell Gareth
immediately. Git history has to be rewritten, and the longer that waits the worse
it gets.

---

## Stage 1, automated profile, about two minutes

```bash
python3 tools/inspect_workbook.py ~/adaptavate-model/Adaptavate-BBE-model.xlsx
```

This reads the file without modifying it and answers the structural questions
automatically: macros, external links, sheet inventory, every function used,
risky functions flagged individually, named ranges present or missing, and a
recommended backend.

It exits with code 2 if it finds blockers, so it can be wired into a build check
later.

**Paste the whole output back to Gareth.** It is written to be readable by a
non-developer and it is the fastest way to get a decision on anything commercial,
such as asking Adaptavate for a different version of the file.

**Stop here and escalate if it reports:**

| Finding | Why it stops the build |
|---|---|
| External data connections or links to other workbooks | Those links cannot resolve on a server. We need a self-contained copy. |
| `.xlsb` format | Not readable by our tooling. Ask for `.xlsx`. |
| No formulas at all | We have been sent values, not a model. Query it. |
| Many missing named ranges | Decide with Gareth: ask Adaptavate to add them, or map their existing names. Do not paper over it with cell coordinates. |

---

## Stage 1b, dependency trace, about one minute

```bash
python3 tools/trace_dependencies.py ~/adaptavate-model/Adaptavate-BBE-model.xlsx --slice slice.json
```

Stage 1 told you the workbook's shape. This tells you what each of our twelve
outputs **actually depends on**, by walking every formula chain backwards to its
source. See `FOLLOWING-THE-STRING.md` for the full explanation.

It answers the two questions that matter most on a very large model:

- **Is each output genuinely driven by our inputs?** An output that secretly
  depends on a hard-coded cell will never move when a partner drags the relevant
  slider. No error, just a number that silently fails to respond.
- **How much of the workbook do we actually need?** On a 24,000 cell test model,
  the twelve outputs depended on 33 cells. Everything else was irrelevant.

**Escalate to Gareth before Stage 2 if it reports:**

| Finding | What it means |
|---|---|
| An output reaching 0 inputs | That figure is a frozen constant. Confirm whether that is intended. |
| Hard-coded values in a chain | An assumption we did not know about. Ask what it is and whether it should vary by facility. |
| A broken chain, empty cell referenced | A formula is probably missing. |
| `INDIRECT` or `OFFSET` in a chain | That output cannot be verified structurally, it needs value-based testing. |
| An input that drives nothing | Either our mapping is wrong, or that control should not be on screen. |

Take the questions this produces straight to Adaptavate. It is a twenty minute
call that saves days of guessing.

---

## Stage 2, understand the model by hand, half a day

Stages 1 and 1b tell you the shape and the dependency chains. Now you need the
substance, and the trace has already told you which cells to look at, so this is
a short job rather than a whole-workbook read. Open it
in Excel or LibreOffice and work out, for each of our twelve outputs, which cell
holds it.

- [ ] Identify the eight inputs. Do they map one-to-one onto our form fields, or
      does Adaptavate's model take them differently? For example we send a
      percentage where they may expect a decimal
- [ ] Identify the twelve outputs. Confirm each is a single number, not a range,
      not a formatted string, not a chart
- [ ] Note the units for every one. A figure in thousands of pounds where we
      assumed pounds is a thousand-fold error that looks entirely plausible
- [ ] Check whether any output depends on something we do not collect. If their
      model needs a variable our form does not have, that is a scope
      conversation with Gareth before you code around it
- [ ] Time a manual recalculation in Excel. Press F9 and count. This is the floor
      on how fast the server can ever be

Write the mapping down as you go. You are filling in this table:

| Our field | Their named range (or cell) | Their unit | Conversion needed |
|---|---|---|---|
| `plantCapacity` | | | |
| `gasConsumption` | | | |
| `lineConversion` | | | |
| `biocharRate` | | | |
| `feedstockCost` | | | |
| `carbonPrice` | | | |
| feedstock type | | | |
| credit mode | | | |

Do the same for the twelve outputs. This table is the handover artefact for this
stage, and it is what you will check the numbers against later.

---

## Stage 3, named ranges

If the expected names are missing, there are two honest routes.

**Preferred: ask Adaptavate to add them.** Five minutes of their time. In Excel,
select the cell, type a name into the Name Box left of the formula bar, press
enter. Send them the list of names from `app/calc/engine.py` and ask them to apply them to
the corresponding cells.

**Acceptable: map their existing names to ours.** If they already use their own
naming, edit the `INPUT_RANGES` and `OUTPUT_RANGES` dictionaries in `app/calc/engine.py`
to point at their names. This keeps the safety property intact.

**Not acceptable: hard-coded cell coordinates.** Run
`python3 tests/test_selftest.py` to see exactly why. It demonstrates a
single inserted row causing plant capacity to be written into the feedstock cost
cell, producing a confidently wrong number with no error at all. If someone
insists on coordinates because of time pressure, escalate to Gareth rather than
absorbing the risk quietly.

---

## Stage 4, wire it up, half a day

1. Copy the workbook to `model/Adaptavate-BBE-model.xlsx`
2. Update `INPUT_RANGES` and `OUTPUT_RANGES` in `app/calc/engine.py` from your Stage 2
   table
3. Add any unit conversions in `prepare_inputs()`, where they are visible and
   testable, not scattered through the code
4. Run it:

```bash
pytest -q
```

Expect it to fail the first time. The startup self-test compares against the
stand-in model's expected values, which will not match Adaptavate's real
outputs. That failure is the system working correctly.

5. Replace `SELF_TEST_EXPECTED` in `app/calc/engine.py` with Adaptavate's real figures for
   the default input set, taken from their workbook by hand. From that point the
   self-test guards the real model.

---

## Stage 5, the validation sheet, one day, and this is the Tier 1 deliverable

This is what proves the tool tells the truth, and it is what Gareth signs off.

Build a comparison across **at least 20 input combinations**, including:

- [ ] The default scenario
- [ ] Both extremes of all four sliders, eight cases
- [ ] All four feedstock types
- [ ] All three credit modes
- [ ] One deliberately poor scenario, low conversion, low biochar, high feedstock
      cost, which should not pay back
- [ ] One strong scenario, high conversion, high biochar, which should go carbon
      negative
- [ ] Zero plant capacity, which must not crash or divide by zero

For each: run it through Adaptavate's workbook by hand, run it through the tool,
record both, compute the difference.

**Every output must match.** Not approximately. A discrepancy is a blocker, not a
rounding note. If a figure differs, the most common causes in order are: a unit
mismatch, a wrong cell mapped, or a conversion applied twice.

Deliver the sheet to Gareth with a one line summary: how many combinations, how
many matched, any outstanding discrepancies.

---

## Stage 6, performance decision

```bash
pytest -q     # prints per-calculation timing for both backends
```

| Measured time | What it means |
|---|---|
| Under 400ms | Fine. Debounce the sliders client-side and it will feel instant |
| 400ms to 1s | Usable but noticeably laggy while dragging a slider. Tell Gareth |
| Over 1s | Not acceptable for a conference demo. Escalate, we need a different approach |

For reference, on the stand-in model the pure-Python backend ran at 16ms and the
LibreOffice backend at 991ms. If Adaptavate's workbook forces the LibreOffice
route, expect to be in the third row of that table and raise it early. Options at
that point include caching common scenarios, or asking Adaptavate to simplify
the workbook for this purpose.

---

## Stage 7, the security pass

Before this goes anywhere near a partner, confirm the model cannot leak.

- [ ] Start the service, make a real request, and search the response for
      Adaptavate's actual coefficients. Not ours, theirs, taken from their
      workbook. Nothing should appear
- [ ] Confirm the workbook is not reachable by any URL
- [ ] Confirm it is not in the git repository or its history
- [ ] Trigger a deliberate server error and confirm the response says nothing
      about sheets, cells or formulas
- [ ] Confirm source maps are disabled in the production build
- [ ] Confirm the tool requires a token, and that a request without one is
      refused

`full_http_test.sh` covers the mechanical parts of this. The coefficient search
has to be done against their real numbers, so it cannot be scripted in advance.

---

## Stage 8, hand back

Send Gareth:

1. The Stage 1 inspection output
2. The Stage 2 mapping table
3. The Stage 5 validation sheet, the important one
4. The Stage 6 timing figure and which backend is in use
5. Anything in Stage 7 that is not yet closed
6. Anything Adaptavate still owes us

---

## The four things most likely to go wrong

Flagged so they are recognised rather than debugged from scratch.

**Units.** Their model may hold capacity in thousands of m², or cost in pence, or
express conversion as 0.4 rather than 40. Every one of these produces a plausible
looking wrong number. This is why Stage 2 records units explicitly.

**Percentages.** We send `40` for forty percent. If their model expects `0.4`,
every result is wrong by a factor of a hundred and the shape of the output still
looks sensible.

**Rounding inside the workbook.** If their sheet rounds for display, the tool will
show the rounded figure. Fine, as long as the validation sheet is compared
against the same rounding. Mismatched rounding wastes an afternoon.

**A stale cached value.** If a formula cell has a cached value from the last time
Adaptavate opened it, and the recalculation silently fails, you can read the old
cached number and believe it is a fresh calculation. The startup self-test is
what catches this: change an input, confirm the output actually moves.
