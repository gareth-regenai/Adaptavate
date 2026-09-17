"""Shared fixtures. The test model is built on demand so CI needs no workbook."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_MODEL = ROOT / "model" / "Adaptavate-BBE-TEST-model.xlsx"


@pytest.fixture(scope="session", autouse=True)
def _environment():
    """Configure the app for tests before anything imports app.config."""
    os.environ.setdefault("WORKBOOK_PATH", str(TEST_MODEL))
    os.environ.setdefault("CALC_BACKEND", "formulas")
    os.environ["ACCESS_TOKENS"] = "partner-token"
    os.environ["INTERNAL_TOKENS"] = "internal-token"
    os.environ["ENVIRONMENT"] = "test"
    yield


@pytest.fixture(scope="session", autouse=True)
def test_model(_environment):
    """Build the stand-in workbook if it is not already present."""
    if not TEST_MODEL.exists():
        subprocess.run(
            [sys.executable, "tools/make_test_model.py"],
            cwd=ROOT, check=True, capture_output=True,
        )
    assert TEST_MODEL.exists(), "test model was not created"
    return TEST_MODEL


@pytest.fixture(scope="session")
def engine(test_model):
    from app.calc import build_engine
    return build_engine(test_model, backend="formulas")


@pytest.fixture(scope="session")
def client(test_model):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def valid_payload():
    return {
        "feedstock": "wheat", "feedstockCost": 180, "plantCapacity": 5_000_000,
        "gasConsumption": 9.5, "lineConversion": 40, "biocharRate": 15,
        "carbonPrice": 120, "creditMode": "Offset",
    }


PARTNER = {"Authorization": "Bearer partner-token"}
INTERNAL = {"Authorization": "Bearer internal-token"}
