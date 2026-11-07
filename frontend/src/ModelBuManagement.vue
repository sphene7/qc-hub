<template>
  <div class="bu-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <input v-model="q" class="search" placeholder="搜索部番，如 F113" @keyup.enter="reload" />
        <select v-model="unitFilter" class="select" @change="reload">
          <option value="">全部事业部</option>
          <option v-for="u in businessUnits" :key="u" :value="u">{{ u }}</option>
        </select>
        <button class="btn-secondary" @click="reload">查询</button>
      </div>
      <div class="toolbar-right">
        <span class="count">共 {{ total }} 条</span>
        <span v-if="!canEdit" class="readonly-hint">只读（需要类别管理/异常处理权限才能维护）</span>
        <template v-if="canEdit">
          <input
            ref="fileInput"
            type="file"
            accept=".xls,.xlsx,.csv,.tsv,.txt"
            class="file-input"
            @change="onImportFile"
          />
          <button class="btn-secondary" :disabled="importing" @click="pickImportFile">
            {{ importing ? "导入中…" : "导入对照表" }}
          </button>
          <button class="btn-primary" @click="openCreate">+ 新增部番</button>
        </template>
      </div>
    </div>

    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>部番</th>
            <th>基型</th>
            <th>事业部</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="4" class="empty">加载中…</td></tr>
          <tr v-else-if="!items.length"><td colspan="4" class="empty">没有匹配的部番</td></tr>
          <template v-else>
            <tr v-for="row in items" :key="row.id">
              <td class="mono">{{ row.model }}</td>
              <td class="muted">{{ row.base_model || '-' }}</td>
              <td><span class="bu-tag">{{ row.business_unit }}</span></td>
              <td class="ops">
                <template v-if="canEdit">
                  <button class="link" @click="openEdit(row)">编辑</button>
                  <button class="link danger" @click="remove(row)">删除</button>
                </template>
                <span v-else class="muted">-</span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <div class="pager">
        <span>第 {{ page }} / {{ pageCount }} 页</span>
        <button class="page-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <button class="page-btn" :disabled="page >= pageCount" @click="goPage(page + 1)">下一页</button>
      </div>
    </div>

    <div v-if="modal.open" class="overlay">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ modal.id ? '编辑部番' : '新增部番' }}</h3>
          <button class="close" @click="closeModal">✕</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>部番<span class="req">*</span></span>
            <input v-model="form.model" placeholder="如：T5724-A1" />
          </label>
          <label class="field">
            <span>事业部<span class="req">*</span></span>
            <input v-model="form.business_unit" list="bu-options" placeholder="如：变焦" />
          </label>
          <datalist id="bu-options">
            <option v-for="u in businessUnits" :key="u" :value="u" />
          </datalist>
          <div v-if="modal.error" class="modal-error">{{ modal.error }}</div>
        </div>
        <div class="modal-foot">
          <button class="btn-secondary" @click="closeModal">取消</button>
          <button class="btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { authFetch } from "./api.js";

const props = defineProps({
  workbookId: { type: String, default: "" },
  canEdit: { type: Boolean, default: false },
});
const apiBase = computed(() =>
  props.workbookId ? `/api/workbooks/${props.workbookId}/sampling/model-bu` : "/api/admin/model-bu",
);

const loading = ref(true);
const saving = ref(false);
const importing = ref(false);
const error = ref("");
const notice = ref("");
const q = ref("");
const unitFilter = ref("");
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const items = ref([]);
const businessUnits = ref([]);
const modal = ref({ open: false, id: null, error: "" });
const form = ref({ model: "", business_unit: "" });
const fileInput = ref(null);

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

async function readJson(res) {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const params = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) });
    if (q.value.trim()) params.set("q", q.value.trim());
    if (unitFilter.value) params.set("business_unit", unitFilter.value);
    const res = await authFetch(`${apiBase.value}?${params.toString()}`);
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "加载失败");
    items.value = data.items || [];
    total.value = data.total || 0;
    businessUnits.value = data.business_units || [];
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function reload() {
  page.value = 1;
  load();
}

function goPage(next) {
  page.value = Math.min(Math.max(1, next), pageCount.value);
  load();
}

function flash(message) {
  notice.value = message;
  setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 4000);
}

function openCreate() {
  form.value = { model: "", business_unit: unitFilter.value || "" };
  modal.value = { open: true, id: null, error: "" };
}

function openEdit(row) {
  form.value = { model: row.model, business_unit: row.business_unit };
  modal.value = { open: true, id: row.id, error: "" };
}

