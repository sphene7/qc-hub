"""抽检三级登记：送检 → 抽检（检验员）→ 异常处理。

字段按 Excel「抽检」段切分：
* 送检登记：日期 … 送检数量（外部/产线填）。
* 抽检登记：外观抽检数量 … 检验员（检验员填，含不良明细）。
* 异常登记：剩下的闭环字段（OA 单号、责任、对策、结案）。

保存任一层都会重算该送检单的抽检汇总，并回写 OQC 宽表（一行 = 一个检验员），
宽表里 `抽检批` 只记首行、`合格批` 只在整批合格时记 1，合格率分母不会翻倍。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from .entry import fill_row
from .logutil import log
from .models import Project
from .store import update_sheet_data

SUB_SHEET = "送检登记"
INSP_SHEET = "抽检登记"
DEF_SHEET = "异常登记"

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

# 回写宽表时保留旧行上的闭环字段（OA补录 / 闭环分析 维护的）
OQC_PRESERVE_FIELDS = CLAUSE_FIELDS + ("责任课级负责人", "品质工程师")


def _col(key: str, label: str, role: str, type_: str = "string") -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "role": role,
        "type": type_,
        "index": 0,
        "fill": 1.0,
        "unique": 0,
        "samples": [],
        "semantic": None,
        "formula_cells": 0,
    }


SUB_COLUMNS = [
    _col("送检单号", "送检单号", "id"),
    _col("日期", "日期", "date", "date"),
    _col("月份", "月份", "dimension"),
    _col("送检类型", "送检类型", "dimension"),
    _col("机种", "机种", "dimension"),
    _col("系列", "系列", "dimension"),
    _col("送检单位", "送检单位", "dimension"),
    _col("送检数量", "送检数量", "measure", "number"),
    _col("同批送检次数", "同批送检次数", "measure", "number"),
    _col("是否紧急出货", "是否紧急出货", "dimension"),
    _col("层别备注", "层别备注", "text"),
    _col("确认者", "确认者", "dimension"),
    _col("课室负责人", "课室负责人", "dimension"),
    _col("登记人", "登记人", "dimension"),
    _col("登记时间", "登记时间", "dimension"),
]

INSP_COLUMNS = [
    _col("抽检单号", "抽检单号", "id"),
    _col("送检单号", "送检单号", "dimension"),
    _col("外观抽检数量", "外观抽检数量", "measure", "number"),
    _col("机能抽检数量", "机能抽检数量", "measure", "number"),
    _col("不良数量", "不良数量", "measure", "number"),
    _col("不良率", "不良率", "measure", "number"),
    _col("抽检批", "抽检批", "measure", "number"),
    _col("合格批", "合格批", "measure", "number"),
    _col("合格批率", "合格批率", "measure", "number"),
    _col("判定", "判定", "dimension"),
    _col("不良属性", "不良属性", "dimension"),
    _col("不良位置", "不良位置", "dimension"),
    _col("现象", "现象", "dimension"),
    _col("数量", "数量", "measure", "number"),
    _col("检验员", "检验员", "dimension"),
    _col("登记人", "登记人", "dimension"),
    _col("登记时间", "登记时间", "dimension"),
]

DEF_COLUMNS = [
    _col("异常单号", "异常单号", "id"),
    _col("抽检单号", "抽检单号", "dimension"),
    _col("送检单号", "送检单号", "dimension"),
    _col("OA单号", "OA单号", "text"),
    _col("指定质控公司", "指定质控公司", "dimension"),
    _col("责任单位", "责任单位", "dimension"),
    _col("责任人", "责任人", "dimension"),
    _col("临时对策", "临时对策", "text"),
    _col("根因分析", "根因分析", "text"),
    _col("永久对策", "永久对策", "text"),
    _col("改善后确认", "改善后确认", "text"),
    _col("结案日期", "结案日期", "date", "date"),
    _col("结案天数", "结案天数", "measure", "number"),
    _col("登记人", "登记人", "dimension"),
    _col("登记时间", "登记时间", "dimension"),
]

SHEET_COLUMNS = {
    SUB_SHEET: SUB_COLUMNS,
    INSP_SHEET: INSP_COLUMNS,
    DEF_SHEET: DEF_COLUMNS,
}


def _new_sheet_spec(name: str) -> dict[str, Any]:
    columns = [dict(c) for c in SHEET_COLUMNS[name]]
    for i, col in enumerate(columns):
        col["index"] = i + 1
    return {
        "name": name,
        "kind": "fact",
        "derived": False,
        "empty": False,
        "primary": False,
        "note": None,
        "header_row": 1,
        "col_count": len(columns),
        "row_count": 0,
        "columns": columns,
        "joins": [],
        "kpis": [],
        "charts": [],
        "filters": [],
        "preview": [],
        "form": {"enabled": True, "fields": [], "computed": []},
        "formula": {"columns": []},
    }


# ── 基础设施 ────────────────────────────────────────────────────────────


def find_oqc_sheet(spec: dict[str, Any]) -> dict[str, Any] | None:
    for sheet in spec.get("sheets") or []:
        name = sheet.get("name") or ""
        if "OQC" in name or "抽检批次" in name:
            return sheet
    return None


def ensure_sheets(item: dict[str, Any], wid: str, db: Session) -> bool:
    """补齐三张登记表 / 迁移列结构 / OQC 关联列。"""
    spec = item["spec"]
    sheets = spec.setdefault("sheets", [])
    names = {s.get("name") for s in sheets}
    changed = False

    for name in (SUB_SHEET, INSP_SHEET, DEF_SHEET):
        wanted = SHEET_COLUMNS[name]
        if name not in names:
            sheets.append(_new_sheet_spec(name))
            item["frames"][name] = pd.DataFrame()
            changed = True
            continue
        sheet = next(s for s in sheets if s.get("name") == name)
        current_keys = [c.get("key") for c in sheet.get("columns") or []]
        wanted_keys = {c["key"] for c in wanted}
        obsolete = [k for k in current_keys if k not in wanted_keys]
        if obsolete:
            sheet["columns"] = [c for c in sheet.get("columns") or [] if c.get("key") not in obsolete]
            sheet["col_count"] = len(sheet["columns"])
            df_old = item["frames"].get(name)
            if df_old is not None and not df_old.empty:
                drop = [k for k in obsolete if k in df_old.columns]
                if drop:
                    item["frames"][name] = df_old.drop(columns=drop)
            current_keys = [c.get("key") for c in sheet.get("columns")]
            changed = True
        if [c["key"] for c in wanted] != current_keys:
            has_rows = bool(item["frames"].get(name) is not None and not item["frames"][name].empty)
            if not has_rows:
                # 空表直接换成新结构（含字段顺序调整）
                sheet["columns"] = [dict(c) for c in wanted]
                sheet["col_count"] = len(wanted)
                changed = True
            else:
                for col in wanted:
                    if col["key"] not in current_keys:
                        sheet.setdefault("columns", []).append(dict(col))
                        changed = True

    oqc = find_oqc_sheet(spec)
    if oqc is not None:
        keys = {c.get("key") for c in oqc.get("columns") or []}
        for key in (OQC_LINK_SUB, OQC_LINK_INSP):
            if key not in keys:
                oqc.setdefault("columns", []).append(_col(key, key, "dimension"))
                changed = True

    if changed:
        project = db.query(Project).filter(Project.project_id == wid).first()
        if project:
            project.spec = spec
            db.commit()
        log(f"[sampling.ensure_sheets] wid={wid} schema updated")

    for name in (SUB_SHEET, INSP_SHEET, DEF_SHEET):
        df = item["frames"].get(name)
        if df is None:
            item["frames"][name] = pd.DataFrame()
        elif "__source" not in df.columns:
            df = df.copy()
            df["__source"] = "imported"
            item["frames"][name] = df

    return changed


def _df(item: dict[str, Any], name: str) -> pd.DataFrame:
    df = item["frames"].get(name)
    return df if df is not None else pd.DataFrame()


def _clean(value: Any) -> Any:
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return value


def _records(item: dict[str, Any], name: str) -> list[dict[str, Any]]:
    df = _df(item, name)
    if df is None or df.empty:
        return []
    return [{k: _clean(v) for k, v in row.to_dict().items()} for _, row in df.iterrows()]


def _write(wid, item, name, records, user_id, db) -> None:
    df = pd.DataFrame(records) if records else pd.DataFrame()
    if not df.empty and "__source" not in df.columns:
        df["__source"] = "entered"
    item["frames"][name] = df
    sheet = next((s for s in item["spec"]["sheets"] if s.get("name") == name), None)
    if sheet:
        sheet["row_count"] = int(len(df))
        sheet["empty"] = df.empty
    update_sheet_data(wid, name, df, user_id, db)


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_if_possible(value: float | None) -> Any:
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


def _date_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    return text if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _month_text(date_text: str) -> str:
    parsed = pd.to_datetime(date_text, errors="coerce")
    if pd.isna(parsed):
        return ""
    return f"{int(parsed.year)}年{int(parsed.month)}月"


def _next_seq(values: list[str], prefix: str) -> int:
    # 单号形如 SJ20260825-001 / SJ-20260825-001-C01，前缀与流水号之间可能有 "-"
    pattern = re.compile(rf"^{re.escape(prefix)}-?(\d+)$")
    mx = 0
    for value in values:
        m = pattern.match(_text(value))
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ── 读 ──────────────────────────────────────────────────────────────────


def _defects_of(record: dict[str, Any]) -> list[dict[str, Any]]:
    """把「；」拼接的不良字段还原成组。"""
    attrs = _text(record.get("不良属性")).split(DEFECT_SEP) if _text(record.get("不良属性")) else []
    locs = _text(record.get("不良位置")).split(DEFECT_SEP) if _text(record.get("不良位置")) else []
    phens = _text(record.get("现象")).split(DEFECT_SEP) if _text(record.get("现象")) else []
    qtys = _text(record.get("数量")).split(DEFECT_SEP) if _text(record.get("数量")) else []
    n = max(len(attrs), len(locs), len(phens), len(qtys))
    groups = []
    for i in range(n):
        groups.append(
            {
                "不良属性": attrs[i].strip() if i < len(attrs) else "",
                "不良位置": locs[i].strip() if i < len(locs) else "",
                "现象": phens[i].strip() if i < len(phens) else "",
                "数量": qtys[i].strip() if i < len(qtys) else "",
            }
        )
    return groups


def load_tree(item: dict[str, Any], dept: str = "") -> list[dict[str, Any]]:
    subs = _records(item, SUB_SHEET)
    if dept:
        subs = [s for s in subs if _text(s.get("送检单位")) == dept]
    inspections = _records(item, INSP_SHEET)
    clauses = {_text(c.get("抽检单号")): c for c in _records(item, DEF_SHEET)}

    for c in inspections:
        c["不良组"] = _defects_of(c)
        c["异常处理"] = clauses.get(_text(c.get("抽检单号")))

    by_sub: dict[str, list[dict[str, Any]]] = {}
    for c in inspections:
        by_sub.setdefault(_text(c.get("送检单号")), []).append(c)

    tree = []
    for s in subs:
        s = dict(s)
        rows = sorted(by_sub.get(_text(s.get("送检单号")), []), key=lambda c: _text(c.get("抽检单号")))
        s["抽检"] = rows
        s["异常总数"] = sum(len(c["不良组"]) for c in rows)
        tree.append(s)
    tree.sort(key=lambda x: (_text(x.get("日期")), _text(x.get("送检单号"))), reverse=True)
    return tree


def options(item: dict[str, Any]) -> dict[str, list[str]]:
    def uniq(values) -> list[str]:
        seen: list[str] = []
        for v in values:
            s = _text(v)
            if s and s not in seen:
                seen.append(s)
        return sorted(seen)

    def column(records, key):
        return uniq(r.get(key) for r in records)

    oqc = find_oqc_sheet(item["spec"])
    oqc_records = _records(item, oqc["name"]) if oqc else []
    code_records: list[dict[str, Any]] = []
    for sheet in item["spec"].get("sheets") or []:
        if (sheet.get("name") or "").strip() == "代码":
            code_records = _records(item, sheet["name"])
            break
    insp_records = _records(item, INSP_SHEET)
    phenomena = []
    locations = []
    for c in insp_records:
        for g in _defects_of(c):
            phenomena.append(g["现象"])
            locations.append(g["不良位置"])

    return {
        "机种": uniq(column(oqc_records, "机种") + column(code_records, "机种") + column(code_records, "机种_2")),
        "送检单位": uniq(column(oqc_records, "送检单位") + column(code_records, "课室") + column(code_records, "课室_2")),
        "送检类型": uniq(column(oqc_records, "送检类型") + ["正常送检", "试做送检"]),
        "检验员": uniq(column(insp_records, "检验员") + column(oqc_records, "检验员")),
        "不良位置": uniq(locations + column(oqc_records, "不良位置")),
        "现象": uniq(phenomena + column(code_records, "不良描述") + column(oqc_records, "现象")),
        "不良属性": ["外观不良", "性能不良"],
        "确认者": uniq(column(oqc_records, "确认者") + column(code_records, "负责人")),
        "课室负责人": uniq(column(oqc_records, "课室负责人") + column(code_records, "课室负责人")),
    }


# ── 汇总 / 回写宽表 ────────────────────────────────────────────────────


def _batch_of(item: dict[str, Any], sid: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    sub = next((s for s in _records(item, SUB_SHEET) if _text(s.get("送检单号")) == sid), None)
    inspections = [c for c in _records(item, INSP_SHEET) if _text(c.get("送检单号")) == sid]
    inspections.sort(key=lambda c: _text(c.get("抽检单号")))
    return sub, inspections


def _refresh_batch(wid: str, item: dict[str, Any], sid: str, user_id: int, db: Session) -> None:
    """重算该送检单下每条抽检的汇总与批次口径，并回写宽表。"""
    sub, inspections = _batch_of(item, sid)
    if sub is None:
        return

    batch_failed = any(_text(c.get("判定")).upper().startswith("NG") for c in inspections)
    for idx, c in enumerate(inspections):
        groups = _defects_of(c)
        total = 0.0
        for g in groups:
            q = _num(g["数量"])
            if q:
                total += q
        appearance = _num(c.get("外观抽检数量")) or 0.0
        c["不良数量"] = _int_if_possible(total) if groups else None
        c["不良率"] = (total / appearance) if (groups and appearance > 0) else 0.0
        if groups:
            n = len(groups)
            c["判定"] = "NG" if n == 1 else f"NG×{n}"
        else:
            c["判定"] = "OK"
        c[SENT_FIELD] = 1 if idx == 0 else 0
        c[PASS_FIELD] = 1 if (idx == 0 and not batch_failed) else 0
        c["合格批率"] = (c[PASS_FIELD] / c[SENT_FIELD]) if c[SENT_FIELD] else 0
        c["__source"] = "entered" if not _text(c.get("__source")) else c.get("__source")

    _write(wid, item, INSP_SHEET, inspections, user_id, db)
    _rebuild_oqc(wid, item, sub, inspections, user_id, db)


def _rebuild_oqc(wid, item, sub, inspections, user_id, db) -> None:
    oqc = find_oqc_sheet(item["spec"])
    if oqc is None:
        return
    sid = _text(sub.get("送检单号"))
    clauses = {_text(c.get("抽检单号")): c for c in _records(item, DEF_SHEET)}

    old = _records(item, oqc["name"])
    kept = [r for r in old if _text(r.get(OQC_LINK_SUB)) != sid]
    stale = {_text(r.get(OQC_LINK_INSP)): r for r in old if _text(r.get(OQC_LINK_SUB)) == sid}

    new_rows: list[dict[str, Any]] = []
    for idx, insp in enumerate(inspections):
        groups = _defects_of(insp)
        values = {
            "日期": sub.get("日期"),
            "月份": sub.get("月份") or _month_text(_text(sub.get("日期"))),
            "送检类型": sub.get("送检类型"),
            "机种": sub.get("机种"),
            "送检数量": sub.get("送检数量"),
            "外观抽检数量": insp.get("外观抽检数量"),
            "机能抽检数量": insp.get("机能抽检数量"),
            "同批送检次数": sub.get("同批送检次数"),
            "是否紧急出货": sub.get("是否紧急出货"),
            "层别备注": sub.get("层别备注"),
            "确认者": sub.get("确认者"),
            "课室负责人": sub.get("课室负责人"),
            OQC_LINK_SUB: sid,
            OQC_LINK_INSP: insp.get("抽检单号"),
        }
        row = fill_row(item["spec"], oqc, item["frames"], values, assign_id=False)

        if groups:
            row["不良位置"] = DEFECT_SEP.join(_text(g.get("不良位置")) for g in groups)
            row["现象"] = DEFECT_SEP.join(_text(g.get("现象")) for g in groups)
            row["数量"] = DEFECT_SEP.join(_text(g.get("数量")) for g in groups)
            row["不良属性"] = DEFECT_SEP.join(_text(g.get("不良属性")) for g in groups)
            row["检验员"] = _text(insp.get("检验员"))
        else:
            for key in ("不良位置", "现象", "数量", "不良属性"):
                row[key] = None
            row["检验员"] = _text(insp.get("检验员"))

        row["不良数量"] = insp.get("不良数量")
        row["不良率"] = insp.get("不良率")
        row[SENT_FIELD] = insp.get(SENT_FIELD)
        row[PASS_FIELD] = insp.get(PASS_FIELD)
        row["合格批率"] = insp.get("合格批率")
        row["判定"] = insp.get("判定")

        clause = clauses.get(_text(insp.get("抽检单号"))) or {}
        for key in CLAUSE_FIELDS:
            if clause.get(key) not in (None, ""):
                row[key] = clause.get(key)

        prev = stale.get(_text(insp.get("抽检单号")))
        if prev:
            for key in OQC_PRESERVE_FIELDS:
                if prev.get(key) not in (None, "") and row.get(key) in (None, ""):
                    row[key] = prev.get(key)
        row["__source"] = "entered"
        new_rows.append(row)

    _write(wid, item, oqc["name"], kept + new_rows, user_id, db)


# ── 送检登记 ────────────────────────────────────────────────────────────


def create_submission(wid, item, payload, user_id, db, user_label: str = "", dept: str = "") -> dict[str, Any]:
    ensure_sheets(item, wid, db)
    subs = _records(item, SUB_SHEET)
    existing = [_text(s.get("送检单号")) for s in subs]
    day = _date_text(payload.get("日期")) or date.today().strftime("%Y-%m-%d")
    base = "SJ" + day.replace("-", "")
    seq = _next_seq([v for v in existing if v.startswith(base)], base)
    sid = f"{base}-{seq:03d}"

    record = {
        "送检单号": sid,
        "日期": day,
        "月份": _month_text(day),
        "送检类型": _text(payload.get("送检类型")),
        "机种": _text(payload.get("机种")),
        "系列": _text(payload.get("系列")) or _text(payload.get("机种")).split("-")[0],
        "送检单位": _text(payload.get("送检单位")),
        "送检数量": _int_if_possible(_num(payload.get("送检数量"))),
        "同批送检次数": _int_if_possible(_num(payload.get("同批送检次数"))),
        "是否紧急出货": _text(payload.get("是否紧急出货")),
        "层别备注": _text(payload.get("层别备注")),
        "确认者": _text(payload.get("确认者")),
        "课室负责人": _text(payload.get("课室负责人")),
        "登记人": user_label,
        "登记时间": _now_text(),
        "__source": "entered",
    }
    if not record["机种"]:
        raise ValueError("请填写机种")
    if _num(payload.get("送检数量")) is None:
        raise ValueError("请填写送检数量")
    if user_label and dept:
        record["送检单位"] = dept

    _fill_lookups(item, record)
    subs.append(record)
    _write(wid, item, SUB_SHEET, subs, user_id, db)
    log(f"[sampling.create_submission] wid={wid} sid={sid}")
    return record


def _fill_lookups(item: dict[str, Any], record: dict[str, Any]) -> None:
    oqc = find_oqc_sheet(item["spec"])
    if oqc is None:
        return
    try:
        filled = fill_row(
            item["spec"], oqc, item["frames"], {"机种": record.get("机种")}, assign_id=False
        )
    except Exception:  # noqa: BLE001
        return
    for key in ("系列", "送检单位", "确认者", "课室负责人"):
        if not _text(record.get(key)) and filled.get(key) not in (None, ""):
            record[key] = filled.get(key)


def update_submission(wid, item, sid, payload, user_id, db, user_label: str = "", dept: str = "") -> dict[str, Any]:
    ensure_sheets(item, wid, db)
    subs = _records(item, SUB_SHEET)
    record = next((s for s in subs if _text(s.get("送检单号")) == sid), None)
    if record is None:
        raise ValueError("送检单不存在")
    if dept and _text(record.get("送检单位")) != dept:
        raise ValueError("只能修改本课室的送检单")

    day = _date_text(payload.get("日期")) or record.get("日期")
    record.update(
        {
            "日期": day,
            "月份": _month_text(_text(day)),
                "送检类型": _text(payload.get("送检类型")),
            "机种": _text(payload.get("机种")),
            "系列": _text(payload.get("系列")),
            "送检单位": _text(payload.get("送检单位")),
            "送检数量": _int_if_possible(_num(payload.get("送检数量"))),
            "同批送检次数": _int_if_possible(_num(payload.get("同批送检次数"))),
            "是否紧急出货": _text(payload.get("是否紧急出货")),
            "层别备注": _text(payload.get("层别备注")),
            "确认者": _text(payload.get("确认者")),
            "课室负责人": _text(payload.get("课室负责人")),
        }
    )
    if not record["机种"]:
        raise ValueError("请填写机种")
    if dept:
        record["送检单位"] = dept
    _fill_lookups(item, record)
    _write(wid, item, SUB_SHEET, subs, user_id, db)
    _, inspections = _batch_of(item, sid)
    _rebuild_oqc(wid, item, record, inspections, user_id, db)
    return record


def delete_submission(wid, item, sid, user_id, db, dept: str = "") -> None:
    ensure_sheets(item, wid, db)
    target = next((s for s in _records(item, SUB_SHEET) if _text(s.get("送检单号")) == sid), None)
    if target is None:
        raise ValueError("送检单不存在")
    if dept and _text(target.get("送检单位")) != dept:
        raise ValueError("只能删除本课室的送检单")
    subs = [s for s in _records(item, SUB_SHEET) if _text(s.get("送检单号")) != sid]
    doomed = {_text(c.get("抽检单号")) for c in _records(item, INSP_SHEET) if _text(c.get("送检单号")) == sid}
    inspections = [c for c in _records(item, INSP_SHEET) if _text(c.get("送检单号")) != sid]
    defs = [d for d in _records(item, DEF_SHEET) if _text(d.get("抽检单号")) not in doomed]
    _write(wid, item, SUB_SHEET, subs, user_id, db)
    _write(wid, item, INSP_SHEET, inspections, user_id, db)
    _write(wid, item, DEF_SHEET, defs, user_id, db)
    oqc = find_oqc_sheet(item["spec"])
    if oqc is not None:
        kept = [r for r in _records(item, oqc["name"]) if _text(r.get(OQC_LINK_SUB)) != sid]
        _write(wid, item, oqc["name"], kept, user_id, db)
    log(f"[sampling.delete_submission] wid={wid} sid={sid}")


# ── 抽检登记 ────────────────────────────────────────────────────────────


def _defect_fields(defects: list[dict[str, Any]]) -> dict[str, Any]:
    filled = []
    for d in defects or []:
        loc = _text(d.get("不良位置"))
        phen = _text(d.get("现象"))
        attr = _text(d.get("不良属性"))
        qty = _num(d.get("数量"))
        if not (loc or phen or attr or qty):
            continue
        filled.append({"不良属性": attr, "不良位置": loc, "现象": phen, "数量": _int_if_possible(qty)})
    if not filled:
        return {"不良属性": None, "不良位置": None, "现象": None, "数量": None}
    return {
        "不良属性": DEFECT_SEP.join(g["不良属性"] for g in filled),
        "不良位置": DEFECT_SEP.join(g["不良位置"] for g in filled),
        "现象": DEFECT_SEP.join(g["现象"] for g in filled),
        "数量": DEFECT_SEP.join(_text(g["数量"]) for g in filled),
    }


def _inspection_record(iid, sid, payload, user_label) -> dict[str, Any]:
    inspector = _text(payload.get("检验员"))
    if not inspector:
        raise ValueError("请填写检验员")
    groups = payload.get("defects") or payload.get("不良组") or []
    fields = _defect_fields(groups)
    total = 0.0
    for d in groups or []:
        q = _num(d.get("数量"))
        if q:
            total += q
    appearance = _num(payload.get("外观抽检数量")) or 0.0
    count = len([g for g in groups or [] if _text(g.get("不良位置")) or _text(g.get("现象")) or _num(g.get("数量"))])
    return {
        "抽检单号": iid,
        "送检单号": sid,
        "外观抽检数量": _int_if_possible(_num(payload.get("外观抽检数量"))),
        "机能抽检数量": _int_if_possible(_num(payload.get("机能抽检数量"))),
        "不良数量": _int_if_possible(total) if count else None,
        "不良率": (total / appearance) if (count and appearance > 0) else 0.0,
        "抽检批": 0,
        "合格批": 0,
        "合格批率": 0.0,
        "判定": ("NG" if count == 1 else f"NG×{count}") if count else "OK",
        "不良属性": fields["不良属性"],
        "不良位置": fields["不良位置"],
        "现象": fields["现象"],
        "数量": fields["数量"],
        "检验员": inspector,
        "登记人": user_label,
        "登记时间": _now_text(),
        "__source": "entered",
    }


def add_inspection(wid, item, sid, payload, user_id, db, user_label: str = "") -> dict[str, Any]:
    ensure_sheets(item, wid, db)
    subs = _records(item, SUB_SHEET)
    if not any(_text(s.get("送检单号")) == sid for s in subs):
        raise ValueError("送检单不存在")

    inspections = _records(item, INSP_SHEET)
    mine = [c for c in inspections if _text(c.get("送检单号")) == sid]
    inspector = _text(payload.get("检验员"))
    if any(_text(c.get("检验员")) == inspector for c in mine):
        raise ValueError(f"检验员「{inspector}」已登记过这张送检单，请直接修改")

    seq = _next_seq([_text(c.get("抽检单号")) for c in mine], f"{sid}-C")
    iid = f"{sid}-C{seq:02d}"
    record = _inspection_record(iid, sid, payload, user_label)
    inspections.append(record)
    _write(wid, item, INSP_SHEET, inspections, user_id, db)
    _refresh_batch(wid, item, sid, user_id, db)
    log(f"[sampling.add_inspection] wid={wid} iid={iid}")
    return record


def update_inspection(wid, item, iid, payload, user_id, db, user_label: str = "") -> dict[str, Any]:
    ensure_sheets(item, wid, db)
    inspections = _records(item, INSP_SHEET)
    record = next((c for c in inspections if _text(c.get("抽检单号")) == iid), None)
    if record is None:
        raise ValueError("抽检记录不存在")

    inspector = _text(payload.get("检验员"))
    if not inspector:
        raise ValueError("请填写检验员")
    sid = _text(record.get("送检单号"))
    if any(
        _text(c.get("送检单号")) == sid
        and _text(c.get("检验员")) == inspector
        and _text(c.get("抽检单号")) != iid
        for c in inspections
    ):
        raise ValueError(f"检验员「{inspector}」已登记过这张送检单")

    updated = _inspection_record(iid, sid, payload, _text(record.get("登记人")) or user_label)
    updated["登记时间"] = record.get("登记时间") or _now_text()
    record.update(updated)
    _write(wid, item, INSP_SHEET, inspections, user_id, db)
    _refresh_batch(wid, item, sid, user_id, db)
    return record


def delete_inspection(wid, item, iid, user_id, db) -> None:
    ensure_sheets(item, wid, db)
    inspections = _records(item, INSP_SHEET)
    target = next((c for c in inspections if _text(c.get("抽检单号")) == iid), None)
    if target is None:
        raise ValueError("抽检记录不存在")
    sid = _text(target.get("送检单号"))
    kept = [c for c in inspections if _text(c.get("抽检单号")) != iid]
    _write(wid, item, INSP_SHEET, kept, user_id, db)
    _write(wid, item, DEF_SHEET, [d for d in _records(item, DEF_SHEET) if _text(d.get("抽检单号")) != iid], user_id, db)
    _refresh_batch(wid, item, sid, user_id, db)
    log(f"[sampling.delete_inspection] wid={wid} iid={iid}")


# ── 异常登记（剩下的闭环字段）────────────────────────────────────────────


def _close_days(start_day: str, close_day: str) -> Any:
    start = pd.to_datetime(start_day or "", errors="coerce")
    end = pd.to_datetime(close_day or "", errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return None
    return max(0, int((end - start).days))


def upsert_exception(wid, item, iid, payload, user_id, db, user_label: str = "") -> dict[str, Any]:
    ensure_sheets(item, wid, db)
    inspections = _records(item, INSP_SHEET)
    insp = next((c for c in inspections if _text(c.get("抽检单号")) == iid), None)
    if insp is None:
        raise ValueError("抽检记录不存在")
    sid = _text(insp.get("送检单号"))
    sub = next((s for s in _records(item, SUB_SHEET) if _text(s.get("送检单号")) == sid), {})

    defs = _records(item, DEF_SHEET)
    existing = next((d for d in defs if _text(d.get("抽检单号")) == iid), None)
    did = _text(existing.get("异常单号")) if existing else f"{iid}-Y01"
    record = {
        "异常单号": did,
        "抽检单号": iid,
        "送检单号": sid,
        "OA单号": _text(payload.get("OA单号")),
        "指定质控公司": _text(payload.get("指定质控公司")),
        "责任单位": _text(payload.get("责任单位")),
        "责任人": _text(payload.get("责任人")),
        "临时对策": _text(payload.get("临时对策")),
        "根因分析": _text(payload.get("根因分析")),
        "永久对策": _text(payload.get("永久对策")),
        "改善后确认": _text(payload.get("改善后确认")),
        "结案日期": _text(payload.get("结案日期")) or None,
        "结案天数": _close_days(_text(sub.get("日期")), _text(payload.get("结案日期"))),
        "登记人": existing.get("登记人") if existing else user_label,
        "登记时间": existing.get("登记时间") if existing else _now_text(),
        "__source": "entered",
    }
    if existing:
        defs = [record if d is existing else d for d in defs]
    else:
        defs.append(record)
    _write(wid, item, DEF_SHEET, defs, user_id, db)
    _, batch = _batch_of(item, sid)
    _rebuild_oqc(wid, item, sub, batch, user_id, db)
    return record


def delete_exception(wid, item, iid, user_id, db) -> None:
    ensure_sheets(item, wid, db)
    inspections = _records(item, INSP_SHEET)
    insp = next((c for c in inspections if _text(c.get("抽检单号")) == iid), None)
    if insp is None:
        raise ValueError("抽检记录不存在")
    sid = _text(insp.get("送检单号"))
    sub = next((s for s in _records(item, SUB_SHEET) if _text(s.get("送检单号")) == sid), {})
    _write(wid, item, DEF_SHEET, [d for d in _records(item, DEF_SHEET) if _text(d.get("抽检单号")) != iid], user_id, db)
    _, batch = _batch_of(item, sid)
    _rebuild_oqc(wid, item, sub, batch, user_id, db)
