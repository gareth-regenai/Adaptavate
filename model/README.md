# model/

Adaptavate's workbook goes here, named:

    Adaptavate-BBE-model.xlsx

**This directory is gitignored.** The workbook is Adaptavate's intellectual
property. It must never be committed, never be included in a Docker image, and
never be placed anywhere the web server can serve it. It is mounted read-only at
run time.

If it has been committed at any point, tell Gareth immediately. Git history
needs rewriting and the longer that waits the worse it gets.

## First steps when the file arrives

```bash
python tools/inspect_workbook.py model/Adaptavate-BBE-model.xlsx
python tools/trace_dependencies.py model/Adaptavate-BBE-model.xlsx
```

Then follow `docs/WORKBOOK-INTAKE-RUNBOOK.md` from Stage 0.

## The stand-in

`Adaptavate-BBE-TEST-model.xlsx` is committed deliberately. It has the same
named ranges and the same shape as we expect the real workbook to have, with
invented formulas, so the application and its tests run without Adaptavate's IP
present. Rebuild it any time with:

```bash
python tools/make_test_model.py
```
