"""Excel formula parsing: references, R1C1 patterns, VLOOKUP joins."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

FUNC_RE = re.compile(r"\b([A-Z][A-Z0-9.]+)\s*\(", re.I)

# 'Sheet Name'!$A$2:$B$10  |  Sheet1!A:A  |  $C$3  |  C3:E3
REF_RE = re.compile(
    r"(?:'([^']+)'|([A-Za-z0-9_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff ]*))!"
    r"|(\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)"
    r"|(\$?[A-Z]{1,3}:\$?[A-Z]{1,3})(?!\d)",
    re.I,
)

SHEET_REF_RE = re.compile(
    r"(?:'([^']+)'|([A-Za-z0-9_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff ]*))!"
    r"(\$?[A-Z]{1,3}(?::\$?[A-Z]{1,3}(?!\d)|\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?))",
    re.I,
)

LOCAL_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_'!])(\$?[A-Z]{1,3})(\$?\d+)(?::(\$?[A-Z]{1,3})(\$?\d+))?",
    re.I,
)

COL_RANGE_RE = re.compile(
    r"(?<![A-Za-z0-9_'!])(\$?[A-Z]{1,3}):(\$?[A-Z]{1,3})(?!\d)",
    re.I,
)

VLOOKUP_RE = re.compile(
    r"VLOOKUP\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*(\d+)\s*,",
    re.I,
)

COUNTIF_RE = re.compile(
    r"COUNTIFS?\s*\(",
    re.I,
)


def col_letters_to_index(letters: str) -> int:
    letters = letters.replace("$", "").upper()
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def index_to_col_letters(idx: int) -> str:
    out = []
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out.append(chr(65 + rem))
    return "".join(reversed(out))


def _sheet_name(quoted: str | None, plain: str | None) -> str | None:
    if quoted is not None:
        return quoted
    if plain is not None:
        return plain
    return None


def extract_functions(formula: str) -> list[str]:
    return [m.group(1).upper() for m in FUNC_RE.finditer(formula or "")]


def extract_refs(formula: str, current_sheet: str) -> list[dict[str, Any]]:
    """Pull cell / range references from a formula."""
    if not formula:
        return []
    text = formula[1:] if formula.startswith("=") else formula
    refs: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    for m in SHEET_REF_RE.finditer(text):
        sheet = (m.group(1) or m.group(2) or current_sheet).strip()
        rng = m.group(3)
        key = (sheet, rng.upper())
        if key in seen:
            continue
        seen.add(key)
        refs.append(_parse_range_token(sheet, rng, current_sheet))

    # local A1 / A1:B2
    for m in LOCAL_REF_RE.finditer(text):
        start = m.start()
        # skip if preceded by ! (already captured as sheet ref)
        if start > 0 and text[start - 1] == "!":
            continue
        c1, r1, c2, r2 = m.group(1), m.group(2), m.group(3), m.group(4)
        token = m.group(0)
        key = (current_sheet, token.upper())
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "sheet": current_sheet,
                "same_sheet": True,
                "token": token,
                "col": col_letters_to_index(c1),
                "row": int(r1.replace("$", "")),
                "col_abs": "$" in c1,
                "row_abs": "$" in r1,
                "end_col": col_letters_to_index(c2) if c2 else None,
                "end_row": int(r2.replace("$", "")) if r2 else None,
                "kind": "range" if c2 else "cell",
            }
        )

    for m in COL_RANGE_RE.finditer(text):
        start = m.start()
        if start > 0 and text[start - 1] == "!":
            continue
        token = m.group(0)
        key = (current_sheet, token.upper())
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "sheet": current_sheet,
                "same_sheet": True,
                "token": token,
                "col": col_letters_to_index(m.group(1)),
                "row": None,
                "end_col": col_letters_to_index(m.group(2)),
                "end_row": None,
                "kind": "col_range",
            }
        )
    return refs


def _parse_range_token(sheet: str, rng: str, current_sheet: str) -> dict[str, Any]:
    rng = rng.strip()
    same = sheet == current_sheet
    col_range = re.match(r"^(\$?[A-Z]{1,3}):(\$?[A-Z]{1,3})$", rng, re.I)
    if col_range:
        return {
            "sheet": sheet,
            "same_sheet": same,
            "token": rng,
            "col": col_letters_to_index(col_range.group(1)),
            "row": None,
            "end_col": col_letters_to_index(col_range.group(2)),
            "end_row": None,
            "kind": "col_range",
        }
    cell_range = re.match(
        r"^(\$?[A-Z]{1,3})(\$?\d+)(?::(\$?[A-Z]{1,3})(\$?\d+))?$", rng, re.I
    )
    if cell_range:
        c2, r2 = cell_range.group(3), cell_range.group(4)
        return {
            "sheet": sheet,
            "same_sheet": same,
            "token": rng,
            "col": col_letters_to_index(cell_range.group(1)),
            "row": int(cell_range.group(2).replace("$", "")),
            "end_col": col_letters_to_index(c2) if c2 else None,
            "end_row": int(r2.replace("$", "")) if r2 else None,
            "kind": "range" if c2 else "cell",
        }
    return {
        "sheet": sheet,
        "same_sheet": same,
        "token": rng,
        "col": None,
        "row": None,
        "kind": "unknown",
    }


def to_r1c1(formula: str, row: int, col: int) -> str:
    """Convert A1-style same-sheet refs to R1C1 relative to (row, col)."""
    if not formula:
        return ""
    text = formula[1:] if formula.startswith("=") else formula

    def repl_cell(m: re.Match) -> str:
        start = m.start()
        if start > 0 and text[start - 1] == "!":
            return m.group(0)
        c1, r1, c2, r2 = m.group(1), m.group(2), m.group(3), m.group(4)

        def one(c_tok: str, r_tok: str) -> str:
            c_abs = "$" in c_tok
            r_abs = "$" in r_tok
            c_i = col_letters_to_index(c_tok)
            r_i = int(r_tok.replace("$", ""))
            c_part = f"C{c_i}" if c_abs else f"C[{c_i - col}]"
            r_part = f"R{r_i}" if r_abs else f"R[{r_i - row}]"
            return r_part + c_part

        if c2:
            return one(c1, r1) + ":" + one(c2, r2)
        return one(c1, r1)

    return LOCAL_REF_RE.sub(repl_cell, text)


def parse_vlookups(formula: str, current_sheet: str) -> list[dict[str, Any]]:
    if not formula:
        return []
    text = formula[1:] if formula.startswith("=") else formula
    out = []
    for m in VLOOKUP_RE.finditer(text):
        lookup, table, index = m.group(1).strip(), m.group(2).strip(), int(m.group(3))
        lookup_refs = extract_refs("=" + lookup, current_sheet)
        table_refs = extract_refs("=" + table, current_sheet)
        lookup_col = lookup_refs[0]["col"] if lookup_refs else None
        table_ref = table_refs[0] if table_refs else None
        return_col = None
        if table_ref and table_ref.get("col"):
            start = table_ref["col"]
            end = table_ref.get("end_col") or start
            return_col = start + index - 1
            if return_col > end:
                return_col = end
        out.append(
            {
                "lookup_expr": lookup,
                "lookup_col": lookup_col,
                "table": table,
                "table_sheet": (table_ref or {}).get("sheet"),
                "table_key_col": (table_ref or {}).get("col"),
                "return_col": return_col,
                "index": index,
            }
        )
    return out


def analyze_column_formulas(
    formulas: dict[tuple[int, int], str],
    header_row: int,
    last_row: int,
    last_col: int,
    sheet: str,
    headers: list[str],
) -> list[dict[str, Any]]:
    """Detect fill-down column formulas and cross-sheet joins."""
    columns: list[dict[str, Any]] = []
    for c in range(1, last_col + 1):
        patterns: list[str] = []
        samples: list[str] = []
        funcs: Counter[str] = Counter()
        dep_cols: Counter[int] = Counter()
        cross_sheets: set[str] = set()
        vlookups: list[dict[str, Any]] = []
        count = 0
        for r in range(header_row + 1, last_row + 1):
            f = formulas.get((r, c))
            if not f:
                continue
            count += 1
            if len(samples) < 3:
                samples.append(f)
            r1c1 = to_r1c1(f, r, c)
            patterns.append(r1c1)
            for fn in extract_functions(f):
                funcs[fn] += 1
            for ref in extract_refs(f, sheet):
                if ref.get("same_sheet") and ref.get("col"):
                    if ref["col"] != c:
                        dep_cols[ref["col"]] += 1
                elif ref.get("sheet") and ref["sheet"] != sheet:
                    cross_sheets.add(ref["sheet"])
            vlookups.extend(parse_vlookups(f, sheet))
        if count == 0:
            continue
        most, freq = Counter(patterns).most_common(1)[0]
        coverage = freq / max(count, 1)
        data_rows = max(last_row - header_row, 1)
        fill_ratio = count / data_rows
        if fill_ratio < 0.3 and coverage < 0.5:
            continue
        dep_names = []
        for col_i, _n in dep_cols.most_common(8):
            if 1 <= col_i <= len(headers):
                dep_names.append(headers[col_i - 1])
        name = headers[c - 1] if 0 <= c - 1 < len(headers) else index_to_col_letters(c)
        expr = _humanize_pattern(most, headers, c)
        kind = _classify_formula_kind(funcs, vlookups, dep_names)
        columns.append(
            {
                "col": c,
                "name": name,
                "pattern": most,
                "sample": samples[0] if samples else "",
                "coverage": round(coverage, 3),
                "fill_ratio": round(fill_ratio, 3),
                "functions": [fn for fn, _ in funcs.most_common(6)],
                "depends_on": dep_names,
                "cross_sheets": sorted(cross_sheets),
                "vlookups": _dedupe_vlookups(vlookups, headers),
                "kind": kind,
                "expr": expr,
            }
        )
    return columns


def _dedupe_vlookups(items: list[dict[str, Any]], headers: list[str]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for v in items:
        key = (v.get("lookup_col"), v.get("table"), v.get("index"))
        if key in seen:
            continue
        seen.add(key)
        lookup_name = None
        lc = v.get("lookup_col")
        if lc and 1 <= lc <= len(headers):
            lookup_name = headers[lc - 1]
        out.append({**v, "lookup_name": lookup_name})
    return out


def _humanize_pattern(pattern: str, headers: list[str], self_col: int) -> str:
    """Turn R1C1 like R[0]C[-6]/R[0]C[-3] into 不良数量 / 外观抽检数量 when possible."""

    def repl(m: re.Match) -> str:
        rpart, cpart = m.group(1), m.group(2)
        if rpart not in ("R[0]", "R"):
            return m.group(0)
        if cpart.startswith("C[") and cpart.endswith("]"):
            try:
                delta = int(cpart[2:-1])
            except ValueError:
                return m.group(0)
            idx = self_col + delta
        elif cpart.startswith("C") and cpart[1:].isdigit():
            idx = int(cpart[1:])
        else:
            return m.group(0)
        if 1 <= idx <= len(headers):
            return "{" + headers[idx - 1] + "}"
        return m.group(0)

    text = re.sub(r"(R\[?-?\d*\]?)(C\[?-?\d*\])", repl, pattern)
    text = text.replace("R[0]", "").replace("+", " + ").replace("-", " - ")
    text = text.replace("*", " * ").replace("/", " / ")
    return re.sub(r"\s+", " ", text).strip()


def _classify_formula_kind(funcs: Counter, vlookups: list, dep_names: list[str]) -> str:
    fns = set(funcs)
    if vlookups or "VLOOKUP" in fns or "XLOOKUP" in fns:
        return "lookup"
    if fns & {"COUNTIF", "COUNTIFS", "SUMIF", "SUMIFS", "SUMPRODUCT", "AVERAGEIF"}:
        return "aggregate"
    if fns & {"LEFT", "RIGHT", "MID", "FIND", "SEARCH", "TEXT"}:
        return "extract"
    if "ROW" in fns:
        return "index"
    if dep_names:
        return "calculated"
    return "formula"


def collect_sheet_formulas(
    formulas: dict[tuple[int, int], str],
    sheet: str,
    header_row: int,
    last_row: int,
    last_col: int,
    headers: list[str],
) -> dict[str, Any]:
    samples = []
    func_counter: Counter[str] = Counter()
    cross: set[str] = set()
    for (r, c), f in formulas.items():
        if not (1 <= r <= last_row and 1 <= c <= last_col):
            continue
        for fn in extract_functions(f):
            func_counter[fn] += 1
        for ref in extract_refs(f, sheet):
            if ref.get("sheet") and ref["sheet"] != sheet:
                cross.add(ref["sheet"])
        if len(samples) < 8:
            samples.append({"cell": f"{index_to_col_letters(c)}{r}", "formula": f[:180]})
    column_formulas = analyze_column_formulas(
        formulas, header_row, last_row, last_col, sheet, headers
    )
    return {
        "count": len(formulas),
        "functions": [{"name": n, "count": c} for n, c in func_counter.most_common(12)],
        "cross_sheets": sorted(cross),
        "samples": samples,
        "columns": column_formulas,
    }
