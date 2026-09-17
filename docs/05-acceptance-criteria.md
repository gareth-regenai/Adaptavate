# 05, Acceptance Criteria

Definition of done. Work through this before handing back. Every item is
pass or fail, not a judgement call.

## Security, the non-negotiables

- [ ] Open the deployed tool, open browser dev tools, inspect the network tab.
      The request contains the eight inputs. The response contains only the
      output values in `docs/04`. No formulas, coefficients or intermediate
      working appear anywhere
- [ ] Inspect the sources tab. No Adaptavate coefficient, factor or formula is
      present in any client-side file
- [ ] Source maps are disabled in the production build
- [ ] The workbook is not reachable at any URL. Try to guess a few, then confirm
      it is not in any public or static directory
- [ ] The workbook is not in the git repository, and never has been in its history
- [ ] Trigger a server error deliberately. The message returned to the client is
      generic and reveals no sheet name, cell reference or stack trace
- [ ] The tool requires credentials. Accessing it without them fails

## Calculation correctness

- [ ] The 20-plus input comparison sheet described in `docs/03` is complete, and
      every tool output matches the workbook run manually
- [ ] Both extremes of every slider are included in that comparison
- [ ] All four feedstock types are included
- [ ] All three credit modes are included
- [ ] The startup validation assertion is in place: a known input set is run at
      boot and the service refuses to start if outputs do not match expected

## Input validation

- [ ] Every input outside its stated range is rejected server-side with a 400
- [ ] Negative plant capacity is rejected, not clamped silently, not calculated
- [ ] Negative gas consumption is rejected
- [ ] Non-numeric input in a numeric field is rejected
- [ ] A missing field is rejected
- [ ] An absurd magnitude, for example plant capacity of 999,999,999,999, is
      rejected or clamped with a clear message
- [ ] Validation is enforced server-side even when the client-side control
      prevents it. Test by posting directly to the API, bypassing the browser

## Output handling

- [ ] A scenario producing negative `netCarbon` renders as carbon negative, with
      the dashboard's distinct styling, and does not error or clamp to zero
- [ ] A scenario that never pays back returns null for `paybackYears` and renders
      "10+ yrs", not infinity, not a negative number, not an error
- [ ] A zero plant capacity scenario does not divide by zero anywhere
- [ ] The cumulative cash flow chart renders with 11 points, year 0 to year 10

## Interface

- [ ] All eight controls are present and functional
- [ ] All six output modules are present with the units specified in `docs/04`
- [ ] Moving any control updates the dashboard
- [ ] Slider input is debounced, dragging a slider does not fire a request per pixel
- [ ] Every input has its explanatory tooltip, text carried from the prototype
- [ ] The Partner Mode and Adaptavate Mode distinction is present
- [ ] The interface is usable on a phone. Test on a real phone, not just a
      resized desktop window. Partners will open this on a phone at the conference
- [ ] Tap targets on phone are at least 44px. The prototype's were 35px, which
      was flagged as too small
- [ ] Full keyboard operation works: tab through every control, arrow keys move
      sliders, Enter activates buttons
- [ ] No JavaScript errors in the console under any input combination

## Performance

- [ ] Input change to updated figures is under 400ms on a normal connection
- [ ] The service does not cold start. Confirm by leaving it untouched for an
      hour, then loading it, it must respond immediately
- [ ] Two simultaneous users calculating different scenarios receive correct,
      non-interleaved results

## Deployment

- [ ] A staging environment exists and is separate from live
- [ ] Pushing to the deployment branch rebuilds and redeploys automatically
- [ ] The live environment runs on an always-on instance, not a free idling one
- [ ] Credentials and the workbook are held in environment secrets, not in code

## Before the 7 October event, specifically

- [ ] A full dry run has been done on the live environment, not staging
- [ ] The dry run was done on a phone, on mobile data, not office wifi
- [ ] At least one person who did not build it has used it unaided and reached
      a sensible result
- [ ] Gareth has seen and signed off the calculation comparison sheet
