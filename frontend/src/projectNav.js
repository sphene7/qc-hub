/** 三个业务模块各自的项目内 Tab 顺序（系统管理员可配置） */

export const BUSINESS_MODULE_KEYS = ["inspection", "complaint", "sampling"];

export const BUSINESS_MODULE_LABELS = {
  inspection: "产线巡检",
  complaint: "客诉跟进",
  sampling: "产品抽检",
};

/** 各模块可用的 Tab */
export const MODULE_NAV_KEYS = {
  inspection: ["dashboard", "sampling", "analytics", "codes", "sheets"],
  complaint: ["dashboard", "analytics", "sheets"],
  sampling: ["dashboard", "analytics", "codes", "sheets"],
};

/** Tab 在各模块下的显示名（dashboard 因模块而异） */
export const NAV_TAB_LABELS = {
  dashboard: {
    inspection: "问题清单",
    complaint: "客诉明细",
    sampling: "抽检明细",
  },
  sampling: "抽检数据",
  analytics: "趋势分析",
  codes: "类别管理",
  sheets: "原始分表",
};

export const DEFAULT_NAV_ORDERS = {
  inspection: ["dashboard", "sampling", "analytics", "codes", "sheets"],
  complaint: ["dashboard", "analytics", "sheets"],
  sampling: ["dashboard", "analytics", "codes", "sheets"],
};

export function navTabLabel(moduleKey, tabKey) {
  const item = NAV_TAB_LABELS[tabKey];
  if (typeof item === "object") return item[moduleKey] || tabKey;
  return item || tabKey;
}

export function normalizeNavOrder(order, moduleKey) {
  const allowed = new Set(MODULE_NAV_KEYS[moduleKey] || []);
  const defaults = DEFAULT_NAV_ORDERS[moduleKey] || [];
  const out = [];
  for (const key of order || []) {
    const k = String(key).trim();
    if (allowed.has(k) && !out.includes(k)) out.push(k);
  }
  for (const key of defaults) {
    if (allowed.has(key) && !out.includes(key)) out.push(key);
  }
  return out;
}

export function normalizeNavOrders(raw) {
  const result = {};
  for (const mod of BUSINESS_MODULE_KEYS) {
    const src = raw?.[mod];
    result[mod] = normalizeNavOrder(src, mod);
  }
  return result;
}

/** 兼容旧版单一 project_nav_order 数组 → 归入 inspection */
export function migrateNavOrders(data) {
  if (data?.project_nav_orders && typeof data.project_nav_orders === "object") {
    return normalizeNavOrders(data.project_nav_orders);
  }
  if (Array.isArray(data?.project_nav_order)) {
    return normalizeNavOrders({
      inspection: data.project_nav_order,
    });
  }
  return normalizeNavOrders({});
}

export function buildVisibleNavItems(moduleKey, order, defs) {
  const allowed = MODULE_NAV_KEYS[moduleKey] || [];
  const items = [];
  const seen = new Set();
  for (const key of normalizeNavOrder(order, moduleKey)) {
    if (!allowed.includes(key)) continue;
    const def = defs[key];
    if (def?.show && !seen.has(key)) {
      items.push(def);
      seen.add(key);
    }
  }
  for (const key of allowed) {
    const def = defs[key];
    if (def?.show && !seen.has(key)) {
      items.push(def);
      seen.add(key);
    }
  }
  return items;
}

export function detectProjectModuleKey({ isInspection, isComplaint, isOqc }) {
  if (isComplaint) return "complaint";
  if (isOqc) return "sampling";
  if (isInspection) return "inspection";
  return "inspection";
}
