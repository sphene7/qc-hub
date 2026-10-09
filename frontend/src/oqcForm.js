/** Shared OQC / 变焦抽检 form helpers (EntryForm + EditRowDialog). */

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
  const modelKey = oqcModelFieldKey(sheet);
  return {
    modelKey,
    section: !!modelKey && computed.has("送检单位"),
    confirmer: !!modelKey && computed.has("确认者"),
    head: computed.has("送检单位") && computed.has("课室负责人"),
    phenomenon: fields.some((f) => f.key === "不良代码") && computed.has("现象"),
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
  if (key === "不良代码") {
    for (const k of Object.keys(lookups?.defect_phenomena || {})) {
      if (k && !opts.includes(k)) opts.push(k);
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

export function resolveDefectCodeForPhenomenon(phenomenon, lookups) {
  const target = String(phenomenon || "").trim();
  if (!target) return "";
  const matches = [];
  for (const [code, desc] of Object.entries(lookups?.defect_phenomena || {})) {
    const c = String(code || "").trim();
    const d = String(desc || "").trim();
    if (!c) continue;
    if (d === target) matches.push(c);
  }
  if (matches.length === 1) return matches[0];
  if (matches.length > 1) {
    matches.sort((a, b) => a.localeCompare(b, "zh-CN"));
    return matches[0];
  }
  return "";
}

export function onOqcDefectChange(code, lookups, pickers) {
  const phen = lookups?.defect_phenomena?.[String(code || "").trim()];
  if (phen) pickers.phenomenon = phen;
}

export function onOqcPhenomenonChange(phenomenon, lookups, pickers) {
  const code = resolveDefectCodeForPhenomenon(phenomenon, lookups);
  if (code) pickers.defectCode = code;
  return code;
}

export function applyOqcPickersToValues(values, flags, pickers) {
  if (flags.section && pickers.section) values["送检单位"] = pickers.section;
  if (flags.confirmer && pickers.confirmer) values["确认者"] = pickers.confirmer;
  if (flags.head && pickers.head) values["课室负责人"] = pickers.head;
  if (flags.phenomenon && pickers.phenomenon) values["现象"] = pickers.phenomenon;
}

export function syncOqcPickersFromRow(row, pickers, lookups = null) {
  if (!row) return;
  if (row["送检单位"]) pickers.section = String(row["送检单位"]);
  if (row["确认者"]) pickers.confirmer = String(row["确认者"]);
  if (row["课室负责人"]) pickers.head = String(row["课室负责人"]);
  if (row["现象"]) pickers.phenomenon = String(row["现象"]);
  if (lookups && row["现象"] && !row["不良代码"]) {
    const code = resolveDefectCodeForPhenomenon(row["现象"], lookups);
    if (code) pickers.defectCode = code;
  }
}

export function visibleComputedFields(sheet, flags) {
  return (sheet?.form?.computed || []).filter((c) => {
    if (c.key === "送检单位" && flags.section) return false;
    if (c.key === "确认者" && flags.confirmer) return false;
    if (c.key === "课室负责人" && flags.head) return false;
    if (c.key === "现象" && flags.phenomenon) return false;
    return c.kind !== "auto_id";
  });
}
