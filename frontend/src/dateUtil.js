/** 抽检状况等「M月D日」与 HTML date 互转 */

export function inferProjectYear(spec) {
  const text = `${spec?.title || ""} ${spec?.filename || ""}`;
  const m = text.match(/20\d{2}/);
  const year = m ? parseInt(m[0], 10) : new Date().getFullYear();
  console.log("[dateUtil] inferProjectYear", { text: text.slice(0, 40), year });
  return year;
}

export function todayIso() {
  const d = new Date();
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  console.log("[dateUtil] todayIso", iso);
  return iso;
}

export function formatSamplingDateLabel(v) {
  if (v == null || v === "") return "";
  const s = String(v).trim();
  if (/^\d+月\d+日$/.test(s)) return s;
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${parseInt(m[2], 10)}月${parseInt(m[3], 10)}日`;
  const n = Number(s);
  if (!Number.isNaN(n) && n > 20000 && n < 80000) {
    const base = new Date(1899, 11, 30);
    const d = new Date(base.getTime() + n * 86400000);
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  }
  return s;
}

export function cnDateToIso(label, year = new Date().getFullYear()) {
  const m = String(label || "").match(/(\d+)月(\d+)日/);
  if (!m) {
    console.warn("[dateUtil] cnDateToIso: 无法解析", { label, year });
    return "";
  }
  const iso = `${year}-${String(m[1]).padStart(2, "0")}-${String(m[2]).padStart(2, "0")}`;
  console.log("[dateUtil] cnDateToIso", { label, year, iso });
  return iso;
}

export function isoToCnDate(iso) {
  if (!iso) {
    console.warn("[dateUtil] isoToCnDate: 空 ISO");
    return "";
  }
  const parts = iso.split("-");
  if (parts.length < 3) {
    console.warn("[dateUtil] isoToCnDate: 格式异常", iso);
    return "";
  }
  const [y, mo, d] = parts;
  const cn = `${parseInt(mo, 10)}月${parseInt(d, 10)}日`;
  console.log("[dateUtil] isoToCnDate", { iso, cn, year: y });
  return cn;
}

export function resolveEditorDate(rawValue, spec) {
  const year = inferProjectYear(spec);
  const label = formatSamplingDateLabel(rawValue);
  const iso = label ? cnDateToIso(label, year) : "";
  console.log("[dateUtil] resolveEditorDate", { rawValue, label, year, iso });
  return { label, iso, year };
}
