"""Canonical UI blueprints for the three homepage business modules.

Excel → web conversion should follow these table layouts (巡检 / 客诉 / 抽检),
not mirror every raw workbook sheet 1:1.
"""

from __future__ import annotations

from typing import Any

MODULE_KEYS = ("inspection", "complaint", "sampling")

# ── 抽检列分层（录入 ↔ 列表必须同源）────────────────────────────────
# 已退役：登记表单 + 列表都不出现（Excel 列可仍在库中）
SAMPLING_RETIRED_COLUMNS = frozenset({
    "不良代码",
    "是否紧急出货",
    "层别备注",
    "单据类型",
    "间断送检次数",
})

# 延后录入：不在「抽检登记」表单，但在列表展示；改走 OA补录 / 闭环分析
SAMPLING_DEFERRED_FORM_COLUMNS = frozenset({
    "OA单号",
    "指定质控公司",
    "临时对策",
    "根因分析",
    "永久对策",
    "改善后确认",
    "责任单位",
    "责任人",
    "责任课级负责人",
    "品质工程师",
    "结案日期",
    "结案天数",
})

# 列表额外隐藏：手选「判定_2」只服务自动「判定」，列表只展示判定
SAMPLING_HIDDEN_DISPLAY_COLUMNS = SAMPLING_RETIRED_COLUMNS | frozenset({"判定_2"})

# Preferred main fact sheet name fragments (first match wins).
MAIN_SHEET_HINTS: dict[str, tuple[str, ...]] = {
    "inspection": ("问题清单",),
    "complaint": ("客诉跟进", "客诉"),
    "sampling": ("OQC", "抽检批次"),
}

# Curated list columns — aligned with existing homepage dashboards.
DISPLAY_COLUMNS: dict[str, list[str]] = {
    "inspection": [
        "序号",
        "日期",
        "月份",
        "模块",
        "工位",
        "问题点描述",
        "类别",
        "分类",
        "人-张程亮",
        "机-陈刚",
        "料-王岩良",
        "法（QCP/SOP）",
        "环境-刘焕良",
        "责任单位",
        "确认人",
        "工段负责人",
        "巡检人",
        "是否结案",
        "逾期天数",
    ],
    "complaint": [
        "月份",
        "产品线",
        "问题归类",
        "不良类型归类",
        "投诉日期",
        "系列",
        "详细机种",
        "生产地",
        "客户/發生處",
        "投诉内容",
        "不良率",
        "暂定对策",
        "不良属性",
        "责任部门",
        "责任跟踪者",
        "结案日期",
        "结案状况（Y/N）",
        "结案状态",
        "结案天数",
        "延期天数",
    ],
    "sampling": [
        "日期",
        "月份",
        "时间段",
        "系列",
        "机种",
        "送检类型",
        "送检单位",
        "送检数量",
        "外观抽检数量",
        "机能抽检数量",
        "不良数量",
        "不良率",
        "抽检批",
        "合格批",
        "合格批率",
        "判定",
        "不良属性",
        "不良位置",
        "现象",
        "数量",
        "检验员",
        "同批送检次数",
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
        "确认者",
        "课室负责人",
    ],
}


MODULE_META: dict[str, dict[str, Any]] = {
    "inspection": {
        "label": "产线巡检",
        "type": "产线巡检问题管理",
        "purpose": "记录产线巡检发现的问题点，跟踪责任与结案进度",
        "actions": ["edit", "mark_status"],
        "nav_hint": "主表=问题清单；抽检数据/代码表为附属功能，勿做成与主表并列的原始分表页",
    },
    "complaint": {
        "label": "客诉跟进",
        "type": "客诉及反馈跟进",
        "purpose": "跟踪客户投诉与反馈，管理对策与结案",
        "actions": ["edit", "mark_status"],
        "nav_hint": "主表=客诉跟进表；汇总/推移图由趋势分析页承担，勿按 Excel 分表逐页镜像",
    },
    "sampling": {
        "label": "产品抽检",
        "type": "OQC抽检批次管理",
        "purpose": "记录 OQC 抽检批次，区分外观/性能不良并关联不良现象",
        "actions": ["edit", "mark_status"],
        "nav_hint": "主表=OQC 抽检批次表；代码表做类别管理，Excel「首页」由趋势分析替代",
    },
}


def _sheet_names(spec: dict[str, Any]) -> list[str]:
    return [(s.get("name") or "").strip() for s in spec.get("sheets") or []]


