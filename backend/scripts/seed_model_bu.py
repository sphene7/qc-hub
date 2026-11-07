"""把「部番 → 事业部」导入 model_bu_map。

优先读仓库内 CSV（可随代码提交），也可传 xls/xlsx/csv 路径：

    python scripts/seed_model_bu.py
    python scripts/seed_model_bu.py "E:/path/OQC  表格对应表(1).xls"

可重复执行（按部番 upsert）。对面环境拉代码后执行本脚本即可，无需再拷 Excel。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import get_db_session, init_database  # noqa: E402
from app.models import ModelBusinessUnit  # noqa: E402

DEFAULT_CSV = Path(__file__).resolve().parent / "data" / "model_bu_map.csv"
DEFAULT_XLS = r"E:\JMCL_WORK\2026_11_02\OQC  表格对应表(1).xls"


def _load_rows(path: Path) -> list[tuple[str, str, str]]:
    suffix = path.suffix.lower()
    rows: list[tuple[str, str, str]] = []

    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            start_data = True
            if header and any(h.strip() in ("部番", "机种", "产品线", "事业部") for h in header):
                start_data = False
            if start_data and header and len(header) >= 2:
                model, bu = header[0].strip(), header[1].strip()
                if model and bu:
                    rows.append((model, model.split("-")[0], bu))
            for parts in reader:
                if len(parts) < 2:
                    continue
                model = str(parts[0] or "").strip()
                bu = str(parts[1] or "").strip()
                if model and bu:
                    rows.append((model, model.split("-")[0], bu))
        return rows

    if suffix == ".xls":
        import xlrd

        book = xlrd.open_workbook(str(path))
        sheet = book.sheet_by_index(0)
        for r in range(1, sheet.nrows):
            model = str(sheet.cell_value(r, 0)).strip()
            bu = str(sheet.cell_value(r, 1)).strip()
            if model and bu:
                rows.append((model, model.split("-")[0], bu))
        return rows

    if suffix in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        first = True
        for line in ws.iter_rows(values_only=True):
            if first:
                first = False
                header = [str(c or "").strip() for c in line]
                if any(h in ("部番", "机种", "产品线", "事业部") for h in header):
                    continue
            if not line or len(line) < 2:
                continue
            model = str(line[0] or "").strip()
            bu = str(line[1] or "").strip()
            if model and bu:
                rows.append((model, model.split("-")[0], bu))
        return rows

    raise ValueError(f"不支持的文件类型：{path.suffix}")


def main(path: str | None = None) -> None:
    if path:
        source = Path(path)
    elif DEFAULT_CSV.exists():
        source = DEFAULT_CSV
    else:
        source = Path(DEFAULT_XLS)

    if not source.exists():
        raise SystemExit(f"找不到对照表文件：{source}")

    rows = _load_rows(source)
    if not rows:
        raise SystemExit(f"文件无有效数据：{source}")

    init_database()
    db = get_db_session()
    try:
        existing = {m.model: m for m in db.query(ModelBusinessUnit).all()}
        added = updated = 0
        for model, base, bu in rows:
            item = existing.get(model)
            if item is None:
                db.add(ModelBusinessUnit(model=model, base_model=base, business_unit=bu))
                added += 1
            elif item.business_unit != bu or item.base_model != base:
                item.business_unit = bu
                item.base_model = base
                updated += 1
        db.commit()
        total = db.query(ModelBusinessUnit).count()
        print(f"来源：{source}")
        print(f"导入完成：新增 {added}，更新 {updated}，表内共 {total} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
