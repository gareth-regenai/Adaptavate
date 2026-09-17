# Following The String: Verifying A 100,000 Variable Model

Your question: how do you make sure the chain runs all the way from each output
back to its source, and can Python just follow it?

Yes. It is called dependency tracing, and it solves your other problem at the
same time. On the test model below, **99.86% of the workbook turned out to be
irrelevant.** Twelve outputs depended on thirty-three cells out of twenty-four
thousand.

---

## What "following the string" actually means

A spreadsheet is a web of cells pointing at other cells. `Outputs!B13` might read
`Calcs!B9`, which reads `Calcs!B8`, which reads three cells on the Inputs sheet.
That is the string. Excel shows you one link at a time with Trace Precedents.
Python can walk the entire web in one pass.

The process is mechanical:

1. Read every formula in the workbook and note which cells it mentions
2. That gives a map: this cell feeds that cell, twenty thousand times over
3. Start at an output, walk backwards, collect everything you touch, keep going
   until you reach cells that are not formulas
4. Whatever you collected is that output's complete dependency chain. Everything
   you did not collect is irrelevant to that output

`tools/trace_dependencies.py` in this folder does exactly that. It only reads the file.

```bash
python3 tools/trace_dependencies.py model/Adaptavate-BBE-model.xlsx --slice slice.json
```

On a 24,000 cell workbook it took **0.6 seconds**. The work scales with how many
formulas there are, not the total cell count, so a 100,000 variable model should
still be well under a minute.

---

## How does it know it has reached the end?

There is no "end marker" in a spreadsheet. Nothing labels a cell as the source.
So the rule is defined by absence:

> **A cell is the end of the string precisely because it contains no formula.
> There is nothing further to follow.**

The walk is a simple loop. Look at a cell. If it holds a formula, read which
cells that formula mentions, and repeat for each of them. If it does not hold a
formula, stop. When every branch has stopped, the trace is complete.

Worth being clear that a chain is a **tree, not a single line**. One formula can
reference six cells, each of which references more. The walk follows every branch,
which is why an output can touch nineteen cells while only being three links deep.

### The five ways a branch terminates

Run `tools/explain_trace.py` to watch it happen on a real output:

```bash
python3 tools/explain_trace.py Adaptavate-BBE-TEST-model.xlsx out_capex
```

```
Outputs!B8  = =2600000*(in_plant_capacity/5000000)*(0.6+Calculations!B2*0.4)
   Inputs!B5  (in_plant_capacity)  [INPUT] in_plant_capacity = 5000000
      -> END OF STRING: this is one of our inputs
   Calculations!B2  = =in_line_conversion/100
      Inputs!B7  (in_line_conversion)  [INPUT] in_line_conversion = 40
         -> END OF STRING: this is one of our inputs
```

**1. `[INPUT]`, the correct ending.** The branch reached one of our eight inputs.
This is what we want every branch to do.

**2. `[CONSTANT]`, a real ending, but a warning.** A number typed into a cell.
Nothing sits behind it, so the walk genuinely stops, but it means a fixed
assumption is baked into that output:

```
Outputs!B4  = =Assumptions!B3
   Assumptions!B3  [CONSTANT] = 21.75
      -> END OF STRING: a typed-in value, not a formula, nothing behind it
```

That output is frozen at 21.75 forever.

**3. `[EMPTY]`, a broken ending.** The formula points at a cell containing
nothing. This is the failure you originally asked about:

```
   Calcs!B47  [EMPTY] nothing in this cell
      -> END OF STRING: BROKEN, the chain points at nothing
```

**4. `[SEEN]`, an efficiency stop.** This cell was already traced on another
branch. Two outputs often share working, and there is no point walking the same
subtree twice. Without this, a model with heavy shared working would take
exponentially longer.

**5. `[CIRCULAR]`, a safety stop.** The chain refers back to itself. Excel allows
this in some configurations and it would otherwise loop forever:

```
Loop!B6  = =B2
   Loop!B2  = =B3+1
      Loop!B3  = =B4*2
         Loop!B4  = =B2+B1
            Loop!B2  [CIRCULAR] refers back to itself, stopping
            Loop!B1  = =in_plant_capacity*2
               Loop!B5  [INPUT] in_plant_capacity = 5000000
```