def _column_keys(spec: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for sheet in spec.get("sheets") or []:
        for col in sheet.get("columns") or []:
            k = (col.get("key") or "").strip()
            if k:
                keys.add(k)
    return keys


def classify_module(spec: dict[str, Any], *, filename: str | None = None) -> str | None:
    """Return inspection | complaint | sampling | None (generic)."""
    title = " ".join(
        filter(
            None,
            [
                filename or "",
                spec.get("filename") or "",
                spec.get("title") or "",
                " ".join(_sheet_names(spec)),
            ],
        )
    )
    cols = _column_keys(spec)

    # Strong sheet-name signals first
    if any("客诉" in n for n in _sheet_names(spec)) or "客诉" in title:
        return "complaint"
    if any("OQC" in n or "抽检批次" in n for n in _sheet_names(spec)):
        return "sampling"
    if any("问题清单" in n for n in _sheet_names(spec)) or "巡检" in title:
        return "inspection"

    # Column fingerprints (for renamed sheets)
    if {"投诉日期", "投诉内容", "不良属性"} & cols:
        return "complaint"
    if {"抽检批", "合格批", "合格批率"} & cols or ({"送检数量", "不良代码"} <= cols):
        return "sampling"
    if {"问题点描述", "是否结案"} <= cols or ({"模块", "工位", "巡检人"} <= cols):
        return "inspection"

    if "抽检" in title and "巡检" not in title:
        return "sampling"
    return None


def resolve_main_sheet(spec: dict[str, Any], module_key: str | None) -> str | None:
    if not module_key:
        return (spec.get("primary_sheet") or "").strip() or None
    hints = MAIN_SHEET_HINTS.get(module_key) or ()
    sheets = spec.get("sheets") or []
    for hint in hints:
        for s in sheets:
            name = (s.get("name") or "").strip()
            if hint in name and s.get("kind") not in ("lookup", "instruction", "hidden"):
                return s.get("name")
    # Fallback: largest fact sheet that is not an unpivot of sampling wide data for inspection
    primary = (spec.get("primary_sheet") or "").strip()
    if module_key == "inspection" and primary and ("抽检数据" in primary or "展开" in primary):
        for s in sheets:
            if "问题清单" in (s.get("name") or ""):
                return s.get("name")
    return primary or None


def curated_display_columns(sheet: dict[str, Any], module_key: str | None) -> list[str]:
    """Intersect blueprint columns with the actual sheet; keep blueprint order."""
    if not module_key or module_key not in DISPLAY_COLUMNS:
        return []
    present = {
        (c.get("key") or "")
        for c in sheet.get("columns") or []
        if c.get("key") and not str(c["key"]).startswith("__")
    }
    preferred = DISPLAY_COLUMNS[module_key]
    hidden = SAMPLING_HIDDEN_DISPLAY_COLUMNS if module_key == "sampling" else frozenset()
    matched = [c for c in preferred if c in present and c not in hidden]
    if len(matched) >= 5:
        return matched
    return matched


def apply_module_blueprint(design: dict[str, Any], spec: dict[str, Any], module_key: str | None) -> dict[str, Any]:
    """Align dashboard_design main table with homepage module patterns."""
    if not module_key or module_key not in MODULE_META:
        return design

    meta = MODULE_META[module_key]
    design = dict(design or {})
    bu = dict(design.get("business_understanding") or {})
    bu.setdefault("type", meta["type"])
    bu.setdefault("purpose", meta["purpose"])
    main_name = resolve_main_sheet(spec, module_key)
    if main_name:
        bu["main_entity"] = main_name
    design["business_understanding"] = bu

    mt = dict(design.get("main_table") or {})
    if main_name:
        mt["sheet"] = main_name
    mt.setdefault("actions", list(meta["actions"]))

    sheet = None
    target = (mt.get("sheet") or "").strip()
    for s in spec.get("sheets") or []:
        if (s.get("name") or "").strip() == target:
            sheet = s
            break

    if sheet:
        curated = curated_display_columns(sheet, module_key)
        if curated:
            # Prefer curated homepage columns; keep any AI extras that already exist on sheet
            # but sit after curated (rare synonyms) — capped so we don't mirror full Excel width.
            existing = [c for c in (mt.get("display_columns") or []) if c]
            present = {
                (c.get("key") or "")
                for c in sheet.get("columns") or []
                if c.get("key")
            }
            hidden = SAMPLING_HIDDEN_DISPLAY_COLUMNS if module_key == "sampling" else frozenset()
            extras = [
                c
                for c in existing
                if c in present and c not in curated and c not in hidden
            ]
            mt["display_columns"] = [c for c in (curated + extras[:5]) if c not in hidden]
            mt["columns_source"] = "module_blueprint"

    design["main_table"] = mt
    design["module_key"] = module_key
    return design


def attach_module_to_spec(spec: dict[str, Any], *, filename: str | None = None) -> str | None:
    """Classify workbook, fix primary_sheet, stamp module_key on spec."""
    module_key = classify_module(spec, filename=filename)
    spec["module_key"] = module_key
    if module_key:
        main = resolve_main_sheet(spec, module_key)
        if main:
            spec["primary_sheet"] = main
        meta = MODULE_META[module_key]
        spec["module_label"] = meta["label"]
        # Enrich smart_view summary for preview
        sv = dict(spec.get("smart_view") or {})
        sv["module_key"] = module_key
        sv["module_label"] = meta["label"]
        sv["module_hint"] = meta["nav_hint"]
        if main:
            sv["preferred_main_sheet"] = main
        spec["smart_view"] = sv
    return module_key


def prompt_guidance(module_key: str | None, spec: dict[str, Any]) -> str:
    """Extra instructions injected into DeepSeek JSON prompt."""
    if not module_key or module_key not in MODULE_META:
        return (
            "\n本文件未匹配到系统内置三模块（产线巡检/客诉跟进/产品抽检）。"
            "请设计通用单页看板，但仍应：选一张主事实表；配置/代码表不要当作并列主表；"
            "dashboard/说明 sheet 不要作为主表；display_columns 选 8–18 个关键列，不要列出全部列。\n"
        )

    meta = MODULE_META[module_key]
    main = resolve_main_sheet(spec, module_key) or ""
    cols = DISPLAY_COLUMNS.get(module_key) or []
    return f"""
本 Excel 对应系统已有业务模块【{meta['label']}】（module_key={module_key}）。
请按该模块现有网页结构出配置，而不是按 Excel 原始分表 1:1 拆页：

- business_understanding.type = "{meta['type']}"
- business_understanding.purpose = "{meta['purpose']}"
- main_table.sheet 必须是主事实表「{main}」（不要用代码表、汇总图、说明页、宽表展开页当主表）
- main_table.display_columns 优先使用这些列（仅保留 Excel 中真实存在的）：{cols}
- main_table.actions = {meta['actions']}
- {meta['nav_hint']}
- KPI/图表应围绕主表；lookup 表仅作联动选项，不要单独做主列表页
"""
