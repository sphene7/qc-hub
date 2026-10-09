/** HTML5 日期选择器（Date Picker）共用工具 */

export function todayDateString() {
  return new Date().toISOString().slice(0, 10);
}

export function toDateInputValue(v) {
  if (v == null || v === "") return "";
  const s = String(v).trim();
  const m = s.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s].*)?$/);
  if (m) return m[1];
  return s;
}