Note it stops the circular branch and still completes the other one. Tested, it
does not hang.

### The one case where "the end" is a lie

An untraceable function. `INDIRECT` builds its reference out of text while the
sheet is running, so reading the formula tells you nothing about where it points:

```
   Calcs!B9  = =INDIRECT("Calcs!B8")*1.0  [!! INDIRECT untraceable]
      -> END OF STRING: formula reads no other cell
```

Structurally this looks like a terminated branch. It is not. There is more chain
beyond it that cannot be seen by reading the file. This is why any output whose
chain contains one of these gets flagged, and has to be verified by changing
input values and watching whether the output moves, rather than by reading
structure.

### Reading the termination summary

Every trace ends with a tally:

```
   cells visited:            19
   deepest chain:            5 links
   ended at an INPUT:        9
   ended at a CONSTANT:      2
   ended at an EMPTY cell:   0
   stopped, already seen:    4
   stopped, circular:        0
```

What you want to see: a healthy count of INPUT endings, zero EMPTY, zero
CIRCULAR, and any CONSTANT endings explained by Adaptavate rather than
discovered by a partner.

---

## The problem you were worried about is not the main problem

You asked about making sure the strings run all the way to the endpoint. Fair
concern, and the tool checks it. But in practice a broken string usually
announces itself, Excel shows `#REF!` and someone notices.

**The dangerous failure is the opposite: a string that looks perfect but does not
reach one of our inputs.**

If an output secretly depends on a number typed into a cell on a hidden
assumptions sheet, then a partner moves the relevant slider, and that output does
not budge. No error. No warning. It just quietly fails to respond, and if nobody
happens to be watching that particular figure while dragging that particular
slider, it ships.

This is exactly the failure a 100,000 variable model invites, because nobody can
hold the whole thing in their head.

---

## What it found on a deliberately awful test model

I built a 24,000 cell workbook with five faults planted in it, the kind of thing
a real model accumulates over years. The tool found all five.

**1. An output depending on a hidden hard-coded number.**

```
out_capex  (Outputs!B8)
   inputs reached: 2/9  in_line_conversion, in_plant_capacity
   hard-coded values in chain: 1
      Assumptions!B2 = 0.87
```

Capex is being multiplied by 0.87 from an assumptions sheet nobody mentioned. It
might be a perfectly correct plant derate factor. But we need to know it is
there, whether it should vary by facility, and whether Adaptavate intended a
partner to be able to change it.

**2. An output that is a frozen constant.**

```
out_gypsum_pct  (Outputs!B4)
   inputs reached: 0/9  NONE
   *** DEPENDS ON NO INPUT AT ALL, this output will never change ***
      Assumptions!B3 = 21.75
```

This is the one that would have embarrassed us. Gypsum savings would have shown
21.75% no matter what a partner typed. A prospect drags the biochar slider from
5% to 30%, watches every other number move, and that one sits there. Either they
do not notice, which is worse, or they notice and stop trusting the whole tool.

**3. A genuinely broken string, which is what you asked about.**

```
out_unit_cost  (Outputs!B10)
   BROKEN: references 1 empty cell(s), e.g. Calcs!B47
```

**4. A chain that cannot be verified at all.**

```
out_npv  (Outputs!B13)
   UNTRACEABLE: chain uses INDIRECT, cannot verify statically
```

`INDIRECT` builds a cell reference out of text while the sheet runs, so reading
the formula tells you nothing about where it actually points. Any output whose
chain passes through one has to be verified by testing values, not by reading
structure. Worth knowing which ones those are.

**5. An input wired up that drives nothing.**

```
in_credit_multiplier     *** DRIVES NOTHING, wired but unused ***
```

We would be collecting the Inset/Offset/Hybrid choice from the partner, sending
it to the server, writing it into the workbook, and it would affect nothing. That
is either a wrong cell mapping on our side, or the credit mode genuinely is not
modelled and the toggle should not be on screen.

---

## Now the part you actually asked about: cutting it down

Same workbook, the slice report:

