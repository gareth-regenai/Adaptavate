"""LibreOffice backend. Fallback for workbooks the pure-Python route cannot handle.

Drives a real spreadsheet engine, so it copes with macros, volatile functions and
the awkward corners of Excel. Costs roughly 1 second per calculation against 16ms,
which is slow enough to feel laggy while dragging a slider. Use it only when
inspect_workbook.py says the workbook needs it.

Each call works on a throwaway copy; the source workbook is never modified.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import openpyxl

from app.calc.backends.base import Backend, scalar
from app.calc.contract import INPUT_RANGES, INTERNAL_RANGES, OUTPUT_RANGES

log = logging.getLogger(__name__)


class LibreOfficeBackend(Backend):
    name = "libreoffice"

    def __init__(
        self,
        workbook_path: str | Path,
        soffice: str = "soffice",
        timeout: int = 120,
    ):
        self.path = Path(workbook_path)
        self.soffice = soffice
        self.timeout = timeout
        # LibreOffice dislikes concurrent use of the same user profile.
        self._lock = threading.Lock()
        self._ranges = self._read_ranges()

    def _read_ranges(self) -> dict[str, tuple[str, str]]:
        wb = openpyxl.load_workbook(self.path, data_only=False)
        try:
            out: dict[str, tuple[str, str]] = {}
            required = list(INPUT_RANGES.values()) + list(OUTPUT_RANGES.values())
            for name in required + list(INTERNAL_RANGES.values()):
                if name not in wb.defined_names:
                    if name in INTERNAL_RANGES.values():
                        log.warning("optional internal range '%s' not in workbook", name)
                        continue
                    raise RuntimeError(
                        f"Named range '{name}' is missing from {self.path.name}."
                    )
                sheet, cell = wb.defined_names[name].attr_text.split("!")
                out[name] = (sheet.strip("'"), cell.replace("$", ""))
            return out
        finally:
            wb.close()

    def compute(
        self, model_inputs: dict[str, float], include_internal: bool = False
    ) -> dict[str, float | None]:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            work = tmpdir / self.path.name
            shutil.copy2(self.path, work)

            wb = openpyxl.load_workbook(work, data_only=False)
            try:
                for field, value in model_inputs.items():
                    sheet, cell = self._ranges[INPUT_RANGES[field]]
                    wb[sheet][cell] = value
                wb.save(work)
            finally:
                wb.close()

            outdir = tmpdir / "out"
            with self._lock:
                subprocess.run(
                    [
                        self.soffice, "--headless", "--norestore",
                        "--convert-to", "xlsx:Calc MS Excel 2007 XML",
                        "--outdir", str(outdir), str(work),
                    ],
                    check=True,
                    timeout=self.timeout,
                    capture_output=True,
                )

            done = openpyxl.load_workbook(outdir / self.path.name, data_only=True)
            try:
                wanted = dict(OUTPUT_RANGES)
                if include_internal:
                    wanted.update(INTERNAL_RANGES)
                return {
                    key: scalar(done[self._ranges[name][0]][self._ranges[name][1]].value)
                    for key, name in wanted.items()
                    if name in self._ranges
                }
            finally:
                done.close()
