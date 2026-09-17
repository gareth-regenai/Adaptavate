"""
trace_dependencies.py

Answers the question: for each output we care about, what does it ACTUALLY
depend on, all the way back?

Run it on Adaptavate's workbook and it will:

  1. Build a map of which cell feeds which, across every sheet
  2. Walk backwards from each of our 12 outputs to everything it touches
  3. Tell you which of our 8 inputs each output genuinely reaches
  4. FLAG THE DANGEROUS CASE: an output that depends on a cell which is not one
     of our inputs and not a formula, i.e. a hard-coded value nobody told us
     about, which the partner can never change
  5. Report the minimal subset of the workbook the tool actually needs, so a
     100,000 variable model can be cut down to only the part that matters
  6. Flag broken chains: references to empty cells, or to cells that cannot be
     traced statically

    python3 trace_dependencies.py model/Adaptavate-BBE-model.xlsx
    python3 trace_dependencies.py model/Adaptavate-BBE-model.xlsx --slice slice.json

It only reads. It never modifies the workbook.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openpyxl.utils import get_column_letter, range_boundaries

from app.calc.contract import INPUT_RANGES as _CONTRACT_IN  # noqa: E402
from app.calc.contract import OUTPUT_RANGES as _CONTRACT_OUT  # noqa: E402

# Our contract, same names as engine.py
INPUT_NAMES = list(_CONTRACT_IN.values())
OUTPUT_NAMES = list(_CONTRACT_OUT.values())

# Functions whose references cannot be resolved by reading the formula text.
# If one of these sits in a chain, the chain cannot be fully verified statically.
UNTRACEABLE = {"INDIRECT", "OFFSET", "GETPIVOTDATA", "RTD", "WEBSERVICE"}

# A reference like 'Some Sheet'!$B$5:$C$9 or Sheet1!B5 or $B$5 or B5
REF_RE = re.compile(
    r"""(?:(?P<sheet>'[^']+'|[A-Za-z_][A-Za-z0-9_.]*)!)?      # optional sheet
        (?P<start>\$?[A-Z]{1,3}\$?\d{1,7})                    # first cell
        (?::(?P<end>\$?[A-Z]{1,3}\$?\d{1,7}))?                # optional range end
    """,
    re.VERBOSE,
)
FUNC_RE = re.compile(r"([A-Z][A-Z0-9\.]{1,})\s*\(")
# Strings inside formulas must be stripped before looking for references,
# otherwise ="Total B5" looks like a reference to B5.
STRING_RE = re.compile(r'"[^"]*"')


def key(sheet: str, coord: str) -> str:
    return f"{sheet}!{coord.replace('$', '')}"


def expand(sheet: str, start: str, end: str | None, cap: int = 20000) -> list[str]:
    """Turn a reference into the list of cell keys it covers."""
    if end is None:
        return [key(sheet, start)]
    try:
        min_c, min_r, max_c, max_r = range_boundaries(f"{start}:{end}".replace("$", ""))
    except Exception:
        return []
    if (max_c - min_c + 1) * (max_r - min_r + 1) > cap:
        # A whole-column reference like B:B. Record it as a range marker rather
        # than expanding a million cells.
        return [f"{sheet}!{start}:{end}".replace("$", "")]
    out = []
    for r in range(min_r, max_r + 1):
        for c in range(min_c, max_c + 1):
            out.append(key(sheet, f"{get_column_letter(c)}{r}"))
    return out


def build_graph(path: Path):
    """Read every formula and record what each cell depends on."""
    wb = openpyxl.load_workbook(path, data_only=False)
    wbv = openpyxl.load_workbook(path, data_only=True)

    depends_on: dict[str, set[str]] = defaultdict(set)   # cell -> cells it reads
    formulas: dict[str, str] = {}
    literals: dict[str, object] = {}
    funcs_in: dict[str, set[str]] = defaultdict(set)

    # Named ranges resolve to a cell key
    names: dict[str, str] = {}
    for name, dn in wb.defined_names.items():
        try:
            sheet, coord = dn.attr_text.split("!")
            names[name] = key(sheet.strip("'"), coord)
        except Exception:
            continue

    name_re = re.compile(
        r"\b(" + "|".join(re.escape(n) for n in names) + r")\b"
    ) if names else None

    for ws in wb.worksheets:
        wsv = wbv[ws.title]
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                k = key(ws.title, cell.coordinate)
                if isinstance(v, str) and v.startswith("="):
                    formulas[k] = v
                    body = STRING_RE.sub('""', v[1:])
                    for fn in FUNC_RE.findall(body.upper()):
                        funcs_in[k].add(fn.replace("_XLFN.", ""))
                    # named ranges first, so they are not mistaken for text
                    if name_re:
                        for nm in set(name_re.findall(body)):
                            depends_on[k].add(names[nm])
                        body = name_re.sub(" ", body)
                    for m in REF_RE.finditer(body):
                        sheet = (m.group("sheet") or ws.title).strip("'")
                        if sheet not in wb.sheetnames:
                            continue
                        for dep in expand(sheet, m.group("start"), m.group("end")):
                            if dep != k:
                                depends_on[k].add(dep)
                elif v is not None:
                    literals[k] = v
                else:
                    cv = wsv[cell.coordinate].value
                    if cv is not None:
                        literals[k] = cv

    wb.close()
    wbv.close()
    return depends_on, formulas, literals, names, funcs_in


def trace_back(start: str, depends_on: dict[str, set[str]]) -> set[str]:
    """Every cell that feeds into start, transitively. Cycle safe."""
    seen: set[str] = set()
    q = deque([start])
    while q:
        cur = q.popleft()
        for dep in depends_on.get(cur, ()):
            if dep not in seen:
                seen.add(dep)
                q.append(dep)
    return seen


def main(path: Path, slice_out: Path | None) -> int:
    print(f"\nTRACING: {path.name}")
    depends_on, formulas, literals, names, funcs_in = build_graph(path)

    total_cells = len(formulas) + len(literals)
    print(f"   formula cells: {len(formulas):,}")
    print(f"   value cells:   {len(literals):,}")
    print(f"   total:         {total_cells:,}")

    missing_out = [n for n in OUTPUT_NAMES if n not in names]
    if missing_out:
        print("\n   Cannot trace, these output names are not defined in the workbook:")
        for n in missing_out:
            print(f"      {n}")
        print("   Fix the named ranges first, see WORKBOOK-INTAKE-RUNBOOK.md Stage 3.")
        return 2

    input_keys = {names[n]: n for n in INPUT_NAMES if n in names}

    print("\n" + "=" * 74)
    print("PER-OUTPUT TRACE")
    print("=" * 74)

    all_needed: set[str] = set()
    problems: list[str] = []

    for out_name in OUTPUT_NAMES:
        out_key = names[out_name]
        chain = trace_back(out_key, depends_on)
        chain.add(out_key)
        all_needed |= chain

        reached = sorted({input_keys[c] for c in chain if c in input_keys})
        # Cells in the chain that are plain values and NOT one of our inputs.
        # These are the dangerous ones: baked-in assumptions the partner cannot
        # change and we did not know about.
        frozen = [c for c in chain
                  if c not in formulas and c not in input_keys and c in literals
                  and isinstance(literals[c], int | float)]
        # References into empty space: a broken string.
        dangling = [c for c in chain if c not in formulas and c not in literals]
        # Untraceable functions anywhere in the chain
        opaque = sorted({f for c in chain for f in funcs_in.get(c, ()) if f in UNTRACEABLE})

        print(f"\n{out_name}  ({out_key})")
        print(f"   cells in chain: {len(chain):,}")
        print(f"   inputs reached: {len(reached)}/{len(input_keys)}  {', '.join(reached) if reached else 'NONE'}")

        if not reached:
            problems.append(f"{out_name} does not depend on ANY of our inputs. It is a constant.")
            print("   *** DEPENDS ON NO INPUT AT ALL, this output will never change ***")
        if frozen:
            print(f"   hard-coded values in chain: {len(frozen)}")
            for c in frozen[:5]:
                print(f"      {c} = {literals[c]}")
            if len(frozen) > 5:
                print(f"      ... and {len(frozen)-5} more")
        if dangling:
            problems.append(f"{out_name} references {len(dangling)} empty cell(s), e.g. {dangling[0]}")
            print(f"   BROKEN: references {len(dangling)} empty cell(s), e.g. {dangling[0]}")
        if opaque:
            problems.append(f"{out_name} chain contains untraceable function(s): {', '.join(opaque)}")
            print(f"   UNTRACEABLE: chain uses {', '.join(opaque)}, cannot verify statically")

    # ----------------------------------------------------------- input coverage
    print("\n" + "=" * 74)
    print("INPUT COVERAGE, does every input actually drive something?")
    print("=" * 74)
    for in_name in INPUT_NAMES:
        if in_name not in names:
            print(f"   {in_name:24} NOT DEFINED in workbook")
            continue
        k = names[in_name]
        drives = [o for o in OUTPUT_NAMES if k in trace_back(names[o], depends_on)]
        if drives:
            print(f"   {in_name:24} drives {len(drives):2} output(s)")
        else:
            print(f"   {in_name:24} *** DRIVES NOTHING, wired but unused ***")
            problems.append(f"{in_name} is not used by any output. Either it is not "
                            "needed, or it is connected to the wrong cell.")

    # ------------------------------------------------------------ the slice
    print("\n" + "=" * 74)
    print("THE SLICE, how much of this workbook do we actually need?")
    print("=" * 74)
    pct = (len(all_needed) / total_cells * 100) if total_cells else 0
    print(f"   cells the 12 outputs depend on: {len(all_needed):,}")
    print(f"   cells in the whole workbook:    {total_cells:,}")
    print(f"   proportion actually needed:     {pct:.2f}%")
    print(f"   cells that could be discarded:  {total_cells - len(all_needed):,}")

    by_sheet: dict[str, int] = defaultdict(int)
    for c in all_needed:
        by_sheet[c.split("!")[0]] += 1
    print("\n   needed cells by sheet:")
    for sheet, n in sorted(by_sheet.items(), key=lambda x: -x[1]):
        print(f"      {sheet:30} {n:,}")

    wb = openpyxl.load_workbook(path, read_only=True)
    unused_sheets = [s for s in wb.sheetnames if s not in by_sheet]
    wb.close()
    if unused_sheets:
        print("\n   sheets NOT touched by any output:")
        for s in unused_sheets:
            print(f"      {s}")
        print("   These can be excluded from the served copy, subject to Adaptavate")
        print("   confirming nothing on them is needed.")

    if slice_out:
        payload = {
            "needed_cells": sorted(all_needed),
            "by_sheet": dict(by_sheet),
            "unused_sheets": unused_sheets,
            "input_map": {n: names[n] for n in INPUT_NAMES if n in names},
            "output_map": {n: names[n] for n in OUTPUT_NAMES},
        }
        slice_out.write_text(json.dumps(payload, indent=2))
        print(f"\n   slice written to {slice_out}")

    # ------------------------------------------------------------- verdict
    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    if problems:
        print(f"   {len(problems)} problem(s) to resolve with Adaptavate:\n")
        for p in problems:
            print(f"      - {p}")
        print("\n   Do not sign off Tier 1 until each of these is explained.")
        return 2
    print("   Every output traces cleanly back to our inputs.")
    print("   No broken chains, no untraceable functions, no orphaned inputs.")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    slice_path = None
    if "--slice" in sys.argv:
        i = sys.argv.index("--slice")
        if i + 1 < len(sys.argv):
            slice_path = Path(sys.argv[i + 1])
            args = [a for a in args if a != str(slice_path)]
    target = Path(args[0])
    if not target.exists():
        print(f"Not found: {target}")
        sys.exit(1)
    sys.exit(main(target, slice_path))
