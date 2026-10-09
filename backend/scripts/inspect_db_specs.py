"""Inspect stored project specs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import init_database, get_db_session
from app.models import Project
from app import store


def main() -> None:
    init_database()
    db = get_db_session()
    try:
        for p in db.query(Project).all():
            print("=" * 60)
            print(p.project_id, p.name)
            print("integration_config:", "yes" if p.integration_config else "no")
            item = store.get(p.project_id, db)
            spec = item["spec"]
            dd = spec.get("dashboard_design")
            print("dashboard_design:", "yes" if dd else "no")
            if dd:
                bu = dd.get("business_understanding") or {}
                print("  type:", bu.get("type"))
                print("  kpis:", len(dd.get("kpis") or []))
                print("  charts:", len(dd.get("charts") or []))
                mt = dd.get("main_table") or {}
                print("  main_table:", mt.get("sheet"))
            print("primary_sheet:", spec.get("primary_sheet"))
            for s in spec["sheets"]:
                form = s.get("form") or {}
                name = s["name"].strip()
                print(
                    f"  [{name}] kind={s['kind']} rows={s['row_count']} "
                    f"form={form.get('enabled')} fields={len(form.get('fields') or [])} "
                    f"computed={len(form.get('computed') or [])}"
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
