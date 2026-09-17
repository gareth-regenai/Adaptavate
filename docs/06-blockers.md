# 06, Blockers

Nothing in this build starts without item 1. Everything else can be resolved in
parallel during week one, but each one is a real dependency, not a nice-to-have.

## 1. The Excel model, hard blocker

**Status: outstanding as of 15 September 2026.**

The workbook containing the live formulas behind all six output modules. Without
it there is no calculation engine and the build cannot begin. RegenAI does not
have it, and the current prototype runs entirely on stand-in maths written to
demonstrate the interface.

The 7 October timeline assumes this arrives within days. Every week of delay
moves the date by the same week. There is no slack.

Alongside the workbook, ask for:

- **Named ranges** for every input and output cell, or permission to add them.
  Hard-coded cell coordinates break silently when a row is inserted. See
  `docs/03`
- Confirmation of which sheet and cells are canonical, if the workbook contains
  more than one scenario or working area

## 2. Source for the carbon benchmark

The prototype compares GypBlack against a traditional plasterboard figure of
6.4 kg CO₂e per m². **This number was invented for the demo.**

This is a public comparative claim against competitors' products and needs a
defensible, citable published source. Adaptavate must supply the real figure and
its source before this appears in front of a partner.

## 3. Certified carbon removal factor

The tonnes of CO₂ permanently removed per tonne of biochar, and the scheme under
which that is certified (Puro.earth, European Biochar Certificate, or other).

Partners will ask which standard the credits are issued under. The tool should
not state a removal figure that cannot be tied to a certification.

## 4. Commercial meaning of Inset, Offset and Hybrid

The prototype applies an invented multiplier to carbon revenue for each mode.
Adaptavate must define what these three actually mean financially in their model,
since it materially changes the return figure a partner sees.

## 5. Confirmation of the four fixed assumptions

| Assumption | Prototype value | Needed |
|---|---|---|
| Appraisal period | 10 years | Confirm or replace |
| Discount rate | 8 percent | Confirm or replace |
| Reference gas price | GBP 38 per MWh | Confirm, and decide if it should become a user input |
| Traditional board benchmark | 6.4 kg CO₂e per m² | See item 2 |

## 6. CAPEX and OPEX basis

The prototype scales both from invented base figures. Real conversion capital
costs at different plant scales, and a real operating cost breakdown, are needed.
If Adaptavate's workbook already contains these, item 1 covers it. Confirm rather
than assume.

## 7. Access list

Who gets credentials for the conference, and who issues them. Needed before the
dry run, not on the day.

## 8. Hosting account ownership

Decide whether the Render account sits with Adaptavate or RegenAI, and who pays
for it. This affects who can access logs and redeploy after handover. Worth
settling early rather than at go-live.

---

## Not blocking, but decide before Tier 2 starts

- Where partner scenario data should live, Adaptavate's infrastructure or ours.
  This is a question for Adaptavate's engineering side and shapes the Tier 2
  database work
- Which of the six metrics matter most in a partner conversation, which
  prioritises what the Tier 3 report leads with
