/** 抽检三级登记共用请求封装。 */

import { authFetch, getCurrentUser } from "./api.js";

function base(workbookId) {
  return `/api/workbooks/${workbookId}/sampling`;
}

async function request(url, options = {}) {
  const res = await authFetch(url, {
    method: options.method || "GET",
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok) {
    throw new Error(data.detail || `请求失败（${res.status}）`);
  }
  return data;
}

export function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function loadSampling(workbookId) {
  return request(`${base(workbookId)}/entries`);
}

export function createSubmission(workbookId, payload) {
  return request(`${base(workbookId)}/submissions`, { method: "POST", body: payload });
}

export function updateSubmission(workbookId, sid, payload) {
  return request(`${base(workbookId)}/submissions/${encodeURIComponent(sid)}`, {
    method: "PUT",
    body: payload,
  });
}

export function deleteSubmission(workbookId, sid) {
  return request(`${base(workbookId)}/submissions/${encodeURIComponent(sid)}`, {
    method: "DELETE",
  });
}

export function addInspection(workbookId, sid, payload) {
  return request(`${base(workbookId)}/submissions/${encodeURIComponent(sid)}/inspections`, {
    method: "POST",
    body: payload,
  });
}

export function updateInspection(workbookId, iid, payload) {
  return request(`${base(workbookId)}/inspections/${encodeURIComponent(iid)}`, {
    method: "PUT",
    body: payload,
  });
}

export function deleteInspection(workbookId, iid) {
  return request(`${base(workbookId)}/inspections/${encodeURIComponent(iid)}`, {
    method: "DELETE",
  });
}

export function saveException(workbookId, iid, payload) {
  return request(`${base(workbookId)}/inspections/${encodeURIComponent(iid)}/exception`, {
    method: "PUT",
    body: payload,
  });
}

export function deleteException(workbookId, iid) {
  return request(`${base(workbookId)}/inspections/${encodeURIComponent(iid)}/exception`, {
    method: "DELETE",
  });
}

export function submissionStatus(entry) {
  const inspections = entry?.抽检 || [];
  if (!inspections.length) return { label: "待抽检", cls: "smp-badge-muted" };
  const verdicts = inspections.map((c) => String(c.判定 || "").trim().toUpperCase());
  if (verdicts.some((v) => !v)) return { label: "待判定", cls: "smp-badge-muted" };
  if (verdicts.some((v) => v.startsWith("NG"))) return { label: "NG", cls: "smp-badge-bad" };
  if (verdicts.every((v) => v.startsWith("OK"))) return { label: "OK", cls: "smp-badge-ok" };
  return { label: "待判定", cls: "smp-badge-muted" };
}

export function defectCount(entry) {
  return entry?.异常总数 ?? (entry?.抽检 || []).reduce((n, c) => n + (c.不良组 || []).length, 0);
}

/** 当前登录人显示名（与后端 登记人 一致：full_name 优先）。 */
export function meName() {
  const user = getCurrentUser();
  return String(user?.full_name || user?.username || "").trim();
}

/** 关键字 + 日期区间 过滤。 */
export function inRange(day, from, to) {
  const d = String(day || "").slice(0, 10);
  if (from && d && d < from) return false;
  if (to && d && d > to) return false;
  return true;
}

export function matchKeyword(keyword, ...values) {
  const k = String(keyword || "").trim().toLowerCase();
  if (!k) return true;
  return values.some((v) => String(v ?? "").toLowerCase().includes(k));
}

/** 把「送检 → 抽检 → 异常」摊平成各层记录，附带所属送检信息。 */
export function flattenInspections(entries) {
  const out = [];
  for (const e of entries || []) {
    for (const c of e.抽检 || []) {
      out.push({
        ...c,
        日期: e.日期,
        部番: c.部番 || e.部番,
        机种: e.机种,
        送检类型: c.送检类型 || e.送检类型,
        事业部: c.事业部 || e.事业部,
        送检单位: e.送检单位,
        送检数量: e.送检数量,
        submission: e,
      });
    }
  }
  return out;
}

export function csvEscape(value) {
  const text = value == null ? "" : String(value);
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

/** 把「2026-11-10 20:59」拆成日期、时间两列。 */
export function splitDateTime(value) {
  const raw = String(value || "").replace("T", " ").trim();
  if (!raw) return { date: "", time: "" };
  const [datePart, timePart = ""] = raw.split(/\s+/, 2);
  return {
    date: datePart.slice(0, 10),
    time: timePart.slice(0, 5),
  };
}

/** 导出当前筛选为带 BOM 的 CSV，便于 Excel 打开中文。 */
export function downloadCsv(filename, headers, rows) {
  const lines = [headers.map(csvEscape).join(",")];
  for (const row of rows) {
    lines.push(row.map(csvEscape).join(","));
  }
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** 富文本/HTML 压成纯文本，供 CSV 导出。 */
export function plainText(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  if (!/[<>]/.test(raw)) return raw;
  const el = document.createElement("div");
  el.innerHTML = raw;
  return String(el.textContent || el.innerText || "").replace(/\s+/g, " ").trim();
}

