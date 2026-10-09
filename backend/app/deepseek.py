"""DeepSeek API integration for intelligent Excel analysis."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from .logutil import log as _log
from .spec_sync import ensure_main_table_columns, ensure_dashboard_filters

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
JSON_SCHEMA_HINT = """
{
  "business_understanding": {
    "type": "业务类型名称",
    "purpose": "业务目的简述",
    "main_entity": "主表名称"
  },
  "kpis": [
    {
      "id": "unique_id",
      "label": "指标名称",
      "source_sheet": "数据来源表名",
      "calculation": {"type": "count|sum|avg|rate", "field": "字段名(可选)"},
      "format": "int|number|percent"
    }
  ],
  "charts": [
    {
      "id": "unique_id",
      "title": "图表标题",
      "type": "line|bar|pie",
      "source_sheet": "数据来源表名",
      "x_field": "X轴列名",
      "y_field": "Y轴列名或null",
      "aggregation": "count|sum|avg"
    }
  ],
  "filters": [
    {
      "field": "列名",
      "type": "date_range|enum|search",
      "label": "筛选器标签"
    }
  ],
  "main_table": {
    "sheet": "主表名",
    "display_columns": ["列1", "列2"],
    "actions": ["edit", "mark_status"]
  }
}
"""


def create_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-f7dc907b94964d048aca7a6458963c65")
    _log(f"🔑 使用API Key: {api_key[:15]}...{api_key[-5:]}")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _save_debug(name: str, content: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / name
        path.write_text(content, encoding="utf-8")
        _log(f"💾 已保存调试文件: {path}")
    except OSError as exc:
        _log(f"⚠️ 无法保存调试文件: {exc}")


def _summarize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    sheets_info = []
    for sheet in spec.get("sheets", []):
        sheets_info.append(
            {
                "name": sheet["name"],
                "kind": sheet["kind"],
                "row_count": sheet["row_count"],
                "columns": [
                    {
                        "name": col["key"],
                        "label": col["label"],
                        "role": col["role"],
                    }
                    for col in sheet.get("columns", [])[:15]
                ],
            }
        )
    return {
        "filename": spec.get("filename"),
        "title": spec.get("title"),
        "sheets": sheets_info,
        "joins": spec.get("joins", [])[:20],
        "smart_view": spec.get("smart_view", {}),
    }


def _call_chat(client: OpenAI, system: str, user: str, *, max_tokens: int = 4096, json_mode: bool = False) -> str:
    kwargs: dict[str, Any] = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    usage = getattr(response, "usage", None)
    if usage:
        _log(f"   tokens: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
    return response.choices[0].message.content or ""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None

    # 1) 整段直接解析（json_object 模式通常可直接 loads）
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2) ```json 代码块
    blocks = re.findall(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    for block in reversed(blocks):
        try:
            obj = json.loads(block.strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    # 3) 括号匹配：收集所有合法对象，取最大的（避免只解析到 main_table 等子对象）
    candidates: list[dict[str, Any]] = []
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in reversed(starts):
        depth = 0
        in_str = False
        esc = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[start : idx + 1]
                    try:
                        obj = json.loads(snippet)
                        if isinstance(obj, dict):
                            candidates.append(obj)
                    except json.JSONDecodeError:
                        pass
                    break

    if not candidates:
        return None

    def score(d: dict[str, Any]) -> tuple:
        return (
            1 if d.get("kpis") else 0,
            1 if d.get("charts") else 0,
            1 if d.get("business_understanding") else 0,
            len(d),
        )

    return max(candidates, key=score)


def _normalize_design(raw: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    design = dict(raw)
    for key in ("business_understanding", "kpis", "charts", "main_table", "filters"):
        if key not in design:
            design[key] = _get_default_value(key)

    bu = design.get("business_understanding") or {}
    if not bu.get("main_entity"):
        bu["main_entity"] = spec.get("primary_sheet") or (spec.get("sheets", [{}])[0].get("name", ""))
        design["business_understanding"] = bu

    mt = design.get("main_table") or {}
    if not mt.get("sheet"):
        mt["sheet"] = bu.get("main_entity") or spec.get("primary_sheet") or ""
        design["main_table"] = mt

    ensure_main_table_columns(design, spec)
    ensure_dashboard_filters(design, spec)
    return design


def _build_json_prompt(spec: dict[str, Any]) -> str:
    summary = _summarize_spec(spec)
    return f"""你是Excel业务系统架构师。根据以下Excel结构，设计一个**单页业务看板**的配置JSON。

要求：
1. 只输出一个合法JSON对象，不要markdown，不要解释文字
2. 识别主数据表（fact表优先）
3. KPI 3-6个，图表 4-6个，筛选器 3-5个
4. 字段名必须使用Excel中的真实列名（columns.name）
5. 表名必须使用真实sheet名

Excel结构：
{json.dumps(summary, ensure_ascii=False, indent=2)}

JSON schema：
{JSON_SCHEMA_HINT}
"""


def _build_design_doc_prompt(spec: dict[str, Any], design: dict[str, Any]) -> str:
    summary = _summarize_spec(spec)
    return f"""请为以下Excel业务系统设计一份**中文设计方案**（markdown格式），供产品经理阅读。

