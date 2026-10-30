/** HTML5 日期选择器（Date Picker）共用工具 */

function localYmd(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function todayDateString() {
  return localYmd(new Date());
}

/** 抽检登记默认业务日：一般今天录昨天的 */
export function yesterdayDateString() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return localYmd(d);
}

export function toDateInputValue(v) {
  if (v == null || v === "") return "";
  const s = String(v).trim();
  const m = s.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s].*)?$/);
  if (m) return m[1];
  return s;
}