```
cells the 12 outputs depend on: 33
cells in the whole workbook:    24,058
proportion actually needed:     0.14%
cells that could be discarded:  24,025

needed cells by sheet:
   Outputs         12
   Calcs           11
   Inputs           8
   Assumptions      2

sheets NOT touched by any output:
   LegacyModel2019
   SensitivityDump
```

Two entire sheets are provably irrelevant to every number the tool displays.

**Why this matters beyond tidiness:**

- **Speed.** The calculation engine parses the whole workbook at startup. Less
  workbook, faster startup and faster recalculation. This may be the difference
  between the fast 16ms route and the 991ms fallback.
- **Security.** The less of Adaptavate's model sits on the server, the less is
  exposed if anything ever goes wrong.
- **Verification.** Signing off thirty-three cells by hand is an afternoon.
  Signing off a hundred thousand is not possible, so it would not get done.

**Important caution on actually deleting anything.** The slice tells you what the
tool needs *today*. Do not hand Adaptavate a trimmed workbook and ask them to
work from it. Two reasons: those other sheets may matter to them for other
purposes, and if they later change a formula to reference something we deleted,
the tool breaks in a way nobody expects. Ask them to confirm the unused sheets
are genuinely unused, and keep the full workbook as the master.

---

## The conversation this produces with Adaptavate

This is the real value. Instead of "please explain your model", you arrive with
a specific, short list of questions that are hard to wave away:

> Twelve outputs, thirty-three cells. Four things need explaining before we can
> sign this off:
>
> 1. `out_capex` multiplies by 0.87 from `Assumptions!B2`. What is that, and
>    should it vary by facility?
> 2. `out_gypsum_pct` returns a fixed 21.75 regardless of the biochar rate. Is
>    that intentional, or should it be calculated?
> 3. `out_unit_cost` references `Calcs!B47`, which is empty. Is a formula
>    missing?
> 4. We collect a credit mode from the partner but nothing in the model uses it.
>    Should it drive something, or should we remove the control?
>
> Also, `LegacyModel2019` and `SensitivityDump` are not referenced by any output.
> Can you confirm they are not needed?

That is a twenty minute call, not a week of archaeology.

---

## How this fits the build sequence

Insert it into the runbook between Stage 1 and Stage 2:

| Stage | What | Tool |
|---|---|---|
| 1 | Structural profile: macros, links, risky functions | `tools/inspect_workbook.py` |
| **1b** | **Dependency trace: what each output really depends on** | **`tools/trace_dependencies.py`** |
| 2 | Map their cells to our fields, by hand, using the trace to know where to look | the mapping table |
| 5 | Validation sheet, twenty-plus combinations | by hand |

Stage 1b changes Stage 2 from reading a whole workbook to reading thirty-three
cells. That is the difference between a half day and a week.

---

## What it cannot tell you

Being straight about the limits.

- **`INDIRECT` and `OFFSET` defeat it.** They build references while running.
  The tool flags any output whose chain contains one, and those need verifying by
  testing values instead.
- **It reads structure, not correctness.** It proves `out_capex` depends on plant
  capacity. It cannot tell you whether the formula is the *right* formula. That
  is what the Stage 5 validation sheet is for, and the two are complementary:
  tracing finds what is connected, validation finds what is wrong.
- **Macros are invisible to it.** If a VBA routine writes values into cells, the
  tool sees the result as a plain number, not as something calculated. The
  inspector flags whether macros exist.
- **Whole-column references are approximated.** A formula reading `B:B` is
  recorded as a range rather than a million individual cells, to keep it fast.

Given all that, the honest summary: it will find structural problems fast and
reliably, it will cut the verification job down by a factor of hundreds, and it
does not replace checking the numbers themselves.

---

## Trying it now

Both test workbooks are in this folder.

```bash
# the clean one, everything traces properly
python3 tools/trace_dependencies.py Adaptavate-BBE-TEST-model.xlsx

# build and trace the deliberately awful one, all five faults get found
python3 make_messy_workbook.py
python3 tools/trace_dependencies.py messy_model.xlsx --slice slice.json
```

It exits with code 2 when it finds problems, so it can be wired into a build
check that refuses to deploy an unverified workbook.
