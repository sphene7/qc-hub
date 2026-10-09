<template>
  <section class="sampling-view card">
    <div class="view-head">
      <div>
        <h2>抽检数据 · {{ totalRecords }} 行</h2>
        <p class="hint">宽表格式，与 Excel 导出「抽检数据」一致。首列为日期（原 Excel 列名「抽检状况」）。</p>
      </div>
      <div class="head-actions">
        <button
          v-if="canDelete && selectedCount > 0"
          type="button"
          class="danger-btn"
          :disabled="batchDeleting"
          @click="deleteSelectedRows"
        >{{ batchDeleting ? '删除中…' : `删除选中 (${selectedCount})` }}</button>
        <button v-if="canCreate" type="button" class="primary-btn" @click="openCreate">新增</button>
        <div ref="columnPickerRef" class="column-picker-wrap">
          <button type="button" class="ghost-btn" @click="columnsPanelOpen = !columnsPanelOpen">
            列显示
            <span class="col-count-badge">{{ visibleColumnCount }}/{{ allColumns.length }}</span>
          </button>
          <div v-if="columnsPanelOpen" class="column-picker-panel">
            <div class="column-picker-head">
              <span>选择显示的列</span>
              <button type="button" class="link-btn" @click="showAllColumns">全部显示</button>
            </div>
            <div class="column-picker-list">
              <label v-for="col in allColumns" :key="'colpick-' + col" class="column-picker-item">
                <input
                  type="checkbox"
                  :checked="!hiddenColumns.includes(col)"
                  @change="toggleColumnVisibility(col)"
                />
                <span>{{ col }}</span>
              </label>
            </div>
          </div>
        </div>
        <button type="button" class="ghost-btn" :disabled="exporting" @click="exportSheet">
          {{ exporting ? '导出中…' : '导出' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else class="table-wrap">
      <table class="resizable-table">
        <colgroup>
          <col :style="{ width: colWidth('__select__') + 'px' }" />
          <col :style="{ width: colWidth('__date__') + 'px' }" />
          <col v-for="col in visibleColumns" :key="'col-' + col" :style="{ width: colWidth(col) + 'px' }" />
          <col :style="{ width: colWidth('__actions__') + 'px' }" />
        </colgroup>
        <thead>
          <tr>
            <th class="select-col sticky-col resizable-th" :style="{ width: colWidth('__select__') + 'px' }">
              <input
                type="checkbox"
                class="row-select"
                :checked="allPageSelected"
                :indeterminate.prop="somePageSelected && !allPageSelected"
                title="全选本页"
                @change="toggleSelectAllPage"
              />
            </th>
            <th class="sticky-col sticky-col-date resizable-th" :style="{ width: colWidth('__date__') + 'px' }">
              <div class="th-inner">
                <span class="th-label">日期</span>
                <span class="col-sort-arrows">
                  <button type="button" class="col-sort-btn" :class="{ active: sortField === rowKey && sortDirection === 'asc' }" @click="setSort(rowKey, 'asc')">▲</button>
                  <button type="button" class="col-sort-btn" :class="{ active: sortField === rowKey && sortDirection === 'desc' }" @click="setSort(rowKey, 'desc')">▼</button>
                </span>
              </div>
              <span class="col-resizer" @mousedown.prevent="startResize($event, '__date__')" />
            </th>
            <th
              v-for="col in visibleColumns"
              :key="col"
              class="resizable-th"
              :style="{ width: colWidth(col) + 'px' }"
            >
              <div class="th-inner">
                <span class="th-label">{{ col }}</span>
                <span class="col-sort-arrows">
                  <button type="button" class="col-sort-btn" :class="{ active: sortField === col && sortDirection === 'asc' }" @click="setSort(col, 'asc')">▲</button>
                  <button type="button" class="col-sort-btn" :class="{ active: sortField === col && sortDirection === 'desc' }" @click="setSort(col, 'desc')">▼</button>
                </span>
              </div>
              <span class="col-resizer" @mousedown.prevent="startResize($event, col)" />
            </th>
            <th v-if="canUpdate || canDelete" class="actions-col resizable-th" :style="{ width: colWidth('__actions__') + 'px' }">
              <span class="th-label">操作</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in tableData"
            :key="rowSelectKey(row) || row[rowKey]"
            :class="{ 'row-selected': isRowSelected(row) }"
          >
            <td class="select-col sticky-col">
              <input
                type="checkbox"
                class="row-select"
                :checked="isRowSelected(row)"
                @change="toggleRowSelect(row)"
              />
            </td>
            <td class="sticky-col sticky-col-date">{{ formatSamplingDateLabel(row[rowKey]) }}</td>
            <td v-for="col in visibleColumns" :key="col">{{ formatCell(row[col]) }}</td>
            <td v-if="canUpdate || canDelete" class="actions-col">
              <button v-if="canUpdate" type="button" class="icon-btn" title="编辑" @click="openEdit(row)">✏️</button>
              <button v-if="canDelete" type="button" class="icon-btn" title="删除" @click="confirmDelete(row)">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="totalRecords > 0" class="pagination">
      <button type="button" :disabled="currentPage <= 1 || loading" @click="prevPage">上一页</button>
      <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
      <button type="button" :disabled="currentPage >= totalPages || loading" @click="nextPage">下一页</button>
      <label class="page-size">
        每页
        <select v-model.number="pageSize" @change="onPageSizeChange">
          <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
        </select>
        条
      </label>
    </div>

    <!-- Edit / Create dialog -->
    <div v-if="editorOpen" class="modal-backdrop" @mousedown.self="closeEditor">
      <div class="editor-dialog modal-panel">
        <div class="dialog-head">
          <h3>{{ editingRow ? '编辑抽检记录' : '新增抽检记录' }}</h3>
          <button type="button" class="icon-btn" @click="closeEditor">✕</button>
        </div>
        <div class="editor-body">
          <label class="field">
            <span>日期 <i>*</i></span>
            <DateField v-model="editorDate" :disabled="!!editingRow" />
          </label>

          <div class="metric-table-wrap">
            <table class="metric-table">
              <thead>
                <tr>
                  <th class="station-col">工站</th>
                  <th v-for="m in metricHeaders" :key="m">{{ m }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="g in stationGroups" :key="g.name">
                  <td class="station-col">{{ g.name }}</td>
                  <td v-for="m in g.metrics" :key="m.key">
                    <input v-model="editorForm[m.key]" type="text" placeholder="－" :title="m.label" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="dialog-actions">
          <button type="button" class="primary" :disabled="saving" @click="saveEditor">
            {{ saving ? '保存中…' : '保存' }}
          </button>
          <button type="button" class="ghost" @click="closeEditor">取消</button>
          <span v-if="editorMsg" :class="editorOk ? 'ok' : 'err'">{{ editorMsg }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { authFetch, authDownload } from "./api.js";
import DateField from "./DateField.vue";
import {
  formatSamplingDateLabel,
  isoToCnDate,
  resolveEditorDate,
  todayIso,
} from "./dateUtil.js";

const props = defineProps({
  workbookId: String,
  spec: Object,
  canCreate: { type: Boolean, default: true },
  canUpdate: { type: Boolean, default: true },
  canDelete: { type: Boolean, default: true },
});

const rowKey = "抽检状况";
const loading = ref(false);
const saving = ref(false);
const exporting = ref(false);
const tableData = ref([]);
const totalRecords = ref(0);
const currentPage = ref(1);
const pageSize = ref(50);
const pageSizeOptions = [20, 50, 100, 200, 500];
const sortField = ref("抽检状况");
const sortDirection = ref("desc");
const selectedRows = ref(new Map());
const batchDeleting = ref(false);
const editorOpen = ref(false);
const editingRow = ref(null);
const editorForm = reactive({});
const editorDate = ref("");
const editorMsg = ref("");
const editorOk = ref(true);
const hiddenColumns = ref([]);
const columnsPanelOpen = ref(false);
const columnPickerRef = ref(null);

const samplingSheet = computed(() => {
  const sheets = props.spec?.sheets || [];
  return (
    sheets.find((s) => {
      const n = (s.name || "").trim();
      return n === "抽检数据" || (n.startsWith("抽检数据") && !n.includes("展开"));
    }) || null
  );
});

const sheetName = computed(() => samplingSheet.value?.name || "抽检数据");

const allColumns = computed(() => {
  const cols = samplingSheet.value?.columns || [];
  return cols.map((c) => (typeof c === "string" ? c : c.key)).filter((k) => k && k !== rowKey);
});

const visibleColumns = computed(() =>
  allColumns.value.filter((col) => !hiddenColumns.value.includes(col))
);

const visibleColumnCount = computed(() => visibleColumns.value.length);

function columnPrefsKey() {
  return `qc-hub:sampling-col-hidden:${props.workbookId || "default"}`;
}

function loadColumnVisibility() {
  try {
    const raw = localStorage.getItem(columnPrefsKey());
    hiddenColumns.value = raw ? JSON.parse(raw) : [];
  } catch {
    hiddenColumns.value = [];
  }
  const allowed = new Set(allColumns.value);
  hiddenColumns.value = hiddenColumns.value.filter((col) => allowed.has(col));
}

function saveColumnVisibility() {
  try {
    localStorage.setItem(columnPrefsKey(), JSON.stringify(hiddenColumns.value));
  } catch {
    /* ignore */
  }
}

function toggleColumnVisibility(col) {
  const set = new Set(hiddenColumns.value);
  if (set.has(col)) set.delete(col);
  else set.add(col);
  hiddenColumns.value = [...set];
  saveColumnVisibility();
}

function showAllColumns() {
  hiddenColumns.value = [];
  saveColumnVisibility();
}

function onDocumentClick(e) {
  if (!columnsPanelOpen.value) return;
  const el = columnPickerRef.value;
  if (el && !el.contains(e.target)) columnsPanelOpen.value = false;
}

const colWidths = ref({});
const MIN_COL_WIDTH = 52;
const resizing = ref(null);

function estimateColWidth(label) {
  if (label === "__select__") return 36;
  if (label === "__date__") return 88;
  if (label === "__actions__") return 72;
  // 中文约 12px/字 + 内边距与拖拽把手
  return Math.max(MIN_COL_WIDTH, String(label).length * 12 + 24);
}

function colWidth(col) {
  return colWidths.value[col] ?? estimateColWidth(col);
}

function initColWidths() {
  const next = { ...colWidths.value };
  next["__select__"] = next["__select__"] ?? 36;
  next["__date__"] = next["__date__"] ?? 88;
  next["__actions__"] = next["__actions__"] ?? 72;
  for (const col of visibleColumns.value) {
    if (next[col] == null) next[col] = estimateColWidth(col);
  }
  colWidths.value = next;
}

function onResizeMove(e) {
  if (!resizing.value) return;
  const delta = e.clientX - resizing.value.startX;
  const w = Math.max(MIN_COL_WIDTH, resizing.value.startW + delta);
  colWidths.value = { ...colWidths.value, [resizing.value.col]: w };
}

function stopResize() {
  resizing.value = null;
  document.removeEventListener("mousemove", onResizeMove);
  document.removeEventListener("mouseup", stopResize);
  document.body.classList.remove("col-resizing");
}

function startResize(e, col) {
  resizing.value = { col, startX: e.clientX, startW: colWidth(col) };
  document.body.classList.add("col-resizing");
  document.addEventListener("mousemove", onResizeMove);
  document.addEventListener("mouseup", stopResize);
}

const stationGroups = computed(() => {
  const groups = new Map();
  const metricRe = /^(.+?)[-－](抽检数|不良数|不良品|良品数)$/;
  for (const col of allColumns.value) {
    const m = col.match(metricRe);
    if (!m) continue;
    const [, station, metric] = m;
    if (!groups.has(station)) {
      groups.set(station, { name: station, metrics: [] });
    }
    groups.get(station).metrics.push({ key: col, label: metric });
  }
  return [...groups.values()];
});

const metricHeaders = computed(() => {
  const first = stationGroups.value[0];
  return first ? first.metrics.map((m) => m.label) : [];
});

const totalPages = computed(() => Math.max(1, Math.ceil(totalRecords.value / pageSize.value)));

const selectedCount = computed(() => selectedRows.value.size);

const allPageSelected = computed(() => {
  const rows = tableData.value.filter((row) => rowSelectKey(row));
  return rows.length > 0 && rows.every((row) => selectedRows.value.has(rowSelectKey(row)));
});

const somePageSelected = computed(() =>
  tableData.value.some((row) => selectedRows.value.has(rowSelectKey(row)))
);

onMounted(() => {
  loadColumnVisibility();
  initColWidths();
  loadData();
  document.addEventListener("click", onDocumentClick);
});

watch(allColumns, () => initColWidths(), { deep: true });
watch(visibleColumns, () => initColWidths(), { deep: true });

watch(
  () => props.workbookId,
  () => {
    loadColumnVisibility();
    initColWidths();
  },
);

onUnmounted(() => {
  stopResize();
  document.removeEventListener("click", onDocumentClick);
});

function setSort(field, dir) {
  if (sortField.value === field && sortDirection.value === dir) {
    sortField.value = rowKey;
    sortDirection.value = "desc";
  } else {
    sortField.value = field;
    sortDirection.value = dir;
  }
  currentPage.value = 1;
  loadData();
}

function rowSelectKey(row) {
  const id = row[rowKey];
  const dbId = row["__db_id"];
  if (id == null && dbId == null) return "";
  return `${id ?? ""}::${dbId ?? ""}`;
}

function buildDeleteTarget(row) {
  const target = {};
  if (row[rowKey] != null) target.row_id = row[rowKey];
  if (row["__db_id"] != null) target.db_id = row["__db_id"];
  return target;
}

function isRowSelected(row) {
  const key = rowSelectKey(row);
  return key ? selectedRows.value.has(key) : false;
}

function toggleRowSelect(row) {
  const key = rowSelectKey(row);
  if (!key) return;
  const next = new Map(selectedRows.value);
  if (next.has(key)) next.delete(key);
  else next.set(key, buildDeleteTarget(row));
  selectedRows.value = next;
}

function toggleSelectAllPage() {
  const rows = tableData.value.filter((row) => rowSelectKey(row));
  if (!rows.length) return;
  const next = new Map(selectedRows.value);
  if (allPageSelected.value) {
    for (const row of rows) next.delete(rowSelectKey(row));
  } else {
    for (const row of rows) next.set(rowSelectKey(row), buildDeleteTarget(row));
  }
  selectedRows.value = next;
}

function clearRowSelection() {
  selectedRows.value = new Map();
}

function formatCell(v) {
  if (v == null || v === "") return "";
  if (v === "－" || v === "-") return "－";
  return String(v);
}

async function loadData() {
  if (!props.workbookId) return;
  loading.value = true;
  const queryBody = {
    sheet: sheetName.value,
    filters: {},
    offset: (currentPage.value - 1) * pageSize.value,
    limit: pageSize.value,
    sort: sortField.value ? { field: sortField.value, direction: sortDirection.value } : null,
  };
  console.log("[SamplingDataView] query", queryBody);
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/query`, {
      method: "POST",
      body: JSON.stringify(queryBody),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载失败");
    tableData.value = data.rows || [];
    totalRecords.value = data.total || 0;
    console.log("[SamplingDataView] loaded", { total: data.total, rows: tableData.value.length });
  } catch (err) {
    alert(err.message || "加载抽检数据失败");
  } finally {
    loading.value = false;
  }
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--;
    loadData();
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
    loadData();
  }
}

function onPageSizeChange() {
  currentPage.value = 1;
  loadData();
}

function resetEditorForm(row = null) {
  for (const k of Object.keys(editorForm)) delete editorForm[k];
  if (row) {
    const resolved = resolveEditorDate(row[rowKey], props.spec);
    editorForm[rowKey] = resolved.label;
    editorDate.value = resolved.iso;
    console.log("[SamplingDataView] edit form date", resolved);
  } else {
    editorDate.value = todayIso();
    editorForm[rowKey] = isoToCnDate(editorDate.value);
    console.log("[SamplingDataView] new form date default", editorDate.value, editorForm[rowKey]);
  }
  for (const col of allColumns.value) {
    const v = row?.[col];
    editorForm[col] = v == null || v === "" ? "" : String(v);
  }
}

function openCreate() {
  editingRow.value = null;
  editorMsg.value = "";
  resetEditorForm();
  editorOpen.value = true;
}

function openEdit(row) {
  editingRow.value = row;
  editorMsg.value = "";
  resetEditorForm(row);
  editorOpen.value = true;
}

function closeEditor() {
  editorOpen.value = false;
  editingRow.value = null;
}

function editorPayload() {
  const cn = isoToCnDate(editorDate.value);
  const values = {};
  values[rowKey] = cn || editorForm[rowKey]?.trim() || null;
  console.log("[SamplingDataView] editorPayload date", {
    editorDate: editorDate.value,
    cnDate: cn,
    rowKeyValue: values[rowKey],
  });
  for (const col of allColumns.value) {
    const v = editorForm[col];
    values[col] = v === "" || v === undefined ? null : v;
  }
  return values;
}

async function saveEditor() {
  editorMsg.value = "";
  if (!editorDate.value) {
    editorOk.value = false;
    editorMsg.value = "请选择日期";
    console.warn("[SamplingDataView] save blocked: no editorDate");
    return;
  }
  const payload = editorPayload();
  console.log("[SamplingDataView] save", { editing: !!editingRow.value, payloadDate: payload[rowKey] });
  saving.value = true;
  try {
    if (editingRow.value) {
      const rowId = editingRow.value[rowKey];
      const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
        method: "PUT",
        body: JSON.stringify({
          sheet: sheetName.value,
          row_key: rowKey,
          row_id: rowId,
          values: payload,
        }),
      });
      const data = await res.json();
      console.log("[SamplingDataView] PUT response", res.status, data);
      if (!res.ok) throw new Error(data.detail || "保存失败");
    } else {
      const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
        method: "POST",
        body: JSON.stringify({ sheet: sheetName.value, values: payload }),
      });
      const data = await res.json();
      console.log("[SamplingDataView] POST response", res.status, data);
      if (!res.ok) throw new Error(data.detail || "新增失败");
    }
    editorOk.value = true;
    closeEditor();
    await loadData();
  } catch (err) {
    editorOk.value = false;
    editorMsg.value = String(err.message || err);
  } finally {
    saving.value = false;
  }
}

async function performDeleteRows(targets) {
  const payload = { sheet: sheetName.value, row_key: rowKey };
  if (targets.length === 1) {
    Object.assign(payload, targets[0]);
  } else {
    payload.rows = targets;
  }
  const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
    method: "DELETE",
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "删除失败");
  await loadData();
}

async function confirmDelete(row) {
  const id = row[rowKey];
  const dbId = row["__db_id"];
  if (id == null && dbId == null) return;
  const label = formatSamplingDateLabel(id) || `记录#${dbId}`;
  if (!confirm(`确定删除「${label}」这条抽检记录吗？`)) return;
  try {
    await performDeleteRows([buildDeleteTarget(row)]);
    const next = new Map(selectedRows.value);
    next.delete(rowSelectKey(row));
    selectedRows.value = next;
  } catch (err) {
    alert(err.message || "删除失败");
  }
}

async function deleteSelectedRows() {
  const targets = [...selectedRows.value.values()].filter((t) => t.row_id != null || t.db_id != null);
  if (!targets.length) {
    alert("所选行无法识别，请刷新后重试");
    return;
  }
  if (!confirm(`确定删除选中的 ${targets.length} 条抽检记录吗？`)) return;
  batchDeleting.value = true;
  try {
    await performDeleteRows(targets);
    clearRowSelection();
  } catch (err) {
    alert(err.message || "批量删除失败");
  } finally {
    batchDeleting.value = false;
  }
}

async function exportSheet() {
  exporting.value = true;
  try {
    const title = props.spec?.title || "抽检数据";
    await authDownload(
      `/api/workbooks/${props.workbookId}/export`,
      `${title}-抽检数据.xlsx`,
      {
        method: "POST",
        body: JSON.stringify({ mode: "sheet", sheet: sheetName.value }),
        timeout: 120000,
      }
    );
  } catch (err) {
    alert(err.message || "导出失败");
  } finally {
    exporting.value = false;
  }
}
</script>

<style scoped>
.sampling-view { margin-top: 8px; padding: 14px 16px; }
.view-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.view-head h2 { margin: 0 0 4px; font-size: 16px; }
.hint { margin: 0; font-size: 12px; color: var(--muted); }
.head-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ghost-btn {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  color: var(--ink);
  cursor: pointer;
}
.ghost-btn:hover { border-color: var(--primary); color: var(--primary); }
.ghost-btn:disabled { opacity: 0.45; cursor: default; }
.column-picker-wrap { position: relative; }
.col-count-badge {
  margin-left: 4px;
  font-size: 11px;
  color: var(--muted);
}
.column-picker-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 30;
  width: min(320px, 80vw);
  max-height: min(420px, 60vh);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}
.column-picker-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  font-weight: 600;
}
.link-btn {
  border: 0;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.column-picker-list {
  overflow-y: auto;
  padding: 6px 0;
}
.column-picker-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
}
.column-picker-item:hover { background: var(--bg-accent); }
.column-picker-item input { flex-shrink: 0; }
.search {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  min-width: 160px;
}
.loading { padding: 24px; text-align: center; color: var(--muted); }
.table-wrap {
  overflow: auto;
  max-height: calc(100vh - 220px);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.resizable-table {
  border-collapse: separate;
  border-spacing: 0;
  font-size: 11px;
  table-layout: fixed;
  width: max-content;
  min-width: 100%;
}
.resizable-table th,
.resizable-table td {
  border-bottom: 1px solid var(--line);
  border-right: 1px solid var(--line);
  padding: 6px 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-sizing: border-box;
}
.resizable-table th {
  background: var(--bg-accent);
  color: var(--ink);
  font-weight: 650;
  position: sticky;
  top: 0;
  z-index: 2;
  vertical-align: bottom;
}
.resizable-th {
  position: relative;
  padding-right: 10px;
}
.th-label {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}
.col-resizer {
  position: absolute;
  top: 0;
  right: 0;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  user-select: none;
  touch-action: none;
}
.col-resizer:hover,
.col-resizer:active {
  background: rgba(124, 92, 191, 0.35);
}
.sticky-col {
  position: sticky;
  left: 0;
  z-index: 3;
  background: var(--card);
  box-shadow: 2px 0 4px rgba(107, 74, 168, 0.06);
}
.sticky-col-date {
  left: 36px;
  z-index: 4;
}
thead .sticky-col { background: var(--bg-accent); z-index: 5; }
thead .sticky-col-date { z-index: 6; }
.actions-col {
  position: sticky;
  right: 0;
  background: var(--card);
  z-index: 2;
  text-align: center;
}
thead .actions-col { background: var(--bg-accent); z-index: 4; }
.icon-btn { border: 0; background: transparent; cursor: pointer; padding: 2px 4px; }
.pagination {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 12px;
  font-size: 13px;
}
.pagination button {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 4px 10px;
  cursor: pointer;
}
.pagination button:disabled { opacity: 0.45; cursor: default; }
.page-size {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}
.page-size select {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 3px 6px;
  background: #fff;
}
.editor-dialog {
  width: min(720px, 96vw);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}
.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.dialog-head h3 { margin: 0; font-size: 15px; }
.editor-body {
  padding: 10px 14px;
  overflow-y: auto;
  flex: 1;
}
.field { display: grid; gap: 4px; font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.field i { color: var(--danger); font-style: normal; }
.field input {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 8px;
  max-width: 200px;
}
.metric-table-wrap {
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: auto;
  max-height: calc(88vh - 160px);
}
.metric-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.metric-table th,
.metric-table td {
  border: 1px solid var(--line);
  padding: 4px 6px;
  text-align: center;
}
.metric-table thead th {
  background: var(--bg-accent);
  font-weight: 600;
  font-size: 11px;
  white-space: nowrap;
}
.metric-table .station-col {
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
  background: #fafafa;
  min-width: 88px;
}
.metric-table tbody td:not(.station-col) {
  padding: 2px 4px;
  min-width: 64px;
}
.metric-table input {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 4px 6px;
  font-size: 12px;
  text-align: center;
}
.th-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}
.col-sort-arrows {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.col-sort-btn {
  border: 0;
  background: transparent;
  font-size: 9px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  color: var(--muted);
}
.col-sort-btn.active {
  color: var(--primary);
}
.select-col {
  width: 36px;
  min-width: 36px;
  text-align: center;
  vertical-align: middle;
}
.row-select {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: var(--primary);
}
tr.row-selected td {
  background: rgba(124, 92, 191, 0.06);
}
.danger-btn {
  background: #dc2626;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.danger-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.primary-btn {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.dialog-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
}
.primary {
  background: var(--primary);
  color: #fff;
  border: 0;
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
}
.ghost {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}
.ok { color: var(--ok); font-size: 13px; }
.err { color: var(--danger); font-size: 13px; }
</style>
