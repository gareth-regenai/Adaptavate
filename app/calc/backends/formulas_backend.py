"""Pure-Python backend. Preferred route, roughly 60x faster than LibreOffice.

Parses the workbook into a dependency graph once at startup, then recalculates
in-process per request. Works only if the workbook sticks to standard formulas.
Run tools/inspect_workbook.py against Adaptavate's file before committing to it.
"""

from __future__ import annotations

import logging
import threading
import time
import warnings
from pathlib import Path

import openpyxl

from app.calc.backends.base import Backend, scalar
from app.calc.contract import INPUT_RANGES, INTERNAL_RANGES, OUTPUT_RANGES

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)


class MissingNamedRange(RuntimeError):
    """The workbook does not define a range the contract requires."""


class FormulasBackend(Backend):
    name = "formulas"

    def __init__(self, workbook_path: str | Path):
        import formulas  # imported lazily so the other backend needs no dependency

        self.path = Path(workbook_path)
        started = time.time()
        self._model = formulas.ExcelModel().loads(str(self.path)).finish()
        self._cells = self._resolve_named_ranges()
        # The solver is not safe to share across threads.
        self._lock = threading.Lock()
        log.info("FormulasBackend ready in %.1fs", time.time() - started)

    def _resolve_named_ranges(self) -> dict[str, str]:
        """Map each contract name to the fully-qualified key the solver uses.

        openpyxl understands named ranges; the formulas library wants
        "'[file.xlsx]SHEET'!B5". This bridges the two.
        """
        wb = openpyxl.load_workbook(self.path, data_only=False)
        try:
            resolved: dict[str, str] = {}
            required = list(INPUT_RANGES.values()) + list(OUTPUT_RANGES.values())
            optional = list(INTERNAL_RANGES.values())
            for name in required + optional:
                if name not in wb.defined_names:
                    if name in optional:
                        # Internal extras are a nice-to-have. If Adaptavate's
                        # workbook does not expose them, Adaptavate Mode simply
                        # shows fewer figures rather than the service refusing
                        # to start.
                        log.warning("optional internal range '%s' not in workbook", name)
                        continue
                    raise MissingNamedRange(
                        f"Named range '{name}' is missing from {self.path.name}. "
                        "Ask Adaptavate to add it. Do not substitute a cell "
                        "coordinate, see docs/FOLLOWING-THE-STRING.md."
                    )
                ref = wb.defined_names[name].attr_text  # "'Outputs'!$B$2"
                sheet, cell = ref.split("!")
                sheet = sheet.strip("'").upper()
                resolved[name] = f"'[{self.path.name}]{sheet}'!{cell.replace('$', '')}"
            return resolved
        finally:
            wb.close()

    def compute(
        self, model_inputs: dict[str, float], include_internal: bool = False
    ) -> dict[str, float | None]:
        overrides = {
            self._cells[INPUT_RANGES[field]]: value
            for field, value in model_inputs.items()
        }
        with self._lock:
            solution = self._model.calculate(inputs=overrides, outputs=None)

        wanted = dict(OUTPUT_RANGES)
        if include_internal:
            wanted.update(INTERNAL_RANGES)
        return {
            key: scalar(solution.get(self._cells[name]))
            for key, name in wanted.items()
            if name in self._cells
        }
