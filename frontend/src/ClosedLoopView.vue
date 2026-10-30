<template>
  <section class="loop-page">
    <header class="loop-head">
      <div>
        <h2>闭环分析</h2>
        <p class="hint">
          步骤③：指定质控 → 责任单位/人 → 临时对策 / 根因 / 永久对策 → 改善确认与结案。
          结案天数根据结案日期自动计算。
        </p>
      </div>
    </header>

    <div class="toolbar">
      <label class="field">
        <span>机种</span>
        <input v-model.trim="qModel" placeholder="搜机种" @keyup.enter="search" />
      </label>
      <label class="field">
        <span>OA 单号</span>
        <input v-model.trim="qOa" placeholder="可选" @keyup.enter="search" />
      </label>
      <label class="check">
        <input type="checkbox" v-model="onlyOpen" @change="search" />
        仅未结案
      </label>
      <button type="button" class="primary" :disabled="loading" @click="search">
        {{ loading ? "查询中…" : "查询" }}
      </button>
    </div>

    <div class="layout">
      <aside class="list">
        <div
          v-for="row in rows"
          :key="rowKey(row)"
          class="list-item"
          :class="{ on: selectedKey === rowKey(row) }"
          @click="selectRow(row)"
        >
          <div class="list-top">
            <strong>#{{ row["序号"] ?? "—" }}</strong>
            <span :class="judgeClass(row['判定'])">{{ row["判定"] || "—" }}</span>
          </div>
          <div class="list-mid">{{ row["机种"] || row["系列"] || "—" }} · {{ row["日期"] || "—" }}</div>
          <div class="list-sub">{{ row["现象"] || "无现象" }}</div>
          <div class="list-meta">
            <span>{{ row["OA单号"] ? `OA ${row["OA单号"]}` : "无 OA" }}</span>
            <span>{{ row["结案日期"] ? "已结案" : "未结案" }}</span>
          </div>
        </div>
        <p v-if="!rows.length" class="empty">{{ loading ? "加载中…" : "暂无记录" }}</p>
      </aside>

      <div class="panel" v-if="selected">
        <div class="panel-head">
          <h3>分析表单 · 序号 {{ selected["序号"] }}</h3>
          <span class="readonly">{{ selected["机种"] || selected["系列"] }} · {{ selected["现象"] }}</span>
        </div>

        <div class="grid">
          <label class="field">
            <span>OA 单号 <i class="opt">只读，请在 OA 补录页填写</i></span>
            <input :value="selected['OA单号'] || ''" disabled />
          </label>
          <label class="field">
            <span>指定质控公司</span>
            <ComboField v-model="form['指定质控公司']" :options="opt('指定质控公司')" placeholder="如汉华" />
          </label>
          <label class="field">
            <span>责任单位</span>
            <ComboField v-model="form['责任单位']" :options="opt('责任单位')" placeholder="产线 / 技术等" />
          </label>
          <label class="field">
            <span>责任人</span>
            <ComboField v-model="form['责任人']" :options="opt('责任人')" placeholder="分析责任人" />
          </label>
          <label class="field full">
            <span>临时对策</span>
            <RichTextField v-model="form['临时对策']" :rows="3" />
          </label>
          <label class="field full">
            <span>根因分析 <i class="opt">可插图</i></span>
            <RichTextField v-model="form['根因分析']" :rows="4" />
          </label>
          <label class="field full">
            <span>永久对策</span>
            <RichTextField v-model="form['永久对策']" :rows="3" />
          </label>
          <label class="field full">
            <span>改善后确认 <i class="opt">可插改善图</i></span>
            <RichTextField v-model="form['改善后确认']" :rows="4" />
          </label>
          <label class="field">
            <span>结案日期</span>
            <DateField v-model="form['结案日期']" @update:model-value="onCloseDate" />
          </label>
          <label class="field">
            <span>结案天数 <i class="opt">自动</i></span>
            <input :value="closeDaysDisplay" disabled />
          </label>
        </div>

        <div class="actions">
          <button type="button" class="primary" :disabled="!canUpdate || saving" @click="save">
            {{ saving ? "保存中…" : "保存闭环" }}
          </button>
          <button type="button" class="ghost" :disabled="saving" @click="fillCloseToday">结案日期=今天</button>
          <span v-if="message" :class="ok ? 'ok' : 'err'">{{ message }}</span>
        </div>
      </div>

      <div v-else class="panel empty-panel">
        <p>从左侧选择一条不良记录开始闭环分析</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { authFetch } from "./api.js";
import ComboField from "./ComboField.vue";
import DateField from "./DateField.vue";
import RichTextField from "./RichTextField.vue";
import { todayDateString, toDateInputValue } from "./dateField.js";

const CLOSE_FIELDS = [
  "指定质控公司",
  "责任单位",
  "责任人",
  "临时对策",
  "根因分析",
  "永久对策",
  "改善后确认",
  "结案日期",
];

const props = defineProps({
  workbookId: String,
  sheet: String,
  spec: Object,
  canUpdate: { type: Boolean, default: false },
});

const rows = ref([]);
const loading = ref(false);
const saving = ref(false);
const message = ref("");
const ok = ref(true);
const qModel = ref("");
const qOa = ref("");
const onlyOpen = ref(true);
const selected = ref(null);
const selectedKey = ref("");
const form = reactive({});
const optionCache = reactive({});

const closeDaysDisplay = computed(() => {
  const days = calcCloseDays(selected.value?.["日期"], form["结案日期"]);
  return days == null ? "—" : String(days);
});

