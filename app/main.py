"""HTTP layer. The only thing a partner's browser can reach.

Local run:
    pip install -r requirements.txt
    python -m tools.make_test_model            # if you have no workbook yet
    uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import Principal, require_token
from app.calc import ValidationError, build_engine
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("app")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="Adaptavate Biomass-to-Board Engine",
    # No interactive docs in production: the schema names every output and is
    # one more surface to reason about. Enable locally if you want them.
    docs_url="/api/docs" if settings.environment == "development" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.environment == "development" else None,
)

# Built once at import. If the workbook has changed in a way that alters the
# numbers, build_engine raises and the process refuses to start. That is
# intentional: a deploy that would serve wrong numbers should fail loudly.
engine = build_engine(settings.workbook_path, backend=settings.backend)
log.info(
    "Engine ready. backend=%s workbook=%s auth=%s",
    engine.backend_name,
    settings.workbook_path,
    "on" if settings.auth_required else "OFF (development)",
)


@app.post("/api/calculate")
async def calculate(request: Request, who: Principal = Depends(require_token)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    try:
        result = engine.calculate(payload, include_internal=who.is_internal)
    except ValidationError as exc:
        # Safe to surface: this is about the partner's own input, not the model.
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        # NEVER surface the real error. A stack trace could leak a sheet name,
        # a cell reference or a formula. Detail goes to the server log only.
        log.exception("Calculation failed for token ending %s", who.tail)
        raise HTTPException(status_code=500, detail="Calculation failed") from None

    # Log what was modelled, not what came back. Useful sales intelligence, and
    # it is what the Tier 2 database will eventually persist.
    log.info(
        "calc token=...%s internal=%s capacity=%s conversion=%s biochar=%s feedstock=%s energyType=%s",
        who.tail,
        who.is_internal,
        payload.get("plantCapacity"),
        payload.get("lineConversion"),
        payload.get("biocharRate"),
        payload.get("feedstock"),
        payload.get("energyType"),
    )
    return JSONResponse(result)


@app.get("/api/health")
async def health():
    """For Render's health check. Says nothing about the model."""
    return {"status": "ok", "backend": engine.backend_name}


@app.get("/api/config")
async def config(who: Principal = Depends(require_token)):
    """Bounds and options for the UI, so the front end has one source of truth.

    Deliberately excludes factors and multipliers: the browser gets the list of
    feedstock names, never what each one does to the maths.
    """
    from app.calc.contract import BOUNDS, CREDIT_MULTIPLIERS, FEEDSTOCK_FACTORS

    return {
        "bounds": {k: {"min": lo, "max": hi} for k, (lo, hi) in BOUNDS.items()},
        "feedstocks": sorted(FEEDSTOCK_FACTORS),
        "creditModes": sorted(CREDIT_MULTIPLIERS),
        "internal": who.is_internal,
    }


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


if settings.serve_web and WEB_DIR.is_dir():
    @app.get("/")
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
