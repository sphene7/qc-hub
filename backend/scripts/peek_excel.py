"""Deep peek at Excel sheet layouts."""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

TESTDATA = Path(__file__).resolve().parents[2] / "testdata"


def peek(path: Path, sheet: str, rows: int = 12, cols: int = 12) -> None:
    print(f"\n{'='*70}\n{path.name} / [{sheet}]\n{'='*70}")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=rows, max_col=cols, values_only=True), 1):
        vals = [("" if v is None else str(v)[:28]) for v in row]
        print(f"R{i:02d}: {vals}")
    wb.close()


def main() -> None:
    files = {
        "complaint": TESTDATA / "2026年客诉及反馈跟进表-更新0816.xlsx",
        "inspection": TESTDATA / "KK机种产线巡检问题清单NEW20260815.xlsx",
        "sampling": TESTDATA / "变焦产品抽检记录表2026年8月.xlsx",
    }
    peek(files["complaint"], "汇总", 15, 15)
    peek(files["complaint"], "月度推移图", 10, 9)
    peek(files["complaint"], "客诉跟进表 ", 5, 10)
    peek(files["inspection"], "问题清单 ", 5, 10)
    peek(files["inspection"], "问题点-趋势图", 8, 12)
    peek(files["inspection"], "抽检数据  ", 4, 8)
    peek(files["sampling"], "首页", 20, 10)


if __name__ == "__main__":
    main()
