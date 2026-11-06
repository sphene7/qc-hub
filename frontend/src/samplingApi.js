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
  const defects = entry?.异常总数 ?? inspections.reduce((n, c) => n + (c.不良组 || []).length, 0);
  if (!inspections.length) return { label: "待抽检", cls: "badge-muted" };
  if (defects > 0) return { label: "NG", cls: "badge-bad" };
  return { label: "OK", cls: "badge-ok" };
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
        机种: e.机种,
        送检单位: e.送检单位,
        送检数量: e.送检数量,
        submission: e,
      });
    }
  }
  return out;
}

