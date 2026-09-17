# Contributing

## Before you push

```bash
ruff check app tools tests
pytest -q
```

CI runs both, plus the workbook inspection and dependency trace, plus a Docker
build and health check. All of it must pass.

## Rules that are not negotiable

**No arithmetic in `web/`.** Every figure comes from the server. `pytest
tests/test_security.py` fails the build if a coefficient appears in the front
end. If you need a new calculated value, add it to the workbook and to
`app/calc/contract.py`, not to JavaScript.

**Never commit the workbook.** `model/*.xlsx` is gitignored except the
stand-in. Adaptavate's model is their IP. If it lands in history, say so
immediately.

**Bounds are enforced server-side.** Adding a UI control is not adding
validation. Put the bound in `app/calc/contract.py` and add a test.

**Update `SELF_TEST_EXPECTED` deliberately, never to make a red test go green.**
That check exists to catch the workbook changing underneath us. If it fails,
find out why before touching it.

## Adding an output

1. Add the named range to the workbook (or ask Adaptavate to)
2. Add it to `OUTPUT_RANGES` in `app/calc/contract.py`, or `INTERNAL_RANGES` if
   it would reveal a model coefficient
3. Render it in `web/index.html`
4. Extend `test_partner_response_keys_are_exactly_the_contract`

## Deciding public vs internal

Ask: could a partner derive a model coefficient from this, combined with the
inputs they already control? If yes, it is internal. Feedstock tonnage is the
worked example: a partner knows capacity and biochar rate, so tonnage would give
them the conversion factor.
