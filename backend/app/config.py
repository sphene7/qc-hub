"""Runtime configuration for platform vs product deployments."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODULES_FILE = ROOT / "product.modules.json"
DEFAULT_UI_SETTINGS_FILE = ROOT / "system.ui.json"

BUSINESS_MODULE_KEYS = ("inspection", "complaint", "sampling")

MODULE_NAV_KEYS: dict[str, list[str]] = {
    "inspection": ["dashboard", "sampling", "analytics", "codes", "sheets"],
    "complaint": ["dashboard", "analytics", "sheets"],
    "sampling": ["dashboard", "analytics", "codes", "sheets"],
}

DEFAULT_PROJECT_NAV_ORDERS: dict[str, list[str]] = {
    mod: list(keys) for mod, keys in MODULE_NAV_KEYS.items()
}

DEFAULT_UI_SETTINGS: dict[str, Any] = {
    "show_raw_sheets": True,
    "show_export_merged": True,
    "project_nav_orders": dict(DEFAULT_PROJECT_NAV_ORDERS),
}


def _normalize_module_nav_order(order: Any, module: str) -> list[str]:
    allowed = MODULE_NAV_KEYS.get(module, [])
    defaults = DEFAULT_PROJECT_NAV_ORDERS.get(module, [])
    if not isinstance(order, list):
        return list(defaults)
    out: list[str] = []
    for key in order:
        s = str(key).strip()
        if s in allowed and s not in out:
            out.append(s)
    for key in defaults:
        if key in allowed and key not in out:
            out.append(key)
    return out


def _normalize_project_nav_orders(raw: Any, legacy_list: Any = None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if isinstance(raw, dict):
        for mod in BUSINESS_MODULE_KEYS:
            result[mod] = _normalize_module_nav_order(raw.get(mod), mod)
        return result
    if isinstance(legacy_list, list):
        result = {mod: list(DEFAULT_PROJECT_NAV_ORDERS[mod]) for mod in BUSINESS_MODULE_KEYS}
        result["inspection"] = _normalize_module_nav_order(legacy_list, "inspection")
        return result
    return {mod: list(DEFAULT_PROJECT_NAV_ORDERS[mod]) for mod in BUSINESS_MODULE_KEYS}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_modules_file() -> dict[str, Any] | None:
    path = os.getenv("PRODUCT_MODULES_FILE", str(DEFAULT_MODULES_FILE))
    module_path = Path(path)
    if not module_path.is_file():
        return None
    try:
        return json.loads(module_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


_file_cfg = _load_modules_file()

APP_MODE = os.getenv("APP_MODE", "platform").strip().lower()
IS_PRODUCT = APP_MODE == "product"

SYSTEM_NAME = os.getenv("SYSTEM_NAME") or (_file_cfg or {}).get("system_name") or "ExcelToWeb"
SYSTEM_SUBTITLE = os.getenv("SYSTEM_SUBTITLE") or (_file_cfg or {}).get("system_subtitle") or "拖入业务表，自动拆公式、认列关系、生成统计页"

ALLOW_UPLOAD = _env_bool("ALLOW_UPLOAD", default=not IS_PRODUCT)
ALLOW_REGISTER = _env_bool("ALLOW_REGISTER", default=not IS_PRODUCT)
ENABLE_AI = _env_bool("ENABLE_AI", default=True)


def get_modules() -> list[dict[str, Any]]:
    """Configured business modules for product mode."""
    raw = os.getenv("SYSTEM_MODULES")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    if _file_cfg and isinstance(_file_cfg.get("modules"), list):
        return _file_cfg["modules"]
    return []


def _ui_settings_path() -> Path:
    return Path(os.getenv("UI_SETTINGS_FILE", str(DEFAULT_UI_SETTINGS_FILE)))


def get_ui_settings() -> dict[str, Any]:
    """Runtime UI settings (admin-editable, persisted to JSON file)."""
    path = _ui_settings_path()
    data: dict[str, Any] = dict(DEFAULT_UI_SETTINGS)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
        except (OSError, json.JSONDecodeError):
            pass
    data["project_nav_orders"] = _normalize_project_nav_orders(
        data.get("project_nav_orders"),
        data.get("project_nav_order"),
    )
    data.pop("project_nav_order", None)
    return data


def save_ui_settings(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge and persist UI settings; returns the saved snapshot."""
    current = get_ui_settings()
    allowed = set(DEFAULT_UI_SETTINGS.keys())
    for key, value in updates.items():
        if key not in allowed:
            continue
        if key == "project_nav_orders":
            current[key] = _normalize_project_nav_orders(value)
        elif key == "project_nav_order":
            current["project_nav_orders"] = _normalize_project_nav_orders(None, value)
            current.pop("project_nav_order", None)
        else:
            current[key] = value
    path = _ui_settings_path()
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def get_system_info() -> dict[str, Any]:
    ui = get_ui_settings()
    return {
        "mode": "product" if IS_PRODUCT else "platform",
        "system_name": SYSTEM_NAME,
        "system_subtitle": SYSTEM_SUBTITLE,
        "allow_upload": ALLOW_UPLOAD,
        "allow_register": ALLOW_REGISTER,
        "enable_ai": ENABLE_AI,
        "modules": get_modules(),
        "show_raw_sheets": bool(ui.get("show_raw_sheets", True)),
        "show_export_merged": bool(ui.get("show_export_merged", True)),
        "project_nav_orders": _normalize_project_nav_orders(
            ui.get("project_nav_orders"),
            ui.get("project_nav_order"),
        ),
    }
