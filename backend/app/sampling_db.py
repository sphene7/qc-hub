"""抽检三级登记 —— 关系型仓储。

替代原先「三张 sheet_data + ；拼接」的存储：
* sampling_submissions  送检单
* sampling_inspections  抽检记录（每检验员一条）
* sampling_defects      不良明细（每不良一条）
* sampling_exceptions   异常处理（每抽检最多一条）
* audit_logs            审计

OQC 宽表仍是 sheet_data 里的一张表（保留给「抽检明细 / 趋势分析」），
但改为**按送检单定向增删**，不再整表重写。
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from .entry import fill_row
from .logutil import log
from .models import (
    AuditLog,
    ModelBusinessUnit,
    Project,
    SamplingDefect,
    SamplingException,
    SamplingInspection,
    SamplingInspector,
    SamplingSubmission,
    SheetData,
    User,
)

OQC_LINK_SUB = "送检单号"
OQC_LINK_INSP = "抽检单号"

SENT_FIELD = "抽检批"
PASS_FIELD = "合格批"

DEFECT_SEP = "；"

CLAUSE_FIELDS = (
    "OA单号",
    "指定质控公司",
    "责任单位",
    "责任人",
    "临时对策",
    "根因分析",
    "永久对策",
    "改善后确认",
    "结案日期",
    "结案天数",
)

OQC_PRESERVE_FIELDS = CLAUSE_FIELDS + ("责任课级负责人", "品质工程师")


def ensure_sheets(item: dict[str, Any], wid: str, db: Session) -> bool:
    """OQC 宽表补上 送检单号/抽检单号 两列（三张 JSON 表已废弃）。"""
    from .sampling_register import _col

    spec = item["spec"]
    sheet = None
    for s in spec.get("sheets") or []:
        if "OQC" in (s.get("name") or "") or "抽检批次" in (s.get("name") or ""):
            sheet = s
            break
    if sheet is None:
        return False
    keys = {c.get("key") for c in sheet.get("columns") or []}
    changed = False
    for key in (OQC_LINK_SUB, OQC_LINK_INSP):
        if key not in keys:
            sheet.setdefault("columns", []).append(_col(key, key, "dimension"))
            changed = True
    if changed:
        project = db.query(Project).filter(Project.project_id == wid).first()
        if project:
            project.spec = spec
            db.commit()
    return changed


class VersionConflict(Exception):
    """乐观锁冲突：记录已被其他人修改。"""


# ── 工具 ────────────────────────────────────────────────────────────────


def _project(db: Session, wid: str) -> Project | None:
    return db.query(Project).filter(Project.project_id == wid).first()


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat", "null"}:
        return ""
    return text

# 与抽检明细「送检类型」下拉保持一致
SUBMIT_TYPE_OPTIONS = (
    "正常送检",
    "样品送检",
    "在制返工",
    "库存返工",
    "加急送检",
    "复检",
)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    if n is None:
        return None
    return int(n) if float(n).is_integer() else int(round(n))


def _date(value: Any) -> date | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().replace(second=0, microsecond=0)


def _month_label(d: Any) -> str:
    return f"{d.year}年{d.month}月" if d else ""


def _now() -> datetime:
    return datetime.now()


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return _text(value)


def _pct(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_business_unit(db: Session, model: str) -> str:
    """机种 → 事业部：先精确匹配部番，再按「-」前基型唯一匹配。"""
    name = _text(model)
    if not name:
        return ""
    exact = db.query(ModelBusinessUnit).filter(ModelBusinessUnit.model == name).first()
    if exact is not None:
        return exact.business_unit
    base = name.split("-")[0]
    rows = db.query(ModelBusinessUnit).filter(ModelBusinessUnit.base_model == base).all()
    units = {r.business_unit for r in rows}
    return units.pop() if len(units) == 1 else ""


def _audit(db: Session, user_id: int, entity: str, entity_id: str, action: str, changes: dict) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            entity=entity,
            entity_id=str(entity_id),
            action=action,
            changes=changes,
            created_at=_now(),
        )
    )


# ── 展示数据 ────────────────────────────────────────────────────────────


def _defect_dict(d: SamplingDefect) -> dict[str, Any]:
    return {
        "不良属性": d.attr or "",
        "不良位置": d.location or "",
        "现象": d.phenomenon or "",
        "数量": d.qty,
    }


def _exception_dict(e: SamplingException | None) -> dict[str, Any] | None:
    if e is None:
        return None
    return {
        "OA单号": e.oa_no or "",
        "指定质控公司": e.qc_company or "",
        "责任单位": e.owner_dept or "",
        "责任人": e.owner or "",
        "临时对策": e.temp_action or "",
        "根因分析": e.root_cause or "",
        "永久对策": e.perm_action or "",
        "改善后确认": e.verify or "",
        "结案日期": _iso(e.close_date) if e.close_date else "",
        "结案天数": e.close_days,
        "确认者": e.confirmer or "",
        "课室负责人": e.room_owner or "",
        "责任课级负责人": e.dept_head or "",
        "品质工程师": e.quality_engineer or "",
        "登记人": "",
    }


def _inspection_dict(c: SamplingInspection, sub: SamplingSubmission) -> dict[str, Any]:
    defects = [_defect_dict(d) for d in (c.defects or [])]
    return {
        "抽检单号": c.code,
        "送检单号": sub.code,
        "日期": _iso(sub.submit_date),
        "部番": sub.part_no or sub.model or "",
        "机种": sub.model or "",
        "事业部": sub.business_unit or "",
        "送检单位": sub.department or "",
        "检验员": c.inspector or "",
        "外观抽检数量": c.appearance_qty,
        "机能抽检数量": c.function_qty,
        "不良数量": c.defect_qty,
        "不良率": _pct(c.defect_rate),
        "抽检批": c.batch_sent,
        "合格批": c.batch_pass,
        "合格批率": _pct(c.batch_rate),
        "判定": c.verdict or "OK",
        "不良属性": DEFECT_SEP.join(d["不良属性"] for d in defects) or None,
        "不良位置": DEFECT_SEP.join(d["不良位置"] for d in defects) or None,
        "现象": DEFECT_SEP.join(d["现象"] for d in defects) or None,
        "数量": DEFECT_SEP.join(str(d["数量"] or "") for d in defects) or None,
        "不良组": defects,
        "异常处理": _exception_dict(c.exception if hasattr(c, "exception") else None),
        "版本": c.version,
        "登记人": "",
        "登记时间": _iso(c.created_at),
    }


def _is_submission_ok(inspections: list[SamplingInspection]) -> bool:
    """与列表状态 OK 一致：有抽检且无不良。"""
    if not inspections:
        return False
    return not any(len(c.defects or []) > 0 for c in inspections)


def _inspect_qty(inspections: list[SamplingInspection]) -> int | None:
    """检验数量：有抽检（含 NG）时按各抽检「外观」汇总；外观为空则用机能。"""
    if not inspections:
        return None
    appearance = sum(int(c.appearance_qty or 0) for c in inspections)
    if appearance > 0:
        return appearance
    function = sum(int(c.function_qty or 0) for c in inspections)
    return function if function > 0 else None


def _submission_dict(s: SamplingSubmission) -> dict[str, Any]:
    inspections = sorted(s.inspections or [], key=lambda c: c.code)
    day = _iso(s.submit_date)
    return {
        "送检单号": s.code,
        "日期": day,  # 兼容旧字段名
        "送检日期": day,
        "月份": s.month_label or _month_label(s.submit_date),
        "送检类型": s.submit_type or "",
        "部番": s.part_no or s.model or "",
        "机种": s.model or "",
        "系列": s.series or "",
        "送检单位": s.department or "",
        "事业部": s.business_unit or "",
        "送检数量": s.qty,
        "检验数量": _inspect_qty(inspections),
        "同批送检次数": s.batch_seq,
        "是否紧急出货": s.urgent or "",
        "层别备注": s.remark or "",
        "确认者": s.confirmer or "",
        "课室负责人": s.room_owner or "",
        "完成日期": _iso(s.completed_at) if s.completed_at else "",
        "版本": s.version,
        "登记人": "",
        "登记时间": _iso(s.created_at),
        "抽检": [_inspection_dict(c, s) for c in inspections],
        "异常总数": sum(len(c.defects or []) for c in inspections),
    }


def _day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _next_batch_seq(
    db: Session,
    project_id: int,
    part_no: str,
    day: datetime,
    exclude_id: int | None = None,
) -> int:
    """同一天、同部番的送检次数：已有最大值 + 1（至少为 1）。"""
    start, end = _day_bounds(day)
    q = db.query(func.coalesce(func.max(SamplingSubmission.batch_seq), 0)).filter(
        SamplingSubmission.project_id == project_id,
        SamplingSubmission.part_no == part_no,
        SamplingSubmission.deleted_at.is_(None),
        SamplingSubmission.submit_date >= start,
        SamplingSubmission.submit_date < end,
    )
    if exclude_id is not None:
        q = q.filter(SamplingSubmission.id != exclude_id)
    return int(q.scalar() or 0) + 1


def _sync_completion(sub: SamplingSubmission) -> None:
    """判定合格（有抽检且无不良）后写入完成日期；否则清空。"""
    inspections = list(sub.inspections or [])
    if not _is_submission_ok(inspections):
        sub.completed_at = None
        return
    if sub.completed_at is None:
        sub.completed_at = _now()


def load_tree(item: dict[str, Any], db: Session, dept: str = "") -> list[dict[str, Any]]:
    project = _project(db, item["id"])
    if project is None:
        return []
    query = (
        db.query(SamplingSubmission)
        .options(
            joinedload(SamplingSubmission.inspections).joinedload(SamplingInspection.defects),
            joinedload(SamplingSubmission.inspections).joinedload(SamplingInspection.exception),
        )
        .filter(SamplingSubmission.project_id == project.id, SamplingSubmission.deleted_at.is_(None))
    )
    if dept:
        query = query.filter(SamplingSubmission.department == dept)
    rows = query.order_by(SamplingSubmission.submit_date.desc(), SamplingSubmission.code.desc()).all()

    names = _user_names(db, rows)
    tree = []
    for s in rows:
        data = _submission_dict(s)
        data["登记人"] = names.get(s.created_by, "")
        inspectors = {i.code: i.created_by for i in s.inspections}
        for c in data["抽检"]:
            c["登记人"] = names.get(inspectors.get(c["抽检单号"]), "")
        tree.append(data)
    return tree


def _user_names(db: Session, rows: list[SamplingSubmission]) -> dict[int, str]:
    ids = {s.created_by for s in rows if s.created_by}
    for s in rows:
        ids.update(c.created_by for c in (s.inspections or []) if c.created_by)
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: (u.full_name or u.username or "") for u in users}


def _split_parts(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    parts: list[str] = []
    for line in text.splitlines():
        for part in re.split(r"[;；|｜/／]+", line):
            cleaned = part.strip()
            if cleaned:
                parts.append(cleaned)
    return parts


def options(item: dict[str, Any], db: Session) -> dict[str, Any]:
    project = _project(db, item["id"])
    if project is None:
        return {}

    def uniq(values) -> list[str]:
        seen: list[str] = []
        for v in values:
            s = _text(v)
            if s and s not in seen:
                seen.append(s)
        return sorted(seen)

    subs = db.query(SamplingSubmission).filter(SamplingSubmission.project_id == project.id).all()
    inspections = (
        db.query(SamplingInspection)
        .join(SamplingSubmission)
        .filter(SamplingSubmission.project_id == project.id)
        .all()
    )
    defects = (
        db.query(SamplingDefect)
        .join(SamplingInspection)
        .join(SamplingSubmission)
        .filter(SamplingSubmission.project_id == project.id)
        .all()
    )
    # 抽检登记：不良现象=代码表「大类」；不良位置=该大类下「不良描述」
    # 下拉只取类别管理代码表，不混入历史自由文本（否则大类会变成小类/旧现象）
    locations = [d.location for d in defects]
    sections_from_code: list[str] = []
    confirmers_from_code: list[str] = []
    heads_from_code: list[str] = []
    models_from_code: list[str] = []
    series_sections: dict[str, str] = {}
    series_confirmers: dict[str, str] = {}
    section_heads: dict[str, str] = {}
    defect_categories: list[str] = []
    defect_minors_by_category: dict[str, list[str]] = {}

    frames = item.get("frames") or {}
    for name, df in frames.items():
        if df is None or getattr(df, "empty", True):
            continue
        sheet = str(name or "")
        is_code_sheet = sheet.strip() == "代码" or (
            "代码" in sheet
            and (
                "不良描述" in (df.columns if df is not None else [])
                or "课室" in (df.columns if df is not None else [])
            )
        )
        if not is_code_sheet:
            continue
        from .code_table_oqc import (
            build_oqc_lookups,
            defect_category_options,
            list_defects,
        )

        lookups = build_oqc_lookups(df)
        series_sections = {**series_sections, **(lookups.get("series_sections") or {})}
        series_confirmers = {**series_confirmers, **(lookups.get("series_confirmers") or {})}
        section_heads = {**section_heads, **(lookups.get("section_heads") or {})}
        sections_from_code.extend((lookups.get("series_sections") or {}).values())
        sections_from_code.extend((lookups.get("section_heads") or {}).keys())
        confirmers_from_code.extend((lookups.get("series_confirmers") or {}).values())
        heads_from_code.extend((lookups.get("section_heads") or {}).values())
        models_from_code.extend((lookups.get("series_sections") or {}).keys())
        models_from_code.extend((lookups.get("series_confirmers") or {}).keys())
        defect_categories.extend(defect_category_options(df))
        for item_d in list_defects(df):
            cat = _text(item_d.get("category"))
            desc = _text(item_d.get("desc"))
            if not cat:
                continue
            if cat not in defect_categories:
                defect_categories.append(cat)
            if not desc:
                continue
            bucket = defect_minors_by_category.setdefault(cat, [])
            if desc not in bucket:
                bucket.append(desc)
            locations.append(desc)

    locations = [part for value in locations for part in _split_parts(value)]

    from .models import Department, ModelBusinessUnit

    departments = [d.name for d in db.query(Department).filter(Department.active.is_(True)).all()]
    model_bu_rows = db.query(ModelBusinessUnit).order_by(ModelBusinessUnit.model).all()
    part_numbers = [m.model for m in model_bu_rows]
    bu_from_map = [m.business_unit for m in model_bu_rows]
    # 历史 OQC 宽表里的送检类型，合并进标准枚举
    types_from_history: list[str] = []
    for name, df in frames.items():
        if df is None or getattr(df, "empty", True):
            continue
        sheet = str(name or "")
        if ("OQC" in sheet or "抽检批次" in sheet) and "送检类型" in df.columns:
            types_from_history.extend(df["送检类型"].tolist())

    categories = uniq(defect_categories)
    minors_by_cat = {
        cat: uniq(defect_minors_by_category.get(cat, []))
        for cat in categories
    }

    managed_inspectors = [
        r.name
        for r in db.query(SamplingInspector)
        .filter(SamplingInspector.active.is_(True))
        .order_by(SamplingInspector.sort_order.asc(), SamplingInspector.id.asc())
        .all()
        if _text(r.name)
    ]
    history_inspectors = []
    for c in inspections:
        history_inspectors.extend(_split_parts(c.inspector))

    return {
        "部番": uniq([s.part_no for s in subs] + models_from_code + part_numbers),
        "机种": uniq([s.model for s in subs] + models_from_code + part_numbers),
        "送检单位": uniq([s.department for s in subs] + departments + sections_from_code),
        "事业部": uniq([s.business_unit for s in subs] + bu_from_map),
        "送检类型": uniq(list(SUBMIT_TYPE_OPTIONS) + types_from_history),
        "检验员": managed_inspectors or uniq(history_inspectors),
        "不良位置": uniq(
            [m for minors in minors_by_cat.values() for m in minors] + locations
        ),
        "现象": categories,
        "不良现象大类": categories,
        "不良属性": ["外观不良", "性能不良"],
        "确认者": uniq([s.confirmer for s in subs] + confirmers_from_code),
        "课室负责人": uniq([s.room_owner for s in subs] + heads_from_code),
        "lookups": {
            "series_sections": series_sections,
            "series_confirmers": series_confirmers,
            "section_heads": section_heads,
            "part_numbers": uniq(part_numbers),
            "submit_types": list(SUBMIT_TYPE_OPTIONS),
            "defect_categories": categories,
            "defect_minors_by_category": minors_by_cat,
            "inspectors": managed_inspectors,
        },
    }


# ── 送检单 ──────────────────────────────────────────────────────────────


def _next_code(db: Session, day: date) -> str:
    prefix = "SJ" + day.strftime("%Y%m%d")
    pattern = re.compile(rf"^{prefix}-(\d+)$")
    codes = (
        db.query(SamplingSubmission.code)
        .filter(SamplingSubmission.code.like(f"{prefix}-%"))
        .all()
    )
    max_seq = 0
    for (code,) in codes:
        m = pattern.match(code or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{prefix}-{max_seq + 1:03d}"


def _next_inspection_code(db: Session, sub_code: str) -> str:
    prefix = f"{sub_code}-C"
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    codes = db.query(SamplingInspection.code).filter(SamplingInspection.code.like(f"{prefix}%")).all()
    max_seq = 0
    for (code,) in codes:
        m = pattern.match(code or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{prefix}{max_seq + 1:02d}"


def create_submission(wid, item, payload, user_id, db, user_label: str = "", dept: str = "") -> dict[str, Any]:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    day = (
        _datetime(payload.get("送检日期"))
        or _datetime(payload.get("日期"))
        or _now().replace(second=0, microsecond=0)
    )
    part_no = _text(payload.get("部番")) or _text(payload.get("机种"))
    if not part_no:
        raise ValueError("请填写部番")
    model = part_no.split("-", 1)[0]
    qty = _int(payload.get("送检数量"))
    if qty is None:
        raise ValueError("请填写送检数量")

    department = dept or _text(payload.get("送检单位"))
    batch_seq = _int(payload.get("同批送检次数"))
    if batch_seq is None:
        batch_seq = _next_batch_seq(db, project.id, part_no, day)
    record = SamplingSubmission(
        project_id=project.id,
        code=_next_code(db, day),
        submit_date=day,
        month_label=_month_label(day),
        part_no=part_no,
        model=model,
        series=_text(payload.get("系列")) or model,
        department=department,
        business_unit=_text(payload.get("事业部")) or resolve_business_unit(db, part_no),
        submit_type=_text(payload.get("送检类型")) or "正常送检",
        qty=qty,
        batch_seq=batch_seq,
        urgent=_text(payload.get("是否紧急出货")),
        remark=_text(payload.get("层别备注")),
        confirmer=_text(payload.get("确认者")),
        room_owner=_text(payload.get("课室负责人")),
        version=1,
        created_by=user_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(record)
    db.flush()
    _audit(db, user_id, "sampling_submission", record.code, "create", {"code": record.code})
    db.commit()
    log(f"[sampling.create_submission] {record.code}")
    return _submission_dict(record)


def _get_submission(db: Session, project: Project, sid: str) -> SamplingSubmission:
    record = (
        db.query(SamplingSubmission)
        .filter(SamplingSubmission.project_id == project.id, SamplingSubmission.code == sid)
        .first()
    )
    if record is None or record.deleted_at is not None:
        raise ValueError("送检单不存在")
    return record


def update_submission(wid, item, sid, payload, user_id, db, user_label: str = "", dept: str = "",
                      expected_version: int | None = None) -> dict[str, Any]:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    record = _get_submission(db, project, sid)
    if dept and _text(record.department) != dept:
        raise ValueError("只能修改本课室的送检单")
    if expected_version is not None and int(expected_version) != int(record.version or 1):
        raise VersionConflict("这张送检单已被其他人修改，请刷新后再试")

    day = (
        _datetime(payload.get("送检日期"))
        or _datetime(payload.get("日期"))
        or record.submit_date
    )
    part_no = _text(payload.get("部番")) or _text(payload.get("机种")) or _text(record.part_no)
    if not part_no:
        raise ValueError("请填写部番")
    model = part_no.split("-", 1)[0]
    day_changed = _iso(day)[:10] != _iso(record.submit_date)[:10]
    part_changed = part_no != _text(record.part_no)
    record.submit_date = day
    record.month_label = _month_label(day)
    record.part_no = part_no
    record.model = model
    record.series = _text(payload.get("系列")) or model
    record.department = dept or _text(payload.get("送检单位"))
    perms_bu = _text(payload.get("事业部"))
    if perms_bu:
        record.business_unit = perms_bu
    elif not _text(record.business_unit) or part_changed:
        record.business_unit = resolve_business_unit(db, part_no)
    record.submit_type = _text(payload.get("送检类型")) or record.submit_type or "正常送检"
    record.qty = _int(payload.get("送检数量"))
    batch_seq = _int(payload.get("同批送检次数"))
    if day_changed or part_changed:
        batch_seq = _next_batch_seq(db, project.id, part_no, day, exclude_id=record.id)
    elif batch_seq is None:
        batch_seq = record.batch_seq
    record.batch_seq = batch_seq
    record.urgent = _text(payload.get("是否紧急出货"))
    record.remark = _text(payload.get("层别备注"))
    record.confirmer = _text(payload.get("确认者"))
    record.room_owner = _text(payload.get("课室负责人"))
    record.version = int(record.version or 1) + 1
    record.updated_at = _now()
    _audit(db, user_id, "sampling_submission", record.code, "update", payload)
    db.commit()
    _sync_oqc(db, item, project, record)
    return _submission_dict(record)


def delete_submission(wid, item, sid, user_id, db, dept: str = "") -> None:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    record = _get_submission(db, project, sid)
    if dept and _text(record.department) != dept:
        raise ValueError("只能删除本课室的送检单")
    record.deleted_at = _now()
    _audit(db, user_id, "sampling_submission", record.code, "delete", {"code": record.code})
    db.commit()
    _delete_oqc_rows(db, project, record.code)
    log(f"[sampling.delete_submission] {sid}")


# ── 抽检记录 ────────────────────────────────────────────────────────────


def _apply_inspection(defects: list[dict[str, Any]]) -> tuple[list[SamplingDefect], int, str, str, str]:
    rows: list[SamplingDefect] = []
    total = 0
    for d in defects or []:
        attr = _text(d.get("不良属性"))
        loc = _text(d.get("不良位置"))
        phen = _text(d.get("现象"))
        qty = _int(d.get("数量"))
        if not (attr or loc or phen or qty):
            continue
        total += qty or 0
        rows.append(SamplingDefect(attr=attr, location=loc, phenomenon=phen, qty=qty))
    return rows, total


def _inspector_overlap(existing: str, incoming: str) -> str | None:
    """若两边检验员名单有交集，返回冲突姓名。"""
    left = set(_split_parts(existing))
    right = set(_split_parts(incoming))
    hit = sorted(left & right)
    return hit[0] if hit else None


def add_inspection(wid, item, sid, payload, user_id, db, user_label: str = "") -> dict[str, Any]:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    sub = _get_submission(db, project, sid)
    inspector = _text(payload.get("检验员"))
    if not inspector:
        raise ValueError("请填写检验员")
    names = _split_parts(inspector)
    if not names:
        raise ValueError("请填写检验员")
    if len(names) != len(set(names)):
        raise ValueError("同一组内检验员不能重复")
    for c in sub.inspections:
        hit = _inspector_overlap(c.inspector, inspector)
        if hit:
            raise ValueError(f"检验员「{hit}」已登记过这张送检单，请直接修改")

    defects, total = _apply_inspection(payload.get("defects") or payload.get("不良组") or [])
    appearance = _int(payload.get("外观抽检数量")) or 0
    count = len(defects)
    inspection = SamplingInspection(
        submission_id=sub.id,
        code=_next_inspection_code(db, sub.code),
        inspector=inspector,
        appearance_qty=_int(payload.get("外观抽检数量")),
        function_qty=_int(payload.get("机能抽检数量")),
        defect_qty=total if count else None,
        defect_rate=f"{total / appearance:.6f}" if (count and appearance) else "0",
        verdict=("NG" if count == 1 else f"NG×{count}") if count else "OK",
        version=1,
        created_by=user_id,
        created_at=_now(),
        updated_at=_now(),
        defects=defects,
    )
    db.add(inspection)
    db.flush()
    db.refresh(sub)
    _sync_completion(sub)
    _audit(db, user_id, "sampling_inspection", inspection.code, "create", {"inspection": inspection.code})
    db.commit()
    _sync_oqc(db, item, project, sub)
    return _inspection_dict(inspection, sub)


def update_inspection(wid, item, iid, payload, user_id, db, user_label: str = "",
                      expected_version: int | None = None) -> dict[str, Any]:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    inspection = (
        db.query(SamplingInspection)
        .join(SamplingSubmission)
        .filter(SamplingInspection.code == iid, SamplingSubmission.project_id == project.id)
        .first()
    )
    if inspection is None:
        raise ValueError("抽检记录不存在")
    if expected_version is not None and int(expected_version) != int(inspection.version or 1):
        raise VersionConflict("这条抽检记录已被其他人修改，请刷新后再试")

    inspector = _text(payload.get("检验员"))
    if not inspector:
        raise ValueError("请填写检验员")
    names = _split_parts(inspector)
    if not names:
        raise ValueError("请填写检验员")
    if len(names) != len(set(names)):
        raise ValueError("同一组内检验员不能重复")
    sub = inspection.submission
    for c in sub.inspections:
        if c.id == inspection.id:
            continue
        hit = _inspector_overlap(c.inspector, inspector)
        if hit:
            raise ValueError(f"检验员「{hit}」已登记过这张送检单")

    defects, total = _apply_inspection(payload.get("defects") or payload.get("不良组") or [])
    appearance = _int(payload.get("外观抽检数量")) or 0
    count = len(defects)
    inspection.inspector = inspector
    inspection.appearance_qty = _int(payload.get("外观抽检数量"))
    inspection.function_qty = _int(payload.get("机能抽检数量"))
    inspection.defect_qty = total if count else None
    inspection.defect_rate = f"{total / appearance:.6f}" if (count and appearance) else "0"
    inspection.verdict = ("NG" if count == 1 else f"NG×{count}") if count else "OK"
    inspection.version = int(inspection.version or 1) + 1
    inspection.updated_at = _now()
    inspection.defects = defects
    db.flush()
    db.refresh(sub)
    _sync_completion(sub)
    _audit(db, user_id, "sampling_inspection", inspection.code, "update", {"inspection": inspection.code})
    db.commit()
    _sync_oqc(db, item, project, sub)
    return _inspection_dict(inspection, sub)


def delete_inspection(wid, item, iid, user_id, db) -> None:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    inspection = (
        db.query(SamplingInspection)
        .join(SamplingSubmission)
        .filter(SamplingInspection.code == iid, SamplingSubmission.project_id == project.id)
        .first()
    )
    if inspection is None:
        raise ValueError("抽检记录不存在")
    sub = inspection.submission
    db.query(SamplingException).filter(SamplingException.inspection_id == inspection.id).delete()
    db.query(SamplingDefect).filter(SamplingDefect.inspection_id == inspection.id).delete()
    db.delete(inspection)
    db.flush()
    db.refresh(sub)
    _sync_completion(sub)
    _audit(db, user_id, "sampling_inspection", iid, "delete", {"inspection": iid})
    db.commit()
    _sync_oqc(db, item, project, sub)
    log(f"[sampling.delete_inspection] {iid}")


# ── 异常处理 ────────────────────────────────────────────────────────────


def upsert_exception(wid, item, iid, payload, user_id, db, user_label: str = "") -> dict[str, Any]:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    inspection = (
        db.query(SamplingInspection)
        .join(SamplingSubmission)
        .filter(SamplingInspection.code == iid, SamplingSubmission.project_id == project.id)
        .first()
    )
    if inspection is None:
        raise ValueError("抽检记录不存在")

    close_date = _date(payload.get("结案日期"))
    start = inspection.submission.submit_date
    if isinstance(start, datetime):
        start = start.date()
    close_days = (close_date - start).days if (close_date and start) else None

    record = inspection.exception
    if record is None:
        record = SamplingException(inspection_id=inspection.id, created_by=user_id, created_at=_now())
        db.add(record)
    record.oa_no = _text(payload.get("OA单号"))
    record.qc_company = _text(payload.get("指定质控公司"))
    record.owner_dept = _text(payload.get("责任单位"))
    record.owner = _text(payload.get("责任人"))
    record.temp_action = _text(payload.get("临时对策"))
    record.root_cause = _text(payload.get("根因分析"))
    record.perm_action = _text(payload.get("永久对策"))
    record.verify = _text(payload.get("改善后确认"))
    record.close_date = close_date
    record.close_days = max(0, close_days) if close_days is not None else None
    record.confirmer = _text(payload.get("确认者"))
    record.room_owner = _text(payload.get("课室负责人"))
    record.dept_head = _text(payload.get("责任课级负责人"))
    record.quality_engineer = _text(payload.get("品质工程师"))
    record.updated_at = _now()
    _audit(db, user_id, "sampling_exception", iid, "upsert", {"inspection": iid})
    db.commit()
    _sync_oqc(db, item, project, inspection.submission)
    return _exception_dict(record)


def delete_exception(wid, item, iid, user_id, db) -> None:
    project = _project(db, wid)
    if project is None:
        raise ValueError("项目不存在")
    inspection = (
        db.query(SamplingInspection)
        .join(SamplingSubmission)
        .filter(SamplingInspection.code == iid, SamplingSubmission.project_id == project.id)
        .first()
    )
    if inspection is None or inspection.exception is None:
        raise ValueError("异常记录不存在")
    sub = inspection.submission
    db.delete(inspection.exception)
    _audit(db, user_id, "sampling_exception", iid, "delete", {"inspection": iid})
    db.commit()
    _sync_oqc(db, item, project, sub)


# ── OQC 宽表（定向同步，不再整表重写）──────────────────────────────────


def _oqc_sheet(item: dict[str, Any]) -> dict[str, Any] | None:
    for sheet in item["spec"].get("sheets") or []:
        name = sheet.get("name") or ""
        if "OQC" in name or "抽检批次" in name:
            return sheet
    return None


def _delete_oqc_rows(db: Session, project: Project, sid: str) -> None:
    sheet = None
    for s in db.query(SheetData.sheet_name).filter(SheetData.project_id == project.id).distinct():
        if "OQC" in (s[0] or "") or "抽检批次" in (s[0] or ""):
            sheet = s[0]
            break
    if not sheet:
        return
    db.execute(
        text(
            "DELETE FROM sheet_data WHERE project_id = :pid AND sheet_name = :sn "
            "AND JSON_UNQUOTE(JSON_EXTRACT(row_data, '$.\"送检单号\"')) = :sid"
        ),
        {"pid": project.id, "sn": sheet, "sid": sid},
    )
    db.commit()


def _sync_oqc(db: Session, item: dict[str, Any], project: Project, sub: SamplingSubmission) -> None:
    """按送检单同步 OQC 宽表：删除旧行，插入重算后的行。"""
    sheet = _oqc_sheet(item)
    if sheet is None:
        return
    db.flush()
    _delete_oqc_rows(db, project, sub.code)

    inspections = sorted(sub.inspections, key=lambda c: c.code)
    if not inspections:
        db.commit()
        return

    batch_failed = any(c.defects for c in inspections)
    frames = item.get("frames") or {}
    for index, insp in enumerate(inspections):
        values = {
            "日期": sub.submit_date.strftime("%Y-%m-%d") if isinstance(sub.submit_date, datetime) else sub.submit_date,
            "月份": sub.month_label,
            "送检类型": _text(sub.submit_type) or "正常送检",
            "机种": sub.part_no or sub.model,
            "送检数量": sub.qty,
            "外观抽检数量": insp.appearance_qty,
            "机能抽检数量": insp.function_qty,
            "同批送检次数": sub.batch_seq,
            "是否紧急出货": sub.urgent,
            "层别备注": sub.remark,
            "确认者": sub.confirmer,
            "课室负责人": sub.room_owner,
            OQC_LINK_SUB: sub.code,
            OQC_LINK_INSP: insp.code,
        }
        try:
            row = fill_row(item["spec"], sheet, frames, values, assign_id=False)
        except Exception as exc:  # noqa: BLE001
            log(f"[sampling.sync_oqc] fill_row failed: {exc}")
            continue

        defects = insp.defects or []
        if defects:
            row["不良位置"] = DEFECT_SEP.join(d.location or "" for d in defects)
            row["现象"] = DEFECT_SEP.join(d.phenomenon or "" for d in defects)
            row["数量"] = DEFECT_SEP.join(str(d.qty or "") for d in defects)
            row["不良属性"] = DEFECT_SEP.join(d.attr or "" for d in defects)
        else:
            for key in ("不良位置", "现象", "数量", "不良属性"):
                row[key] = None
        row["检验员"] = insp.inspector
        row["不良数量"] = insp.defect_qty
        row["不良率"] = _pct(insp.defect_rate)
        row[SENT_FIELD] = 1 if index == 0 else 0
        row[PASS_FIELD] = 1 if (index == 0 and not batch_failed) else 0
        row["合格批率"] = 1 if row[PASS_FIELD] else 0
        row["判定"] = insp.verdict or "OK"

        exception = insp.exception
        if exception is not None:
            row["OA单号"] = exception.oa_no
            row["指定质控公司"] = exception.qc_company
            row["责任单位"] = exception.owner_dept
            row["责任人"] = exception.owner
            row["临时对策"] = exception.temp_action
            row["根因分析"] = exception.root_cause
            row["永久对策"] = exception.perm_action
            row["改善后确认"] = exception.verify
            row["结案日期"] = _iso(exception.close_date) if exception.close_date else None
            row["结案天数"] = exception.close_days
            row["确认者"] = exception.confirmer or row.get("确认者")
            row["课室负责人"] = exception.room_owner or row.get("课室负责人")
            row["责任课级负责人"] = exception.dept_head
            row["品质工程师"] = exception.quality_engineer

        payload = {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in row.items() if not str(k).startswith("__")}
        db.add(
            SheetData(
                project_id=project.id,
                sheet_name=sheet["name"],
                row_data=payload,
                source="entered",
                created_by=None,
                created_at=_now(),
            )
        )

    db.commit()