Excel: {spec.get('filename')}
已生成的系统配置摘要：
- 业务类型: {design.get('business_understanding', {}).get('type')}
- 主表: {design.get('main_table', {}).get('sheet')}
- KPI: {[k.get('label') for k in design.get('kpis', [])]}
- 图表: {[c.get('title') for c in design.get('charts', [])]}

Excel结构：
{json.dumps(summary, ensure_ascii=False, indent=2)}

请按以下章节输出：
## 一、业务理解
## 二、设计目标
## 三、页面布局（筛选/KPI/图表/主表/补充功能）
## 四、数据整合逻辑
## 五、界面布局示意
"""


def analyze_excel_structure(parsed_data: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    _log("\n" + "=" * 80)
    _log("🤖 开始 DeepSeek 分析（两阶段）")
    _log("=" * 80)
    _log(f"📊 文件: {spec.get('filename', 'unknown')}")
    _log(f"📋 表数量: {len(spec.get('sheets', []))}")

    client = create_client()

    # Phase 1: JSON config (for rendering)
    try:
        _log("\n[阶段1/2] 生成系统配置 JSON ...")
        json_prompt = _build_json_prompt(spec)
        _save_debug("deepseek_prompt_json.txt", json_prompt)

        content = ""
        try:
            _log("   尝试 json_object 模式 ...")
            content = _call_chat(
                client,
                "你只输出合法JSON，不要任何其他文字。",
                json_prompt,
                max_tokens=4096,
                json_mode=True,
            )
        except Exception as exc:
            _log(f"   json_object 模式失败: {exc}")
            _log("   回退到普通模式 ...")
            content = _call_chat(
                client,
                "你只输出合法JSON，不要任何其他文字。",
                json_prompt,
                max_tokens=4096,
                json_mode=False,
            )

        _save_debug("deepseek_response_json.txt", content)
        _log(f"   响应长度: {len(content)} 字符")

        raw = _extract_json_object(content)
        if not raw:
            raise ValueError("无法从阶段1响应中提取JSON")

        design = _normalize_design(raw, spec)
        _log(f"   ✅ JSON解析成功: KPI={len(design.get('kpis', []))}, charts={len(design.get('charts', []))}")

    except Exception as exc:
        _log(f"   ❌ 阶段1失败: {exc}")
        design = _get_fallback_design(spec)
        design["parse_error"] = str(exc)

    # Phase 2: Chinese design document (for preview / PM review)
    try:
        _log("\n[阶段2/2] 生成中文设计方案 ...")
        doc_prompt = _build_design_doc_prompt(spec, design)
        doc = _call_chat(
            client,
            "你是资深产品经理，输出清晰的中文markdown设计方案。",
            doc_prompt,
            max_tokens=6000,
            json_mode=False,
        )
        _save_debug("deepseek_response_doc.txt", doc)
        design["design_document"] = doc
        _log(f"   ✅ 设计文档长度: {len(doc)} 字符")
    except Exception as exc:
        _log(f"   ⚠️ 阶段2失败（不影响JSON配置）: {exc}")

    ensure_main_table_columns(design, spec)
    ensure_dashboard_filters(design, spec)

    _log("\n" + "=" * 80)
    _log("🎉 DeepSeek 分析完成")
    _log(f"   业务类型: {design.get('business_understanding', {}).get('type')}")
    _log(f"   KPI: {len(design.get('kpis', []))}, 图表: {len(design.get('charts', []))}")
    _log("=" * 80 + "\n")
    return design


def _get_default_value(key: str) -> Any:
    defaults = {
        "business_understanding": {"type": "unknown", "purpose": "", "main_entity": ""},
        "kpis": [],
        "charts": [],
        "main_table": {"sheet": "", "display_columns": [], "actions": []},
        "filters": [],
        "layout": {"order": ["filters", "kpis", "charts", "table"], "emphasis": ""},
    }
    return defaults.get(key)


def _get_fallback_design(spec: dict[str, Any]) -> dict[str, Any]:
    primary_sheet = spec.get("primary_sheet") or (spec.get("sheets", [{}])[0].get("name", ""))
    primary = next((s for s in spec.get("sheets", []) if s.get("name") == primary_sheet), None)
    cols = [c["key"] for c in (primary or {}).get("columns", []) if c.get("role") != "empty"][:8]

    design = {
        "business_understanding": {
            "type": "数据分析看板",
            "purpose": "展示并管理导入的Excel业务数据",
            "main_entity": primary_sheet,
        },
        "kpis": [
            {
                "id": "total_records",
                "label": "总记录数",
                "source_sheet": primary_sheet,
                "calculation": {"type": "count"},
                "format": "int",
            }
        ],
        "charts": [],
        "main_table": {
            "sheet": primary_sheet,
            "display_columns": cols,
            "actions": ["edit"],
        },
        "filters": [],
        "layout": {"order": ["kpis", "table"], "emphasis": "table"},
    }
    ensure_main_table_columns(design, spec)
    ensure_dashboard_filters(design, spec)
    return design
