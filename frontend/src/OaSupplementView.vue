<template>
  <section class="oa-page">
    <header class="oa-head">
      <div>
        <h2>OA 单号补录</h2>
        <p class="hint">有 OA 后再填。先搜机种 / 日期，点开记录只改 OA 单号，避免和抽检登记混在一起。</p>
      </div>
    </header>

    <div class="toolbar">
      <label class="field">
        <span>机种</span>
        <input v-model.trim="qModel" placeholder="输入机种关键字" @keyup.enter="search" />
      </label>
      <label class="field">
        <span>日期起</span>
        <input type="date" v-model="qFrom" />
      </label>
      <label class="field">
        <span>日期止</span>
        <input type="date" v-model="qTo" />
      </label>
      <label class="check">
        <input type="checkbox" v-model="onlyNg" @change="search" />
        仅不良（NG）
      </label>
      <button type="button" class="primary" :disabled="loading" @click="search">
        {{ loading ? "查询中…" : "查询" }}
      </button>
    </div>

    <p v-if="message" :class="ok ? 'ok' : 'err'">{{ message }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>序号</th>
            <th>日期</th>
            <th>机种</th>
            <th>判定</th>
            <th>现象</th>
            <th>现有 OA</th>
            <th>补录 OA 单号</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length">
            <td colspan="8" class="empty">{{ loading ? "加载中…" : "暂无记录，请调整条件查询" }}</td>
          </tr>
          <tr v-for="row in rows" :key="rowKey(row)">
            <td>{{ row["序号"] ?? "—" }}</td>
            <td>{{ row["日期"] ?? "—" }}</td>
            <td>{{ row["机种"] || row["系列"] || "—" }}</td>
            <td>
              <span :class="judgeClass(row['判定'])">{{ row["判定"] || "—" }}</span>
            </td>
            <td class="phen">{{ row["现象"] || "—" }}</td>
            <td>{{ row["OA单号"] || "—" }}</td>
            <td>
              <input
                v-model="drafts[rowKey(row)]"
                class="oa-input"
                placeholder="输入 OA 单号"
                :disabled="!canUpdate || savingId === rowKey(row)"
              />
            </td>
            <td>
              <button
                type="button"
                class="ghost"
                :disabled="!canUpdate || savingId === rowKey(row)"
                @click="saveOa(row)"
              >
                {{ savingId === rowKey(row) ? "保存中…" : "保存" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="foot">共 {{ total }} 条 · 显示前 {{ rows.length }} 条</p>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { authFetch } from "./api.js";

const props = defineProps({
  workbookId: String,
  sheet: String,
  canUpdate: { type: Boolean, default: false },
});

const rows = ref([]);
const total = ref(0);
const loading = ref(false);
const savingId = ref("");
const message = ref("");
const ok = ref(true);
const qModel = ref("");
const qFrom = ref("");
const qTo = ref("");
const onlyNg = ref(true);
const drafts = reactive({});

function rowKey(row) {
  return String(row?.["序号"] ?? row?.__idx ?? "");
}

function judgeClass(v) {
  const s = String(v || "").toUpperCase();
  if (s.startsWith("NG")) return "ng";
  if (s.startsWith("OK")) return "okj";
  return "";
}

function buildFilters() {
  const filters = {};
  if (qModel.value) {
    filters["机种"] = { type: "contains", value: qModel.value };
  }
  if (qFrom.value || qTo.value) {
    filters["日期"] = {
      type: "date_range",
      start: qFrom.value || undefined,
      end: qTo.value || undefined,
    };
  }
  return filters;
}

async function search() {
  if (!props.workbookId || !props.sheet) return;
  loading.value = true;
  message.value = "";
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/query`, {
      method: "POST",
      body: JSON.stringify({
        sheet: props.sheet,
        filters: buildFilters(),
        offset: 0,
        limit: 200,
        sort: { field: "日期", direction: "desc" },
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "查询失败");
    let list = data.rows || [];
    if (onlyNg.value) {
      list = list.filter((r) => {
        const j = String(r["判定"] || "").toUpperCase();
        return j.includes("NG");
      });
    }
    rows.value = list;
    total.value = onlyNg.value ? list.length : data.total ?? list.length;
    for (const r of list) {
      const k = rowKey(r);
      drafts[k] = r["OA单号"] != null ? String(r["OA单号"]) : "";
    }
  } catch (err) {
    ok.value = false;
    message.value = String(err.message || err);
    rows.value = [];
  } finally {
    loading.value = false;
  }
}

async function saveOa(row) {
  const k = rowKey(row);
  const oa = String(drafts[k] ?? "").trim();
  if (!oa) {
    ok.value = false;
    message.value = "请填写 OA 单号";
    return;
  }
  if (row["序号"] == null) {
    ok.value = false;
    message.value = "无法识别行序号";
    return;
  }
  savingId.value = k;
  message.value = "";
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
      method: "PUT",
      body: JSON.stringify({
        sheet: props.sheet,
        row_key: "序号",
        row_id: row["序号"],
        values: { OA单号: oa },
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    ok.value = true;
    message.value = `已保存序号 ${row["序号"]} 的 OA 单号`;
    if (data.row) {
      const idx = rows.value.findIndex((r) => rowKey(r) === k);
      if (idx >= 0) rows.value[idx] = { ...rows.value[idx], ...data.row };
    }
  } catch (err) {
    ok.value = false;
    message.value = String(err.message || err);
  } finally {
    savingId.value = "";
  }
}

onMounted(search);
watch(() => props.sheet, search);
</script>

<style scoped>
.oa-page {
  padding: 16px 18px 24px;
  display: grid;
  gap: 14px;
}
.oa-head h2 {
  margin: 0 0 4px;
  font-size: 16px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: end;
}
.field {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.field input {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 7px 8px;
  min-width: 140px;
}
.check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
  padding-bottom: 8px;
}
.primary {
  background: var(--primary);
  color: #fff;
  border: 0;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
}
.ghost {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
}
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid #f1f5f9;
  text-align: left;
  vertical-align: middle;
}
th {
  background: #f8fafc;
  color: var(--muted);
  font-weight: 600;
  position: sticky;
  top: 0;
}
.phen {
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.oa-input {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 5px 8px;
  min-width: 140px;
  width: 100%;
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 24px !important;
}
.ng {
  color: #b91c1c;
  font-weight: 650;
}
.okj {
  color: #15803d;
  font-weight: 650;
}
.ok {
  color: var(--ok);
  font-size: 13px;
}
.err {
  color: var(--danger);
  font-size: 13px;
}
.foot {
  margin: 0;
  font-size: 11px;
  color: #94a3b8;
}
</style>
