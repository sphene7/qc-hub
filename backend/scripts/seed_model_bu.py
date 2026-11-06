"""把《OQC 表格对应表》的「部番 → 事业部」导入 model_bu_map。

用法：
    python scripts/seed_model_bu.py "D:/CODE/QE/OQC  表格对应表(1).xls"
不传路径时用默认路径。可重复执行（按部番 upsert）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import xlrd  # noqa: E402

from app.db import init_database, get_db_session  # noqa: E402
from app.models import ModelBusinessUnit  # noqa: E402

DEFAULT_XLS = r"D:\CODE\QE\OQC  表格对应表(1).xls"


def main(path: str) -> None:
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    rows = []
    for r in range(1, sheet.nrows):
        model = str(sheet.cell_value(r, 0)).strip()
        bu = str(sheet.cell_value(r, 1)).strip()
        if not model or not bu:
            continue
        rows.append((model, model.split("-")[0], bu))

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
        print(f"导入完成：新增 {added}，更新 {updated}，表内共 {total} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLS)
