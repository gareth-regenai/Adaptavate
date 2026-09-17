# Adaptavate Biomass-to-Board Engine
#
# Two build targets. Pick with --target:
#   docker build --target lean .   150MB, pure-Python backend only
#   docker build --target full .   ~900MB, adds LibreOffice for the fallback
#
# Use lean unless tools/inspect_workbook.py says Adaptavate's workbook needs
# LibreOffice. See docs/DOCKER-EXPLAINED.md.

# ---------- shared base ----------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CALC_BACKEND=formulas \
    WORKBOOK_PATH=/app/model/Adaptavate-BBE-model.xlsx \
    ENVIRONMENT=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies before application code, so editing app/ does not reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY web/ ./web/
COPY tools/ ./tools/

# The workbook is NOT copied in. It is mounted at run time so Adaptavate's IP
# never gets baked into a distributable image layer.
RUN mkdir -p /app/model

# Non-root. If the container is ever compromised, the attacker is not root in it.
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

# One worker. The engine holds a single workbook in memory behind a lock, so
# extra workers each load their own copy and waste memory. Scale with instances.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# ---------- full: adds a real spreadsheet engine ----------
FROM base AS full
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-calc \
    && rm -rf /var/lib/apt/lists/*
USER appuser
ENV CALC_BACKEND=libreoffice

# ---------- lean: the default, pure-Python only ----------
# Deliberately LAST: Render's blueprint spec has no field to select a build
# stage (docker-compose's `target:` doesn't exist there), and Docker builds
# whichever stage is last in the file when none is requested. `docker build
# --target <stage>` and docker-compose's `target:` still work unaffected by
# order; this ordering only matters for Render's own build, which has no such
# override.
FROM base AS lean