function rowKey(row) {
  return String(row?.["序号"] ?? "");
}

function judgeClass(v) {
  const s = String(v || "").toUpperCase();
  if (s.startsWith("NG")) return "ng";
  if (s.startsWith("OK")) return "okj";
  return "";
}

function opt(key) {
  const set = new Set(optionCache[key] || []);
  const cur = String(form[key] || "").trim();
  if (cur) set.add(cur);
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

function calcCloseDays(start, end) {
  const a = toDateInputValue(start);
  const b = toDateInputValue(end);
  if (!a || !b) return null;
  const d0 = new Date(`${a}T00:00:00`);
  const d1 = new Date(`${b}T00:00:00`);
  if (Number.isNaN(d0.getTime()) || Number.isNaN(d1.getTime())) return null;
  return Math.max(0, Math.round((d1 - d0) / 86400000));
}

function buildFilters() {
  const filters = {};
  if (qModel.value) filters["机种"] = { type: "contains", value: qModel.value };
  if (qOa.value) filters["OA单号"] = { type: "contains", value: qOa.value };
  return filters;
}

function collectOptions(list) {
  for (const key of ["指定质控公司", "责任单位", "责任人"]) {
    const set = new Set(optionCache[key] || []);
    for (const r of list) {
      const v = String(r[key] || "").trim();
      if (v) set.add(v);
    }
    optionCache[key] = [...set];
  }
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
    list = list.filter((r) => {
      const j = String(r["判定"] || "").toUpperCase();
      return j.includes("NG");
    });
    if (onlyOpen.value) {
      list = list.filter((r) => !String(r["结案日期"] || "").trim());
    }
    rows.value = list;
    collectOptions(list);
    if (selectedKey.value) {
      const keep = list.find((r) => rowKey(r) === selectedKey.value);
      if (keep) selectRow(keep);
      else {
        selected.value = null;
        selectedKey.value = "";
      }
    }
  } catch (err) {
    ok.value = false;
    message.value = String(err.message || err);
    rows.value = [];
  } finally {
    loading.value = false;
  }
}

function selectRow(row) {
  selected.value = row;
  selectedKey.value = rowKey(row);
  for (const k of CLOSE_FIELDS) {
    const v = row[k];
    if (k === "结案日期") form[k] = toDateInputValue(v);
    else form[k] = v == null ? "" : String(v);
  }
  message.value = "";
}

function onCloseDate() {
  // display computed via closeDaysDisplay
}

function fillCloseToday() {
  form["结案日期"] = todayDateString();
}

async function save() {
  if (!selected.value || selected.value["序号"] == null) return;
  saving.value = true;
  message.value = "";
  try {
    const values = {};
    for (const k of CLOSE_FIELDS) {
      const v = form[k];
      values[k] = v === "" || v == null ? null : v;
    }
    const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
      method: "PUT",
      body: JSON.stringify({
        sheet: props.sheet,
        row_key: "序号",
        row_id: selected.value["序号"],
        values,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    ok.value = true;
    message.value = "闭环已保存";
    if (data.row) {
      const k = rowKey(data.row);
      const idx = rows.value.findIndex((r) => rowKey(r) === k);
      if (idx >= 0) rows.value[idx] = { ...rows.value[idx], ...data.row };
      selectRow(data.row);
    }
  } catch (err) {
    ok.value = false;
    message.value = String(err.message || err);
  } finally {
    saving.value = false;
  }
}

onMounted(search);
watch(() => props.sheet, search);
</script>

<style scoped>
.loop-page {
  padding: 16px 18px 24px;
  display: grid;
  gap: 14px;
  height: 100%;
  min-height: 0;
}
.loop-head h2 {
  margin: 0 0 4px;
  font-size: 16px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  max-width: 720px;
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
  background: #fff;
  color: var(--ink);
  width: 100%;
  box-sizing: border-box;
}
.field i.opt {
  color: #94a3b8;
  font-style: normal;
  font-weight: 400;
  font-size: 10px;
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
  padding: 8px 12px;
  cursor: pointer;
}
.layout {
  display: grid;
  grid-template-columns: minmax(240px, 300px) 1fr;
  gap: 12px;
  min-height: 0;
  align-items: stretch;
}
.list {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  overflow: auto;
  max-height: calc(100vh - 220px);
}
.list-item {
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
}
.list-item:hover {
  background: #f8fafc;
}
.list-item.on {
  background: color-mix(in srgb, var(--primary) 8%, #fff);
  border-left: 3px solid var(--primary);
}
.list-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}
.list-mid {
  margin-top: 2px;
  font-size: 12px;
  color: var(--ink);
}
.list-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.list-meta {
  margin-top: 4px;
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
}
.panel {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  padding: 14px 16px;
  overflow: auto;
  max-height: calc(100vh - 220px);
}
.empty-panel {
  display: grid;
  place-items: center;
  color: var(--muted);
  font-size: 13px;
}
.panel-head {
  margin-bottom: 12px;
}
.panel-head h3 {
  margin: 0 0 4px;
  font-size: 14px;
}
.readonly {
  font-size: 12px;
  color: var(--muted);
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.field.full {
  grid-column: 1 / -1;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-top: 16px;
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
.empty {
  padding: 20px;
  text-align: center;
  color: var(--muted);
  font-size: 12px;
}
@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .list,
  .panel {
    max-height: none;
  }
}
</style>
