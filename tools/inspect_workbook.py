"""
inspect_workbook.py

Run this the moment Adaptavate's workbook arrives, before writing any code.

It answers the day-one questions in docs/03-excel-integration.md automatically
and tells you which calculation backend is viable. It only reads, it never
modifies the file.

    python3 inspect_workbook.py /path/to/Adaptavate-BBE-model.xlsx

Output is a report you can paste straight back to Gareth.
"""

from __future__ import annotations

import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.calc.contract import INPUT_RANGES as _CONTRACT_IN  # noqa: E402
from app.calc.contract import OUTPUT_RANGES as _CONTRACT_OUT  # noqa: E402

# Functions the pure-Python route commonly cannot handle, or that make a
# workbook unreliable to recalculate outside Excel itself.
RISKY_FUNCTIONS = {
    "INDIRECT": "resolves a reference from text, cannot be traced statically",
    "OFFSET": "volatile reference, often unsupported",
    "NOW": "volatile, result changes every recalculation",
    "TODAY": "volatile, result changes every recalculation",
    "RAND": "volatile, non-deterministic",
    "RANDBETWEEN": "volatile, non-deterministic",
    "CELL": "environment dependent",
    "INFO": "environment dependent",
    "GETPIVOTDATA": "depends on a live pivot cache",
    "RTD": "real-time data feed",
    "WEBSERVICE": "makes a network call",
    "FILTERXML": "usually paired with WEBSERVICE",
    "XLOOKUP": "newer function, check library support",
    "LET": "newer function, check library support",
    "LAMBDA": "newer function, check library support",
    "TEXTJOIN": "check library support",
    "SUMPRODUCT": "usually fine, but often used array-style",
}

EXPECTED_INPUT_NAMES = list(_CONTRACT_IN.values())
EXPECTED_OUTPUT_NAMES = list(_CONTRACT_OUT.values())


