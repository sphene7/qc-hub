"""Compare form fields vs columns and dump AI dashboard design."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import init_database, get_db_session
from app import store


def main() -> None:
    init_database()
    db = get_db_session()
    out = []
    try:
        for pid in ["c1764218cdff", "ff834b56994b", "de868e0253e9"]:
            item = store.get(pid, db)
            spec = item["spec"]
            dd = spec.get("dashboard_design") or {}
            entry = {
                "title": spec["title"],
                "primary_sheet": spec.get("primary_sheet"),
                "main_table": dd.get("main_table"),
                "charts": dd.get("charts"),
                "kpis": dd.get("kpis"),
                "filters": dd.get("filters"),
                "forms": [],
            }
            for s in spec["sheets"]:
                form = s.get("form") or {}
                if not form.get("enabled"):
                    continue
                all_cols = [c["key"] for c in s["columns"] if not c["key"].startswith("__")]
                form_fields = [f["key"] for f in form.get("fields", [])]
                computed = [f["key"] for f in form.get("computed", [])]
                missing = [c for c in all_cols if c not in form_fields and c not in computed]
                entry["forms"].append({
                    "sheet": s["name"].strip(),
                    "total_cols": len(all_cols),
                    "form_fields": form_fields,
                    "computed": computed,
                    "missing_from_form": missing,
                })
            out.append(entry)
    finally:
        db.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
