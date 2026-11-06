"""回填已有送检单的事业部（按部番对照表匹配）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import init_database, get_db_session  # noqa: E402
from app.models import SamplingSubmission  # noqa: E402
from app.sampling_db import resolve_business_unit  # noqa: E402


def main() -> None:
    init_database()
    db = get_db_session()
    try:
        rows = db.query(SamplingSubmission).all()
        changed = 0
        for row in rows:
            if not row.model:
                continue
            unit = resolve_business_unit(db, row.model)
            if unit and unit != (row.business_unit or ""):
                row.business_unit = unit
                changed += 1
        db.commit()
        print(f"共 {len(rows)} 条送检单，回填 {changed} 条事业部")
    finally:
        db.close()


if __name__ == "__main__":
    main()