def h(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def inspect(path: Path) -> dict:
    findings = {"blockers": [], "warnings": [], "notes": []}

    # ---------------------------------------------------------------- file
    h("1. FILE")
    size_mb = path.stat().st_size / 1_048_576
    print(f"   Name: {path.name}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"   Extension: {path.suffix}")
    if path.suffix.lower() == ".xlsb":
        findings["blockers"].append(
            "File is .xlsb (binary format). openpyxl cannot read it. Ask for .xlsx."
        )
        print("   BLOCKER: .xlsb is not readable by openpyxl. Request .xlsx.")
    if path.suffix.lower() == ".xlsm":
        findings["warnings"].append("File is .xlsm, so it is macro-enabled. See section 4.")
    if size_mb > 25:
        findings["warnings"].append(
            f"Large workbook ({size_mb:.0f} MB). Expect slow load and calculation."
        )

    # ------------------------------------------------------- macros & links
    h("2. MACROS AND EXTERNAL CONNECTIONS")
    has_vba = has_extlink = has_conn = False
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            has_vba = any("vbaProject" in n for n in names)
            has_extlink = any("externalLink" in n for n in names)
            has_conn = any("connections.xml" in n for n in names)
    except zipfile.BadZipFile:
        findings["blockers"].append("File is not a valid xlsx archive.")
        print("   BLOCKER: not a readable xlsx archive.")
        return findings

    print(f"   VBA macros present:        {'YES' if has_vba else 'no'}")
    print(f"   Links to other workbooks:  {'YES' if has_extlink else 'no'}")
    print(f"   External data connections: {'YES' if has_conn else 'no'}")

    if has_vba:
        findings["warnings"].append(
            "Workbook contains VBA. If any output depends on a macro running, the "
            "pure-Python route will not work. Use the LibreOffice backend, and "
            "confirm with Adaptavate whether a macro must run to produce the outputs."
        )
    if has_extlink or has_conn:
        findings["blockers"].append(
            "Workbook links to external data. Those links will not resolve on a "
            "server. Ask Adaptavate for a self-contained copy with values pasted in."
        )

    # ------------------------------------------------------------- sheets
    h("3. SHEETS")
    wb = openpyxl.load_workbook(path, data_only=False, keep_vba=False)
    print(f"   {len(wb.sheetnames)} sheet(s):")
    for name in wb.sheetnames:
        ws = wb[name]
        state = ws.sheet_state
        print(f"      {name:28} {ws.max_row:>6} rows x {ws.max_column:>4} cols   {state}")
        if state != "visible":
            findings["notes"].append(f"Sheet '{name}' is {state}.")

    # ------------------------------------------------------ formula profile
    h("4. FORMULA PROFILE")
    func_counter: Counter[str] = Counter()
    formula_cells = 0
    array_like = 0
    risky_hits: dict[str, list[str]] = {}

    for name in wb.sheetnames:
        ws = wb[name]
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if not isinstance(v, str) or not v.startswith("="):
                    continue
                formula_cells += 1
                if v.startswith("=_xlfn") or "_xlfn." in v:
                    array_like += 1
                for fn in re.findall(r"([A-Z][A-Z0-9\.]{1,})\s*\(", v.upper()):
                    fn = fn.replace("_XLFN.", "")
                    func_counter[fn] += 1
                    if fn in RISKY_FUNCTIONS:
                        risky_hits.setdefault(fn, []).append(f"{name}!{cell.coordinate}")

    print(f"   Formula cells: {formula_cells}")
    if formula_cells == 0:
        findings["blockers"].append(
            "No formulas found. Either the file has been sent as values only, or "
            "the model is elsewhere. Query with Adaptavate before proceeding."
        )
    print(f"   Distinct functions used: {len(func_counter)}")
    if func_counter:
        print("   Most used:")
        for fn, n in func_counter.most_common(12):
            print(f"      {fn:16} {n}")

    if risky_hits:
        print("\n   FUNCTIONS THAT NEED ATTENTION:")
        for fn, cells in risky_hits.items():
            print(f"      {fn:14} {len(cells)} use(s), e.g. {cells[0]}")
            print(f"                     {RISKY_FUNCTIONS[fn]}")
        findings["warnings"].append(
            "Risky functions present: " + ", ".join(risky_hits)
            + ". Test these specifically before choosing the pure-Python backend."
        )
    else:
        print("\n   No risky functions detected. Pure-Python backend is a good candidate.")

    # ------------------------------------------------------- named ranges
    h("5. NAMED RANGES")
    defined = dict(wb.defined_names)
    print(f"   {len(defined)} named range(s) defined.")
    if defined:
        for n in list(defined)[:25]:
            print(f"      {n:28} -> {defined[n].attr_text}")
        if len(defined) > 25:
            print(f"      ... and {len(defined)-25} more")

    missing_in = [n for n in EXPECTED_INPUT_NAMES if n not in defined]
    missing_out = [n for n in EXPECTED_OUTPUT_NAMES if n not in defined]
    if missing_in or missing_out:
        print("\n   MISSING the names our engine expects:")
        for n in missing_in + missing_out:
            print(f"      {n}")
        findings["blockers"].append(
            f"{len(missing_in)+len(missing_out)} expected named range(s) missing. "
            "Either ask Adaptavate to add them, or map their existing names to ours "
            "in engine.py's INPUT_RANGES / OUTPUT_RANGES. Do not substitute raw "
            "cell coordinates."
        )
    else:
        print("\n   All expected input and output names present.")

    # --------------------------------------------------- cached values check
    h("6. ARE CALCULATED VALUES CACHED IN THE FILE?")
    wbv = openpyxl.load_workbook(path, data_only=True)
    cached = uncached = 0
    for name in wbv.sheetnames:
        wsv, wsf = wbv[name], wb[name]
        for row in wsf.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    if wsv[name and cell.coordinate].value is None:
                        uncached += 1
                    else:
                        cached += 1
    print(f"   Formula cells with a cached value: {cached}")
    print(f"   Formula cells with no cached value: {uncached}")
    if uncached and not cached:
        findings["notes"].append(
            "No cached values at all. The file was likely generated programmatically. "
            "This is fine, the engine recalculates anyway."
        )
    print("   (Either way the engine recalculates. This is only a clue about origin.)")

    # ------------------------------------------------------- recommendation
    h("7. RECOMMENDATION")
    if findings["blockers"]:
        print("   DO NOT START THE BUILD YET. Blockers:")
        for b in findings["blockers"]:
            print(f"      - {b}")
    else:
        print("   No blockers found.")

    if findings["warnings"]:
        print("\n   Warnings:")
        for w in findings["warnings"]:
            print(f"      - {w}")

    if findings["notes"]:
        print("\n   Notes:")
        for n in findings["notes"]:
            print(f"      - {n}")

    if not findings["blockers"]:
        if has_vba or risky_hits or has_extlink:
            print("\n   Suggested backend: libreoffice (safer given the above)")
            print("   Then benchmark it. If per-calculation time exceeds 400ms,")
            print("   escalate, the interface will feel laggy to a partner.")
        else:
            print("\n   Suggested backend: formulas (pure Python, roughly 60x faster)")
            print("   Verify against the real numbers before trusting it.")

    wb.close()
    wbv.close()
    return findings


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    target = Path(sys.argv[1])
    if not target.exists():
        print(f"Not found: {target}")
        sys.exit(1)
    print(f"\nINSPECTING: {target}")
    result = inspect(target)
    print("\n" + "=" * 72)
    print(f"SUMMARY: {len(result['blockers'])} blocker(s), "
          f"{len(result['warnings'])} warning(s), {len(result['notes'])} note(s)")
    print("=" * 72 + "\n")
    sys.exit(2 if result["blockers"] else 0)
