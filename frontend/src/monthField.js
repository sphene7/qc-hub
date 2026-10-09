export function todayMonthInputValue(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

export function isMonthField(field) {
  if (!field) return false;
  if (field.widget === "month") return true;
  const key = field.key || "";
  return key === "月份" || field.semantic === "month";
}

/** ISO date `YYYY-MM-DD` → month picker value `YYYY-MM`. */
export function monthInputFromDate(dateStr) {
  if (dateStr == null || dateStr === "") return "";
  const m = String(dateStr).match(/^(\d{4})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}`;
  return "";
}

export function toMonthInputValue(value, fallbackYear = new Date().getFullYear()) {
  if (value == null || value === "") return "";
  const s = String(value).trim();
  let m = s.match(/^(\d{4})年(\d{1,2})月$/);
  if (m) return `${m[1]}-${String(m[2]).padStart(2, "0")}`;
  m = s.match(/^(\d{4})-(\d{2})(?:-\d{2})?$/);
  if (m) return `${m[1]}-${m[2]}`;
  m = s.match(/^(\d{1,2})月$/);
  if (m) return `${fallbackYear}-${String(m[1]).padStart(2, "0")}`;
  return "";
}

export function fromMonthInputValue(value) {
  if (value == null || value === "") return "";
  const s = String(value).trim();
  const m = s.match(/^(\d{4})-(\d{2})$/);
  if (m) return `${m[1]}年${parseInt(m[2], 10)}月`;
  return s;
}

export function normalizeMonthLabel(value, defaultYear = 2026) {
  if (value == null || value === "") return "";
  const s = String(value).trim();
  if (/^\d{4}年\d{1,2}月$/.test(s)) return s;
  const m = s.match(/^(\d{1,2})月$/);
  if (m) return `${defaultYear}年${parseInt(m[1], 10)}月`;
  const input = toMonthInputValue(s, defaultYear);
  if (input) return fromMonthInputValue(input);
  return s;
}

export function formatMonthDisplay(value, fallbackYear = 2026) {
  if (value == null || value === "") return "—";
  return normalizeMonthLabel(value, fallbackYear) || "—";
}

export function monthFallbackYear(form, dateKeys = ["投诉日期", "日期"]) {
  for (const key of dateKeys) {
    const raw = form?.[key];
    if (!raw) continue;
    const y = String(raw).slice(0, 4);
    if (/^\d{4}$/.test(y)) return parseInt(y, 10);
  }
  return new Date().getFullYear();
}
