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
        是否紧急出货: c.是否紧急出货 || e.是否紧急出货 || "",
        完成日期: c.完成日期 || e.完成日期 || "",
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

/**
 * 解析扫码枪扫入的工单内容，尽量抽出 工单号 / 部番 / 数量。
 * 支持：JSON；「部番:xx 数量:n」；分隔符 | , ; tab * /；已知部番子串匹配。
 */
export function parseWorkOrderScan(raw, knownParts = []) {
  const text = String(raw || "").replace(/\r/g, "").trim();
  if (!text) return { workOrder: "", partNo: "", qty: "" };

  if (text.startsWith("{")) {
    try {
      const o = JSON.parse(text);
      return {
        workOrder: String(o.工单号 || o.workOrder || o.wo || o.WO || "").trim() || text,
        partNo: String(o.部番 || o.料号 || o.partNo || o.model || "").trim(),
        qty: String(o.数量 || o.送检数量 || o.qty || o.Qty || "").trim(),
      };
    } catch {
      /* fall through */
    }
  }

  const labeledPart = text.match(/(?:部番|料号|机种)\s*[:=：]\s*([A-Za-z0-9][A-Za-z0-9._-]*)/i);
  const labeledQty = text.match(/(?:数量|送检数量|qty)\s*[:=：]\s*(\d+)/i);
  const labeledWo = text.match(/(?:工单号|工单|WO)\s*[:=：]\s*([A-Za-z0-9][A-Za-z0-9._-]*)/i);

  let tokens = text.split(/[|;\t,*\/]+/).map((t) => t.trim()).filter(Boolean);
  if (tokens.length <= 1) {
    tokens = text.split(/_{2,}|\s{2,}|\s+/).map((t) => t.trim()).filter(Boolean);
  }

  const partLike = (t) =>
    /^[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9][A-Za-z0-9-]*$/.test(t) ||
    /^[A-Za-z0-9]+-[A-Za-z0-9-]+$/.test(t);

  let partNo = labeledPart?.[1] || "";
  let qty = labeledQty?.[1] || "";
  let workOrder = labeledWo?.[1] || "";

  if (!partNo && knownParts?.length) {
    const hit = [...knownParts]
      .map((p) => String(p || "").trim())
      .filter(Boolean)
      .sort((a, b) => b.length - a.length)
      .find((p) => text.includes(p));
    if (hit) partNo = hit;
  }

  if (!partNo) {
    partNo = tokens.find((t) => partLike(t)) || "";
  }

  if (!qty) {
    const nums = tokens.filter((t) => /^\d{1,7}$/.test(t) && t !== partNo);
    if (nums.length) qty = nums[nums.length - 1];
  }

  // 无显式工单号时：整段扫码内容作为工单号留存；有分隔时优先取非部番/非数量段
  if (!workOrder) {
    const other = tokens.find((t) => t !== partNo && t !== String(qty));
    workOrder = other && tokens.length >= 2 ? other : text;
  }

  return {
    workOrder: workOrder || text,
    partNo,
    qty: qty ? String(qty) : "",
  };
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