function closeModal() {
  modal.value = { open: false, id: null, error: "" };
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    const url = modal.value.id ? `${apiBase.value}/${modal.value.id}` : apiBase.value;
    const res = await authFetch(url, {
      method: modal.value.id ? "PUT" : "POST",
      body: JSON.stringify(form.value),
    });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "保存失败");
    flash(modal.value.id ? "已更新" : "已新增");
    closeModal();
    await load();
  } catch (err) {
    modal.value.error = err.message;
  } finally {
    saving.value = false;
  }
}

async function remove(row) {
  if (!confirm(`删除「${row.model} → ${row.business_unit}」？`)) return;
  try {
    const res = await authFetch(`${apiBase.value}/${row.id}`, { method: "DELETE" });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "删除失败");
    flash("已删除");
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

function pickImportFile() {
  fileInput.value?.click?.();
}

async function onImportFile(ev) {
  const file = ev.target?.files?.[0];
  if (!file) return;
  importing.value = true;
  error.value = "";
  try {
    const body = new FormData();
    body.append("file", file);
    const res = await authFetch(`${apiBase.value}/import`, { method: "POST", body });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "导入失败");
    flash(
      `已导入 ${data.parsed ?? 0} 行：新增 ${data.added ?? 0}，更新 ${data.updated ?? 0}，共 ${data.total ?? 0} 条`,
    );
    page.value = 1;
    await load();
  } catch (err) {
    error.value = err.message;
  } finally {
    importing.value = false;
    if (ev.target) ev.target.value = "";
  }
}

function onKeydown(ev) {
  if (ev.key === "Escape" && modal.value.open) closeModal();
}
onMounted(() => {
  load();
  window.addEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
.bu-page { display: flex; flex-direction: column; gap: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-left { display: flex; align-items: center; gap: 8px; }
.toolbar-right { display: flex; align-items: center; gap: 10px; }
.search { width: 220px; padding: 8px 12px; border: 1px solid #dce1d6; border-radius: 8px; font-size: 13px; }
.search:focus { outline: none; border-color: #9dbb8a; box-shadow: 0 0 0 3px rgba(84, 130, 53, 0.12); }
.select { padding: 8px 10px; border: 1px solid #dce1d6; border-radius: 8px; font-size: 13px; background: #fff; }
.count { font-size: 12px; color: #8a9086; }
.notice { padding: 8px 12px; border-radius: 8px; background: #eef6ea; color: #3a6b28; font-size: 13px; }
.error { padding: 8px 12px; border-radius: 8px; background: #fdecea; color: #b03a2e; font-size: 13px; }
.table-card { background: #fff; border: 1px solid #e6e8e3; border-radius: 12px; overflow: hidden; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 14px; border-bottom: 1px solid #f0f2ee; text-align: left; white-space: nowrap; }
th { background: #fafbf8; color: #5a6057; font-weight: 600; font-size: 12.5px; }
tbody tr:hover td { background: #f9fbf7; }
.mono { font-family: ui-monospace, Consolas, monospace; color: #3d443a; }
.muted { color: #9aa096; }
.ops { text-align: right; }
.empty { text-align: center; color: #999; padding: 32px; }
.bu-tag { display: inline-block; font-size: 11.5px; padding: 1px 9px; border-radius: 999px; background: #eef3fb; color: #2f6fb3; }
.link { background: none; border: none; color: #5a7a3a; cursor: pointer; font-size: 12.5px; padding: 2px 6px; border-radius: 6px; }
.link:hover { background: #eef6ea; }
.link.danger { color: #c0392b; }
.link.danger:hover { background: #fdecea; }
.pager { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 12px 14px; border-top: 1px solid #f0f2ee; font-size: 12.5px; color: #6f756c; }
.page-btn { padding: 4px 10px; border: 1px solid #dce1d6; border-radius: 6px; background: #fff; font-size: 12px; cursor: pointer; }
.page-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.overlay { position: fixed; inset: 0; background: rgba(24, 30, 20, 0.38); display: flex; align-items: center; justify-content: center; z-index: 60; padding: 20px; }
.modal { background: #fff; border-radius: 12px; width: min(440px, 100%); box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22); overflow: hidden; }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid #eef0ec; }
.modal-head h3 { margin: 0; font-size: 16px; }
.close { background: none; border: none; font-size: 16px; color: #999; cursor: pointer; }
.modal-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 5px; font-size: 13px; }
.field > span { color: #6f756c; }
.field input { padding: 8px 10px; border: 1px solid #dce1d6; border-radius: 8px; font-size: 13px; }
.req { color: #c0392b; margin-left: 2px; }
.modal-error { color: #b03a2e; font-size: 12.5px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid #eef0ec; background: #fbfcfa; }
.btn-primary, .btn-secondary { padding: 6px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #548235; color: #fff; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #fff; border-color: #d6dbcf; color: #444; }
.btn-secondary:disabled { opacity: 0.6; }
.file-input { display: none; }
.readonly-hint { font-size: 12px; color: #9aa096; }
</style>
