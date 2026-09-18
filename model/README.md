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

## Uploading to Render's Secret Files

Two gotchas worth knowing about if this ever looks like it's not working:

- **"Workbook not found" even though it's uploaded.** Render's Secret Files
  are a specific section on the service (Environment -> Secret Files), not a
  general environment variable. If the file isn't there, `WORKBOOK_PATH`
  points at nothing. (A Docker-based service's non-root user needing group
  `1000` to read `/etc/secrets/*` is a separate issue documented by Render;
  we haven't needed to touch `Dockerfile` for it, but it's worth knowing if
  a real permissions error ever shows up here instead of "not found".)
- **Binary corruption.** Render's Secret Files dashboard field is a text
  paste box. Pasting a raw `.xlsx` (a zip file) into it silently corrupts the
  bytes - the symptom is `zipfile.BadZipFile: Bad magic number for central
  directory` at startup, even though the file is found and readable. The
  fix: base64-encode the workbook locally and paste *that* text in instead:

  ```bash
  base64 -i Adaptavate-BBE-model.xlsx | pbcopy   # macOS, copies to clipboard
  base64 -w0 Adaptavate-BBE-model.xlsx           # Linux, prints to stdout
  ```

  `app/calc/engine.py`'s `_materialize_workbook` detects this automatically at
  startup (checks for the zip magic bytes; if absent, tries a base64 decode)
  and decodes it back to a real `.xlsx` before loading. `WORKBOOK_PATH` and
  the secret file's name stay exactly as documented above either way.
