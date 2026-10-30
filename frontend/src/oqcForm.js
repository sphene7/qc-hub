/** Shared OQC / 变焦抽检 form helpers (EntryForm + EditRowDialog). */

export const DEFECT_SEP = "；";
/** 多组录入 UI 接管的字段（含自动合计的不良数量、检验员） */
export const DEFECT_GROUP_KEYS = new Set([
  "不良位置",
  "现象",
  "数量",
  "不良代码",
  "不良数量",
  "检验员",
]);

/** 已退役：登记也不应再出现（与后端 SAMPLING_RETIRED_COLUMNS 对齐） */
export const OQC_RETIRED_KEYS = new Set([
  "不良代码",
  "是否紧急出货",
  "层别备注",
  "单据类型",
  "间断送检次数",
]);

/** 延后到 OA补录 / 闭环分析（列表仍展示） */
export const OQC_STEP1_HIDE_KEYS = new Set([
  "OA单号",
  "结案日期",
  "结案天数",
  "指定质控公司",
  "临时对策",
  "根因分析",
  "永久对策",
  "改善后确认",
  "责任单位",
  "责任人",
  "责任课级负责人",
  "品质工程师",
  ...OQC_RETIRED_KEYS,
]);

export function getFormLookups(sheet, localLookups = {}) {
  const base = sheet?.form?.lookups || {};
  return {
    series_sections: {},
    series_confirmers: {},
    section_heads: {},
    defect_phenomena: {},
    ...base,
    ...localLookups,
  };
}

export function oqcModelFieldKey(sheet) {
  const fields = sheet?.form?.fields || [];
  if (fields.some((f) => f.key === "系列")) return "系列";
  if (fields.some((f) => f.key === "机种")) return "机种";
  return null;
}

export function oqcShowFlags(sheet) {
  const computed = new Set((sheet?.form?.computed || []).map((c) => c.key));
  const fields = sheet?.form?.fields || [];
  const fieldKeys = new Set(fields.map((f) => f.key));
  const colKeys = new Set((sheet?.columns || []).map((c) => c.key).filter(Boolean));
  const modelKey = oqcModelFieldKey(sheet);
  const hasLoc = fieldKeys.has("不良位置") || colKeys.has("不良位置");
  const hasPhen =
    fieldKeys.has("现象") ||
    colKeys.has("现象") ||
    computed.has("现象") ||
    fields.some((f) => f.group === "defect");
  return {
    modelKey,
    section: !!modelKey && computed.has("送检单位"),
    confirmer: !!modelKey && computed.has("确认者"),
    head: computed.has("送检单位") && computed.has("课室负责人"),
    // 方案 B：不再用不良代码联动现象；改为多组录入
    phenomenon: false,
    defectGroups: hasLoc && hasPhen,
  };
}

export function mergeFieldOptions(field, lookups, formValue) {
  let opts = [...(field?.options || [])];
  const key = field?.key;
  if (key === "机种" || key === "系列") {
    for (const k of Object.keys(lookups?.series_sections || {})) {
      if (k && !opts.includes(k)) opts.push(k);
    }
  }
  if (key === "现象") {
    for (const v of Object.values(lookups?.defect_phenomena || {})) {
      const d = String(v || "").trim();
      if (d && !opts.includes(d)) opts.push(d);
    }
  }
  if (key === "送检单位") {
    for (const v of Object.values(lookups?.series_sections || {})) {
      if (v && !opts.includes(v)) opts.push(v);
    }
  }
  const cur = formValue == null ? "" : String(formValue).trim();
  if (cur && !opts.includes(cur)) opts.unshift(cur);
  return opts;
}

export function pickerOptions(map, current = "") {
  const opts = Object.keys(map || {}).filter(Boolean);
  const cur = String(current || "").trim();
  if (cur && !opts.includes(cur)) opts.unshift(cur);
  return opts.sort((a, b) => a.localeCompare(b, "zh-CN"));
}

export function buildSectionPickerOptions(lookups, current = "") {
  const sections = new Set(Object.values(lookups?.series_sections || {}).filter(Boolean));
  for (const k of Object.keys(lookups?.section_heads || {})) {
    if (k) sections.add(k);
  }
  const opts = [...sections];
  const cur = String(current || "").trim();
  if (cur && !opts.includes(cur)) opts.unshift(cur);
  return opts.sort((a, b) => a.localeCompare(b, "zh-CN"));
}

