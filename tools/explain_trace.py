"""
explain_trace.py

Shows the dependency walk for a single output, one step at a time, so you can
see exactly where each branch terminates and why.

    python3 explain_trace.py Adaptavate-BBE-TEST-model.xlsx out_npv

Every branch ends in one of three states, and the walk stops at each of them for
a different reason:

  [INPUT]     one of our 8 inputs. The correct ending.
  [CONSTANT]  a number typed into a cell. A real ending, but it means a
              hard-coded assumption is baked into that output.
  [EMPTY]     nothing there at all. A broken chain.
  [SEEN]      already visited on another branch. Stops to prevent looping.
  [CIRCULAR]  the chain refers back to itself. Stops and flags it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openpyxl.utils import get_column_letter, range_boundaries

from app.calc.contract import INPUT_RANGES as _CONTRACT_IN  # noqa: E402

REF_RE = re.compile(
    r"""(?:(?P<sheet>'[^']+'|[A-Za-z_][A-Za-z0-9_.]*)!)?
        (?P<start>\$?[A-Z]{1,3}\$?\d{1,7})
        (?::(?P<end>\$?[A-Z]{1,3}\$?\d{1,7}))?""",
    re.VERBOSE,
)
STRING_RE = re.compile(r'"[^"]*"')
UNTRACEABLE = {"INDIRECT", "OFFSET", "GETPIVOTDATA", "RTD", "WEBSERVICE"}

INPUT_NAMES = list(_CONTRACT_IN.values())


def k(sheet: str, coord: str) -> str:
    return f"{sheet}!{coord.replace('$','')}"


def load(path: Path):
    wb = openpyxl.load_workbook(path, data_only=False)
    wbv = openpyxl.load_workbook(path, data_only=True)

    formulas, literals = {}, {}
    for ws in wb.worksheets:
        wsv = wbv[ws.title]
        for row in ws.iter_rows():
            for cell in row:
                key = k(ws.title, cell.coordinate)
                v = cell.value
                if isinstance(v, str) and v.startswith("="):
                    formulas[key] = v
                elif v is not None:
                    literals[key] = v
                else:
                    cv = wsv[cell.coordinate].value
                    if cv is not None:
                        literals[key] = cv

    names = {}
    for nm, dn in wb.defined_names.items():
        try:
            sh, co = dn.attr_text.split("!")
            names[nm] = k(sh.strip("'"), co)
        except Exception:
            pass

    sheets = wb.sheetnames
    wb.close(); wbv.close()
    return formulas, literals, names, sheets


def refs_of(formula: str, own_sheet: str, names: dict[str, str], sheets: list[str]):
    """Which cells does this formula read? Returns (cell_keys, functions_used)."""
    body = STRING_RE.sub('""', formula[1:])
    funcs = set(re.findall(r"([A-Z][A-Z0-9\.]{1,})\s*\(", body.upper()))
    funcs = {f.replace("_XLFN.", "") for f in funcs}

    found: list[tuple[str, str]] = []   # (cell_key, how it was written)
    if names:
        nre = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b")
        for nm in dict.fromkeys(nre.findall(body)):
            found.append((names[nm], nm))
        body = nre.sub(" ", body)

    for m in REF_RE.finditer(body):
        sh = (m.group("sheet") or own_sheet).strip("'")
        if sh not in sheets:
            continue
        start, end = m.group("start"), m.group("end")
        if end is None:
            found.append((k(sh, start), f"{sh}!{start}".replace("$", "")))
        else:
            try:
                c1, r1, c2, r2 = range_boundaries(f"{start}:{end}".replace("$", ""))
            except Exception:
                continue
            if (c2 - c1 + 1) * (r2 - r1 + 1) > 400:
                found.append((f"{sh}!{start}:{end}".replace("$", ""), "large range"))
                continue
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    found.append((k(sh, f"{get_column_letter(c)}{r}"), "in range"))
    # de-duplicate, keep order
    seen, out = set(), []
    for cell, how in found:
        if cell not in seen:
            seen.add(cell)
            out.append((cell, how))
    return out, funcs


def walk(target: str, formulas, literals, names, sheets, input_keys):
    stats = {"INPUT": 0, "CONSTANT": 0, "EMPTY": 0, "SEEN": 0, "CIRCULAR": 0,
             "steps": 0, "max_depth": 0, "untraceable": set()}
    visited: set[str] = set()

    def rec(cell: str, depth: int, path: tuple[str, ...], label: str = ""):
        stats["steps"] += 1
        stats["max_depth"] = max(stats["max_depth"], depth)
        pad = "   " * depth
        shown = f"{cell}" + (f"  ({label})" if label and label != cell else "")

        if cell in path:
            stats["CIRCULAR"] += 1
            print(f"{pad}{shown}  [CIRCULAR] refers back to itself, stopping")
            return
        if cell in input_keys:
            stats["INPUT"] += 1
            print(f"{pad}{shown}  [INPUT] {input_keys[cell]} = {literals.get(cell)}")
            print(f"{pad}   -> END OF STRING: this is one of our inputs")
            return
        if cell in formulas:
            if cell in visited:
                stats["SEEN"] += 1
                print(f"{pad}{shown}  [SEEN] already traced on another branch")
                return
            visited.add(cell)
            f = formulas[cell]
            children, funcs = refs_of(f, cell.split("!")[0], names, sheets)
            bad = funcs & UNTRACEABLE
            stats["untraceable"] |= bad
            flag = f"  [!! {', '.join(sorted(bad))} untraceable]" if bad else ""
            print(f"{pad}{shown}  = {f}{flag}")
            if not children:
                stats["CONSTANT"] += 1
                print(f"{pad}   -> END OF STRING: formula reads no other cell")
                return
            for child, how in children:
                rec(child, depth + 1, path + (cell,), how)
            return
        if cell in literals:
            stats["CONSTANT"] += 1
            print(f"{pad}{shown}  [CONSTANT] = {literals[cell]}")
            print(f"{pad}   -> END OF STRING: a typed-in value, not a formula, "
                  f"nothing behind it")
            return
        stats["EMPTY"] += 1
        print(f"{pad}{shown}  [EMPTY] nothing in this cell")
        print(f"{pad}   -> END OF STRING: BROKEN, the chain points at nothing")

    print(f"\nWALKING BACKWARDS FROM {target}\n" + "-" * 70)
    rec(target, 0, ())
    return stats


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    path, want = Path(sys.argv[1]), sys.argv[2]
    formulas, literals, names, sheets = load(path)
    if want not in names:
        print(f"'{want}' is not a named range in this workbook.")
        print("Available:", ", ".join(sorted(names)[:30]))
        sys.exit(1)
    input_keys = {names[n]: n for n in INPUT_NAMES if n in names}

    s = walk(names[want], formulas, literals, names, sheets, input_keys)

    print("\n" + "=" * 70)
    print("HOW THE WALK TERMINATED")
    print("=" * 70)
    print(f"   cells visited:            {s['steps']}")
    print(f"   deepest chain:            {s['max_depth']} links")
    print(f"   ended at an INPUT:        {s['INPUT']}")
    print(f"   ended at a CONSTANT:      {s['CONSTANT']}")
    print(f"   ended at an EMPTY cell:   {s['EMPTY']}  {'<- BROKEN' if s['EMPTY'] else ''}")
    print(f"   stopped, already seen:    {s['SEEN']}")
    print(f"   stopped, circular:        {s['CIRCULAR']}  {'<- FLAG' if s['CIRCULAR'] else ''}")
    if s["untraceable"]:
        print(f"   untraceable functions:    {', '.join(sorted(s['untraceable']))}")
    print()
    print("   The walk is finished when every branch has hit one of the above.")
    print("   There is no separate 'end marker' in a spreadsheet. A cell is the")
    print("   end of a string precisely because it contains no formula, so there")
    print("   is nothing further to follow.")