export function buildConfirmerPickerOptions(lookups, current = "") {
  const owners = new Set(
    Object.values(lookups?.series_confirmers || {})
      .map((v) => String(v || "").trim())
      .filter(Boolean),
  );
  const cur = String(current || "").trim();
  if (cur) owners.add(cur);
  return [...owners].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

export function resolveConfirmerForModel(model, lookups) {
  const key = String(model || "").trim();
  if (!key) return "";
  const map = lookups?.series_confirmers || {};
  if (map[key] != null && String(map[key]).trim()) return String(map[key]).trim();
  for (const [k, v] of Object.entries(map)) {
    if (String(k).trim() === key && v != null && String(v).trim()) return String(v).trim();
  }
  return "";
}

export function onOqcModelChange(value, lookups, pickers) {
  const model = String(value || "").trim();
  const section = lookups?.series_sections?.[model];
  const confirmer = resolveConfirmerForModel(model, lookups);
  if (section) pickers.section = section;
  if (confirmer) pickers.confirmer = confirmer;
  if (pickers.section) {
    const head = lookups?.section_heads?.[pickers.section];
    if (head) pickers.head = head;
  }
}

export function onOqcSectionChange(section, lookups, pickers) {
  pickers.section = String(section || "").trim();
  const head = lookups?.section_heads?.[pickers.section];
  if (head) pickers.head = head;
}

export function buildPhenomenonPickerOptions(lookups, current = "") {
  const set = new Set(
    Object.values(lookups?.defect_phenomena || {})
      .map((v) => String(v || "").trim())
      .filter(Boolean),
  );
  const cur = String(current || "").trim();
  if (cur) set.add(cur);
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

export function emptyDefectGroup() {
  return { location: "", phenomenon: "", qty: "", inspector: "" };
}

function splitDefectParts(val) {
  const s = String(val ?? "").trim();
  if (!s || s.toLowerCase() === "nan" || s.toLowerCase() === "none") return [];
  return s
    .split(/[;；|｜/／\n]+/)
    .map((p) => p.trim())
    .filter(Boolean);
}

/** Parse flat row columns into editable defect groups. */
export function parseDefectGroups(row) {
  if (!row) return [emptyDefectGroup()];
  const locs = splitDefectParts(row["不良位置"]);
  const phens = splitDefectParts(row["现象"]);
  const qtys = splitDefectParts(row["数量"]);
  const inspectors = splitDefectParts(row["检验员"]);
  const n = Math.max(locs.length, phens.length, qtys.length, inspectors.length);
  if (n === 0) return [emptyDefectGroup()];
  const groups = [];
  for (let i = 0; i < n; i++) {
    const location = locs[i] || "";
    const phenomenon = phens[i] || "";
    const qty = qtys[i] || "";
    const inspector = inspectors[i] || "";
    if (!location && !phenomenon && !qty && !inspector) continue;
    groups.push({ location, phenomenon, qty, inspector });
  }
  return groups.length ? groups : [emptyDefectGroup()];
}

export function filledDefectGroups(groups) {
  return (groups || []).filter((g) => {
    const loc = String(g?.location || "").trim();
    const phen = String(g?.phenomenon || "").trim();
    const inspector = String(g?.inspector || "").trim();
    const qty = g?.qty === 0 || g?.qty === "0" ? "0" : String(g?.qty ?? "").trim();
    return loc || phen || qty !== "" || inspector;
  });
}

/** Serialize groups back into flat OQC columns. */
export function serializeDefectGroups(groups) {
  const filled = filledDefectGroups(groups).map((g) => ({
    location: String(g.location || "").trim(),
    phenomenon: String(g.phenomenon || "").trim(),
    qty: g.qty === 0 || g.qty === "0" ? "0" : String(g.qty ?? "").trim(),
    inspector: String(g.inspector || "").trim(),
  }));
  if (!filled.length) {
    return {
      不良位置: null,
      现象: null,
      数量: null,
      不良数量: null,
      不良代码: null,
      检验员: null,
    };
  }
  let total = 0;
  let hasQty = false;
  for (const g of filled) {
    if (g.qty === "") continue;
    const n = Number(g.qty);
    if (!Number.isNaN(n)) {
      total += n;
      hasQty = true;
    }
  }
  return {
    不良位置: filled.map((g) => g.location).join(DEFECT_SEP),
    现象: filled.map((g) => g.phenomenon).join(DEFECT_SEP),
    数量: filled.map((g) => g.qty).join(DEFECT_SEP),
    检验员: filled.map((g) => g.inspector).join(DEFECT_SEP),
    不良数量: hasQty ? total : null,
    不良代码: null,
  };
}

export function applyOqcPickersToValues(values, flags, pickers) {
  if (flags.section && pickers.section) values["送检单位"] = pickers.section;
  if (flags.confirmer && pickers.confirmer) values["确认者"] = pickers.confirmer;
  if (flags.head && pickers.head) values["课室负责人"] = pickers.head;
}

export function syncOqcPickersFromRow(row, pickers) {
  if (!row) return;
  if (row["送检单位"]) pickers.section = String(row["送检单位"]);
  if (row["确认者"]) pickers.confirmer = String(row["确认者"]);
  if (row["课室负责人"]) pickers.head = String(row["课室负责人"]);
}

export function visibleComputedFields(sheet, flags) {
  return (sheet?.form?.computed || []).filter((c) => {
    if (c.key === "送检单位" && flags.section) return false;
    if (c.key === "确认者" && flags.confirmer) return false;
    if (c.key === "课室负责人" && flags.head) return false;
    if (c.key === "现象" && (flags.phenomenon || flags.defectGroups)) return false;
    return c.kind !== "auto_id";
  });
}

/** 抽检：每组位置↔现象成对；有不良时须选不良属性。返回错误文案或 ""。 */
export function validateOqcDefectValues(sheet, values, groups = null) {
  const name = sheet?.name || "";
  if (!name.includes("OQC") && !name.includes("抽检批次")) return "";
  const keys = new Set((sheet?.columns || []).map((c) => c.key).filter(Boolean));
  const fieldKeys = new Set((sheet?.form?.fields || []).map((f) => f.key).filter(Boolean));
  const list = groups != null ? filledDefectGroups(groups) : parseDefectGroups(values);
  const attr = String(values?.["不良属性"] || "").trim();
  const qty = Number(values?.["不良数量"] || 0);

  for (let i = 0; i < list.length; i++) {
    const loc = String(list[i].location || "").trim();
    const phen = String(list[i].phenomenon || "").trim();
    if (loc && !phen && (keys.has("现象") || fieldKeys.has("现象"))) {
      return `第${i + 1}组：填写不良位置时必须填写不良现象`;
    }
    if (phen && !loc && (keys.has("不良位置") || fieldKeys.has("不良位置"))) {
      return `第${i + 1}组：填写不良现象时必须填写不良位置`;
    }
  }

  if (
    (list.length > 0 || qty > 0) &&
    (keys.has("不良属性") || fieldKeys.has("不良属性")) &&
    !attr
  ) {
    return "请选择不良属性（外观不良 / 性能不良）";
  }
  return "";
}
