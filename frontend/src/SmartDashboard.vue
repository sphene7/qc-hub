<template>
  <div
    class="smart-dashboard"
    :class="{
      'has-workbench': viewMode === 'operations' && !!design?.main_table,
      'analytics-view': viewMode === 'analytics',
      'chart-theme-screen': showAnalytics && chartTheme === 'screen',
    }"
  >
    <div v-if="showHeader" class="dashboard-header">
      <h1>{{ design?.business_understanding?.type || '业务看板' }}</h1>
      <p class="purpose">{{ design?.business_understanding?.purpose }}</p>
    </div>

    <div v-if="showAnalytics && analyticsDateField" class="analytics-toolbar card">
      <label class="range-field">
        <span>统计日期</span>
        <div class="range-inputs">
          <input v-model="analyticsDateFrom" type="date" @change="applyAnalyticsDateRange" />
          <span class="range-sep">至</span>
          <input v-model="analyticsDateTo" type="date" @change="applyAnalyticsDateRange" />
        </div>
      </label>
      <button type="button" class="ghost-btn" @click="loadDashboardData">刷新</button>
      <ChartThemePicker v-model="chartTheme" />
      <button
        v-if="analyticsDateFrom || analyticsDateTo"
        type="button"
        class="ghost-btn"
        @click="clearAnalyticsDateRange"
      >清除日期</button>
      <span v-if="analyticsRangeHint" class="hint">{{ analyticsRangeHint }}</span>
    </div>

    <!-- KPI Cards（趋势分析页） -->
    <section v-if="showAnalytics && design?.kpis?.length" class="kpis-section">
      <div class="kpi-card" v-for="kpi in design.kpis" :key="kpi.id">
        <div class="kpi-label">{{ kpi.label }}</div>
        <div class="kpi-value">{{ formatKpiValue(kpi) }}</div>
        <div class="kpi-trend" v-if="kpi.trend">
          <span :class="kpi.trend > 0 ? 'up' : 'down'">
            {{ kpi.trend > 0 ? '↑' : '↓' }} {{ Math.abs(kpi.trend).toFixed(1) }}%
          </span>
        </div>
      </div>
    </section>

    <!-- Charts（趋势分析页） -->
    <section v-if="showAnalytics && design?.charts?.length" class="charts-section">
      <div 
        v-for="chart in design.charts" 
        :key="chart.id" 
        class="chart-card card"
      >
        <h3>{{ chart.title }}</h3>
        <ChartView :option="buildChartOption(chart)" :theme="chartTheme" />
      </div>
    </section>

    <!-- 问题清单：明细表 + 可收起左侧录入面板 -->
    <section
      v-if="showOperations && design?.main_table"
      :class="['workbench', 'card', { 'table-fullscreen': tableFullscreen, 'has-entry': entryPanelVisible && entrySheet?.form?.enabled, 'table-only': !entryPanelVisible }]"
    >
      <div class="workbench-layout">
        <aside v-if="canCreate && entryPanelVisible && entrySheet?.form?.enabled" class="entry-panel">
          <EntryForm
            ref="sidebarEntryRef"
            :workbook-id="workbookId"
            :sheet="entrySheet"
            layout="sidebar"
            @saved="onEntrySaved"
          />
        </aside>

        <div class="table-panel">
          <div class="panel-topbar table-topbar">
            <h2>{{ design.main_table.sheet }} 明细 · {{ tableCountText }}</h2>
            <div class="table-actions">
              <button
                v-if="canCreate && entrySheet?.form?.enabled && !entryPanelVisible"
                type="button"
                class="primary-btn"
                title="弹窗录入"
                @click="entryModalOpen = true"
              >添加数据</button>
              <button
                v-if="canCreate && entrySheet?.form?.enabled"
                type="button"
                class="entry-panel-toggle"
                :class="{ on: entryPanelVisible }"
                :title="entryPanelVisible ? '收起左侧录入面板' : '展开侧栏，在表格旁录入'"
                @click="toggleEntryPanel"
              >
                <span class="toggle-icon" aria-hidden="true">{{ entryPanelVisible ? '◧' : '◨' }}</span>
                {{ entryPanelVisible ? '收起侧栏' : '侧栏录入' }}
              </button>
              <button
                v-if="canDeleteRow && selectedCount > 0"
                type="button"
                class="danger-btn"
                :disabled="batchDeleting"
                @click="deleteSelectedRows"
              >{{ batchDeleting ? '删除中…' : `删除选中 (${selectedCount})` }}</button>
              <button type="button" class="ghost-btn" @click="filtersOpen = !filtersOpen">
                {{ filtersOpen ? '隐藏筛选' : '显示筛选' }}
              </button>
              <div ref="columnPickerRef" class="column-picker-wrap">
                <button type="button" class="ghost-btn" @click="columnsPanelOpen = !columnsPanelOpen">
                  列显示
                  <span class="col-count-badge">{{ visibleColumnCount }}/{{ allDisplayColumns.length }}</span>
                </button>
                <div v-if="columnsPanelOpen" class="column-picker-panel">
                  <div class="column-picker-head">
                    <span>选择显示的列</span>
                    <button type="button" class="link-btn" @click="showAllColumns">全部显示</button>
                  </div>
                  <div class="column-picker-list">
                    <label v-for="col in allDisplayColumns" :key="'colpick-' + col" class="column-picker-item">
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
              <button type="button" class="ghost-btn" @click="toggleTableFullscreen">
                {{ tableFullscreen ? '退出全屏' : '全屏' }}
              </button>
              <button type="button" class="ghost-btn" :disabled="tableExporting" @click="exportData">
                {{ tableExporting ? '导出中…' : '导出' }}
              </button>
            </div>
          </div>

          <div v-show="filtersOpen" class="table-filter-bar">
            <div class="filter-grid">
              <div
                v-for="item in filterBarItems"
                :key="'filter-' + item.key"
                :class="['filter-item', { 'five-m-item': item.kind === 'fiveM' }]"
              >
                <label>{{ item.label }}</label>
                <div v-if="item.kind === 'fiveM'" class="five-m-filter">
                  <button
                    v-for="col in fiveMColumns"
                    :key="col"
                    type="button"
                    class="five-m-filter-btn"
                    :class="{ on: fiveMSelections[col] }"
                    :title="col"
                    @click="toggleFiveMFilter(col)"
                  >{{ fiveMShortLabel(col) }}</button>
                </div>
                <div v-else-if="columnFilterType(item.key) === 'date'" class="date-range">
                  <DateField
                    v-model="columnDateFilters[item.key + '_from']"
                    class="filter-control"
                    @update:model-value="debouncedApplyFilters"
                  />
                  <span class="date-sep">—</span>
                  <DateField
                    v-model="columnDateFilters[item.key + '_to']"
                    class="filter-control"
                    @update:model-value="debouncedApplyFilters"
                  />
                </div>
                <select
                  v-else-if="columnFilterType(item.key) === 'enum' && groupedOptions(item.key)"
                  v-model="columnFilters[item.key]"
                  class="filter-control"
                  @change="applyFilters"
                >
                  <option value="">全部</option>
                  <optgroup v-for="(items, cat) in groupedOptions(item.key)" :key="cat" :label="cat">
                    <option v-for="opt in items" :key="opt" :value="opt">{{ opt }}</option>
                  </optgroup>
                </select>
                <select
                  v-else-if="columnFilterType(item.key) === 'enum'"
                  v-model="columnFilters[item.key]"
                  class="filter-control"
                  @change="applyFilters"
                >
                  <option value="">全部</option>
                  <option v-for="opt in columnMeta[item.key]?.options || []" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <input
                  v-else
                  type="text"
                  v-model="columnFilters[item.key]"
                  class="filter-control"
                  placeholder="全部"
                  @keyup.enter="applyFilters"
                />
              </div>
            </div>
            <div class="filter-bar-actions">
              <button type="button" class="primary-btn" @click="applyFilters">查询筛选</button>
              <button type="button" class="ghost-btn" @click="resetFilters">重置筛选</button>
              <span v-if="filtersActive" class="filter-count-badge">筛选结果：{{ totalRecords }} 条</span>
            </div>
          </div>

          <p class="table-hint">
            点击 ▲▼ 排序 · 修改筛选项后自动搜索<template v-if="closeStatusColumn"> · 「是否结案」列可选状态</template>
          </p>

      <div v-if="loading" class="table-loading">加载中…</div>
      <div
        v-else
        ref="tableWrapperRef"
        class="table-wrapper"
      >
        <table class="data-table">
          <thead>
            <tr class="header-labels">
              <th v-if="canDeleteRow" class="select-col">
                <input
                  type="checkbox"
                  class="row-select"
                  :checked="allPageSelected"
                  :indeterminate.prop="somePageSelected && !allPageSelected"
                  title="全选本页"
                  @change="toggleSelectAllPage"
                />
              </th>
              <th v-for="col in displayColumns" :key="col">
                <div class="th-inner">
                  <span class="col-label">{{ col }}</span>
                  <span class="col-sort-arrows">
                    <button
                      type="button"
                      class="col-sort-btn asc"
                      :class="{ active: sortField === col && sortDirection === 'asc' }"
                      title="升序"
                      @click.stop="setSort(col, 'asc')"
                    >▲</button>
                    <button
                      type="button"
                      class="col-sort-btn desc"
                      :class="{ active: sortField === col && sortDirection === 'desc' }"
                      title="降序"
                      @click.stop="setSort(col, 'desc')"
                    >▼</button>
                  </span>
                </div>
              </th>
              <th v-if="hasActions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!tableData.length">
              <td :colspan="displayColumns.length + (hasActions ? 1 : 0) + (canDeleteRow ? 1 : 0)" class="empty-row">
                暂无数据
              </td>
            </tr>
            <tr 
              v-for="(row, idx) in tableData" 
              :key="idx"
              :class="[getRowClass(row), { 'row-selected': isRowSelected(row) }]"
            >
              <td v-if="canDeleteRow" class="select-col">
                <input
                  type="checkbox"
                  class="row-select"
                  :checked="isRowSelected(row)"
                  @change="toggleRowSelect(row)"
                />
              </td>
              <td
                v-for="col in displayColumns"
                :key="col"
                :class="{ 'readonly-cell': isReadonlyTableColumn(col) }"
                :title="cellHoverTitle(row[col], col)"
              >
                <select
                  v-if="col === closeStatusColumn"
                  class="close-status-select"
                  :class="closeStatusClass(row[col])"
                  :value="normalizeCloseStatus(row[col])"
                  :disabled="statusUpdating === rowRowId(row)"
                  @click.stop
                  @change="(e) => setCloseStatus(row, e.target.value)"
                >
                  <option v-for="opt in closeStatusOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
                <span v-else class="cell-text">{{ formatCellValue(row[col], col) }}</span>
              </td>
              <td v-if="hasActions" class="actions-cell">
                <button 
                  v-if="canUpdate && design.main_table.actions?.includes('edit')"
                  class="icon-btn"
                  @click="editRow(row)"
                >
                  ✏️
                </button>
                <button 
                  v-if="canDeleteRow"
                  class="icon-btn"
                  @click="deleteRow(row)"
                >
                  🗑️
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <!-- Pagination -->
      <div v-if="totalRecords > 0" class="pagination">
        <button type="button" :disabled="currentPage <= 1 || loading" @click="prevPage">上一页</button>
        <span>第 {{ currentPage }} / {{ totalPages }} 页 · 共 {{ totalRecords }} 条</span>
        <button type="button" :disabled="currentPage >= totalPages || loading" @click="nextPage">下一页</button>
        <label class="page-size">
          每页
          <select v-model.number="pageSize" @change="onPageSizeChange">
            <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
          </select>
          条
        </label>
      </div>
        </div>
      </div>
    </section>

    <div v-if="entryModalOpen" class="modal-backdrop" @mousedown.self="entryModalOpen = false">
      <div class="entry-modal modal-panel">
        <div class="entry-modal-head">
          <h3>添加数据 · {{ design?.main_table?.sheet || '问题清单' }}</h3>
          <button type="button" class="icon-btn" @click="entryModalOpen = false">✕</button>
        </div>
        <div class="entry-modal-body">
          <EntryForm
            ref="modalEntryRef"
            v-if="entrySheet?.form?.enabled"
            :workbook-id="workbookId"
            :sheet="entrySheet"
            layout="grid"
            @saved="onModalEntrySaved"
          />
        </div>
      </div>
    </div>

    <EditRowDialog
      :visible="editDialogOpen"
      :workbook-id="workbookId"
      :sheet="entrySheet"
      :row="editingRow"
      :row-key="tableRowKey"
      title="编辑问题记录"
      @close="editDialogOpen = false"
      @saved="onEditSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { authFetch, authDownload } from './api';
import ChartView from './ChartView.vue';
import ChartThemePicker from './ChartThemePicker.vue';
import EntryForm from './EntryForm.vue';
import EditRowDialog from './EditRowDialog.vue';
import DateField from './DateField.vue';
import { formatMonthDisplay } from './monthField.js';

const props = defineProps({
  workbookId: String,
  design: Object,  // AI-generated dashboard design
  spec: Object,    // Workbook spec
  viewMode: {
    type: String,
    default: 'operations', // operations | analytics
  },
  initialEntryPanelVisible: {
    type: Boolean,
    default: true,
  },
  canCreate: { type: Boolean, default: true },
  canUpdate: { type: Boolean, default: true },
  canDelete: { type: Boolean, default: true },
});

const emit = defineEmits(['refresh']);

const showOperations = computed(() => props.viewMode === 'operations');
const showAnalytics = computed(() => props.viewMode === 'analytics');
const showHeader = computed(() => showAnalytics.value || !props.design?.main_table);

const ANALYTICS_DATE_FIELDS = ['日期', '投诉日期', '发生日期', '反馈日期', '抽检状况'];

const analyticsDateFrom = ref('');
const analyticsDateTo = ref('');
const chartTheme = ref(localStorage.getItem('qc-hub:chart-theme') === 'screen' ? 'screen' : 'default');
watch(chartTheme, (value) => localStorage.setItem('qc-hub:chart-theme', value));

const analyticsDateField = computed(() => {
  const cols = props.design?.main_table?.display_columns || [];
  for (const field of ANALYTICS_DATE_FIELDS) {
    if (cols.includes(field)) return field;
  }
  for (const filter of props.design?.filters || []) {
    const field = filter?.field;
    if (field && (filter.type === 'date' || ANALYTICS_DATE_FIELDS.includes(field))) {
      return field;
    }
  }
  for (const kpi of props.design?.kpis || []) {
    const sheet = kpi?.source_sheet;
    if (sheet && props.spec?.sheets?.[sheet]?.columns) {
      for (const field of ANALYTICS_DATE_FIELDS) {
        if (props.spec.sheets[sheet].columns.includes(field)) return field;
      }
    }
  }
  return ANALYTICS_DATE_FIELDS[0];
});

const analyticsRangeHint = computed(() => {
  const from = analyticsDateFrom.value;
  const to = analyticsDateTo.value;
  if (!from && !to) return '';
  if (from && to) return `已筛选：${from} 至 ${to}`;
  if (from) return `已筛选：${from} 起`;
  return `已筛选：至 ${to}`;
});

// State
const filterValues = ref({});
const kpiValues = ref({});
const chartData = ref({});
const tableData = ref([]);
const totalRecords = ref(0);
const allRecordsTotal = ref(0);
const filtersActive = ref(false);
const currentPage = ref(1);
const pageSize = ref(50);
const pageSizeOptions = [20, 50, 100, 200, 500];
const loading = ref(false);
const tableFullscreen = ref(false);
const tableWrapperRef = ref(null);
const columnFilters = ref({});
const columnDateFilters = ref({});
const columnMeta = ref({});
const lookupMaps = ref({});
const sortField = ref('');
const sortDirection = ref('asc');
const statusUpdating = ref(null);
const tableExporting = ref(false);
const editDialogOpen = ref(false);
const editingRow = ref(null);
const entryPanelVisible = ref(true);
const entryModalOpen = ref(false);
const sidebarEntryRef = ref(null);
const modalEntryRef = ref(null);

function refreshLookups() {
  sidebarEntryRef.value?.refreshLookups?.();
  modalEntryRef.value?.refreshLookups?.();
}

function reloadMainTable() {
  loadMainTable();
  refreshLookups();
}

defineExpose({ refreshLookups, reloadMainTable });

function entryPanelStorageKey() {
  return props.workbookId ? `qc-entry-panel:${props.workbookId}` : null;
}

function readEntryPanelVisible() {
  const key = entryPanelStorageKey();
  if (key) {
    try {
      const stored = localStorage.getItem(key);
      if (stored === '0') return false;
      if (stored === '1') return true;
    } catch (_) {
      /* ignore */
    }
  }
  return props.initialEntryPanelVisible !== false;
}

function persistEntryPanelVisible(visible) {
  const key = entryPanelStorageKey();
  if (!key) return;
  try {
    localStorage.setItem(key, visible ? '1' : '0');
  } catch (_) {
    /* ignore */
  }
}

function toggleEntryPanel() {
  entryPanelVisible.value = !entryPanelVisible.value;
  persistEntryPanelVisible(entryPanelVisible.value);
  if (entryPanelVisible.value) entryModalOpen.value = false;
}
const filtersOpen = ref(false);
const columnsPanelOpen = ref(false);
const columnPickerRef = ref(null);
const hiddenColumns = ref([]);
const fiveMSelections = ref({});
const selectedRows = ref(new Map());

// 问题点描述是问题清单最重要的检索字段，保留为可搜索文本筛选。
const DEFAULT_FILTER_EXCLUDED = ['序号', '月份'];

const filterExcludedColumns = computed(() => {
  const fromDesign = props.design?.main_table?.filter_excluded_columns || [];
  return new Set([...DEFAULT_FILTER_EXCLUDED, ...fromDesign]);
});

function isFiveMColumn(col) {
  return /^(人-|机-|料-|法|环境-|环-)/.test(col || '');
}

function fiveMShortLabel(col) {
  if (col.startsWith('人-')) return '人';
  if (col.startsWith('机-')) return '机';
  if (col.startsWith('料-')) return '料';
  if (col.startsWith('法')) return '法';
  if (col.startsWith('环境-') || col.startsWith('环-')) return '环';
  return col.slice(0, 1);
}

function initFiveMSelections() {
  const next = {};
  for (const col of fiveMColumns.value) {
    next[col] = fiveMSelections.value[col] || false;
  }
  fiveMSelections.value = next;
}

function toggleFiveMFilter(col) {
  fiveMSelections.value = {
    ...fiveMSelections.value,
    [col]: !fiveMSelections.value[col],
  };
}

const fiveMColumns = computed(() => displayColumns.value.filter(isFiveMColumn));

const filterBarItems = computed(() => {
  const items = [];
  let fiveMAdded = false;
  for (const col of displayColumns.value) {
    if (filterExcludedColumns.value.has(col)) continue;
    if (isFiveMColumn(col)) {
      if (!fiveMAdded) {
        items.push({ kind: 'fiveM', key: '__fiveM__', label: '人机料法环' });
        fiveMAdded = true;
      }
      continue;
    }
    items.push({ kind: 'column', key: col, label: col });
  }
  return items;
});
const batchDeleting = ref(false);
const filtersReady = ref(false);

const closeStatusColumn = computed(() =>
  displayColumns.value.find((c) => c === '是否结案') || null
);

const readonlyTableColumns = new Set(['结案日期']);
const LONG_TEXT_COLUMNS = new Set(['问题点描述', '投诉内容', '暂定对策']);

function isReadonlyTableColumn(col) {
  return readonlyTableColumns.has(col);
}

// Computed
const allDisplayColumns = computed(() => props.design?.main_table?.display_columns || []);

const displayColumns = computed(() =>
  allDisplayColumns.value.filter((col) => !hiddenColumns.value.includes(col))
);

const visibleColumnCount = computed(() => displayColumns.value.length);

function columnPrefsKey() {
  return `qc-hub:col-hidden:${props.workbookId || "default"}`;
}

function loadColumnVisibility() {
  try {
    const raw = localStorage.getItem(columnPrefsKey());
    hiddenColumns.value = raw ? JSON.parse(raw) : [];
  } catch {
    hiddenColumns.value = [];
  }
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

const mainSheetSpec = computed(() => {
  const target = props.design?.main_table?.sheet?.trim();
  if (!target || !props.spec?.sheets) return null;
  return props.spec.sheets.find((s) => s.name?.trim() === target) || null;
});

const entrySheet = computed(() => mainSheetSpec.value);

const tableRowKey = computed(() => {
  const cols = entrySheet.value?.columns || [];
  if (cols.some((c) => c.key === "序号")) return "序号";
  return "__db_id";
});

const resolvedFilters = computed(() => {
  const designFilters = props.design?.filters || [];
  const sheetFilters = mainSheetSpec.value?.filters || [];
  const byField = Object.fromEntries(sheetFilters.map((f) => [f.field, f]));

  const merged = designFilters.map((f) => {
    const src = byField[f.field] || {};
    return {
      ...f,
      label: f.label || src.label || f.field,
      type: f.type || src.type || 'enum',
      options: f.options?.length ? f.options : (src.options || []),
      min: f.min || src.min,
      max: f.max || src.max,
    };
  });

  const seen = new Set(merged.map((f) => f.field));
  for (const f of sheetFilters) {
    if (!seen.has(f.field)) {
      merged.push({ ...f });
    }
  }
  return merged;
});

const hasActions = computed(() => {
  return props.design?.main_table?.actions?.length > 0;
});

const canDeleteRow = computed(() => {
  if (!props.canDelete) return false;
  const actions = props.design?.main_table?.actions || [];
  return actions.includes("delete") || actions.includes("edit");
});

const selectedCount = computed(() => selectedRows.value.size);

const allPageSelected = computed(() => {
  const rows = tableData.value.filter((row) => rowSelectKey(row));
  return rows.length > 0 && rows.every((row) => selectedRows.value.has(rowSelectKey(row)));
});

const somePageSelected = computed(() =>
  tableData.value.some((row) => selectedRows.value.has(rowSelectKey(row)))
);

const totalPages = computed(() => {
  return Math.max(1, Math.ceil((totalRecords.value || 0) / pageSize.value));
});

const tableCountText = computed(() => {
  if (filtersActive.value) {
    const all = allRecordsTotal.value || totalRecords.value;
    return `筛选 ${totalRecords.value} 条 / 共 ${all} 条`;
  }
  return `共 ${totalRecords.value} 行`;
});

// Initialize filters from design
onMounted(async () => {
  entryPanelVisible.value = readEntryPanelVisible();
  loadColumnVisibility();
  if (showOperations.value) {
    initializeFilters();
    initializeColumnFilters();
    initFiveMSelections();
  }
  window.addEventListener('keydown', onWindowKeydown);
  document.addEventListener('click', onDocumentClick);
  await loadDashboardData();
  filtersReady.value = true;
});

onUnmounted(() => {
  window.removeEventListener('keydown', onWindowKeydown);
  document.removeEventListener('click', onDocumentClick);
  document.body.classList.remove('table-fs-open');
});

watch(
  () => props.workbookId,
  () => {
    entryPanelVisible.value = readEntryPanelVisible();
    loadColumnVisibility();
  },
);

function initializeColumnFilters() {
  const next = {};
  const dateNext = {};
  for (const col of displayColumns.value) {
    next[col] = columnFilters.value[col] || '';
    dateNext[`${col}_from`] = columnDateFilters.value[`${col}_from`] || '';
    dateNext[`${col}_to`] = columnDateFilters.value[`${col}_to`] || '';
  }
  columnFilters.value = next;
  columnDateFilters.value = dateNext;
}

function columnFilterType(col) {
  return columnMeta.value[col]?.type || 'text';
}

function groupedOptions(col) {
  const lookupKey = columnMeta.value[col]?.lookup;
  if (!lookupKey) return null;
  const grouped = lookupMaps.value[lookupKey]?.grouped;
  if (!grouped || !Object.keys(grouped).length) return null;
  return grouped;
}

async function loadColumnMeta() {
  const sheet = props.design?.main_table?.sheet;
  if (!props.workbookId || !sheet) return;
  try {
    const res = await authFetch(
      `/api/workbooks/${props.workbookId}/column-meta?sheet=${encodeURIComponent(sheet)}`
    );
    if (!res.ok) return;
    const data = await res.json();
    columnMeta.value = data.columns || {};
    lookupMaps.value = data.lookups || {};
  } catch (err) {
    console.warn('Failed to load column meta:', err);
  }
}

function onWindowKeydown(e) {
  if (e.key === 'Escape' && tableFullscreen.value) {
    tableFullscreen.value = false;
    document.body.classList.remove('table-fs-open');
  }
}

function toggleTableFullscreen() {
  tableFullscreen.value = !tableFullscreen.value;
  document.body.classList.toggle('table-fs-open', tableFullscreen.value);
}

function initializeFilters() {
  const next = {};
  for (const filter of resolvedFilters.value) {
    if (filter.type === 'date_range') {
      next[filter.field + '_from'] = '';
      next[filter.field + '_to'] = '';
    } else {
      next[filter.field] = '';
    }
  }
  filterValues.value = next;
}

function resetFilters() {
  initializeFilters();
  clearColumnFilters(false);
  const clearedFiveM = {};
  for (const col of fiveMColumns.value) clearedFiveM[col] = false;
  fiveMSelections.value = clearedFiveM;
  sortField.value = '';
  sortDirection.value = 'asc';
  filtersActive.value = false;
  applyFilters();
}

function clearColumnFilters(reload = true) {
  const next = {};
  const dateNext = {};
  for (const col of displayColumns.value) {
    next[col] = '';
    dateNext[`${col}_from`] = '';
    dateNext[`${col}_to`] = '';
  }
  columnFilters.value = next;
  columnDateFilters.value = dateNext;
  if (reload) {
    currentPage.value = 1;
    loadMainTable();
  }
}

async function loadDashboardData() {
  if (!props.workbookId || !props.design) return;
  
  loading.value = true;
  
  try {
    if (showAnalytics.value) {
      await loadKPIs();
      await loadCharts();
    }
    if (showOperations.value) {
      await loadColumnMeta();
      await loadAllRecordsTotal();
      await loadMainTable();
    }
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  } finally {
    loading.value = false;
  }
}

async function loadKPIs() {
  if (!props.design?.kpis) return;
  
  // For each KPI, calculate value from data
  for (const kpi of props.design.kpis) {
    try {
      const value = await calculateKPI(kpi);
      kpiValues.value[kpi.id] = value;
    } catch (err) {
      console.error(`Failed to calculate KPI ${kpi.id}:`, err);
      kpiValues.value[kpi.id] = 0;
    }
  }
}

async function calculateKPI(kpi) {
  // Query the source sheet with filters
  const res = await authFetch(`/api/workbooks/${props.workbookId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sheet: kpi.source_sheet,
      filters: buildFiltersPayload(),
      offset: 0,
      limit: 10000,  // Get all for aggregation
    }),
  });
  
  const data = await res.json();
  const rows = data.rows || [];
  
  // Apply calculation
  const calcType = kpi.calculation?.type || 'count';
  
  if (calcType === 'count') {
    return rows.length;
  } else if (calcType === 'sum' && kpi.calculation?.field) {
    return rows.reduce((sum, row) => sum + (parseFloat(row[kpi.calculation.field]) || 0), 0);
  } else if (calcType === 'avg' && kpi.calculation?.field) {
    const sum = rows.reduce((s, row) => s + (parseFloat(row[kpi.calculation.field]) || 0), 0);
    return rows.length > 0 ? sum / rows.length : 0;
  } else if (calcType === 'rate' && kpi.calculation?.numerator && kpi.calculation?.denominator) {
    const num = rows.reduce((s, row) => s + (parseFloat(row[kpi.calculation.numerator]) || 0), 0);
    const den = rows.reduce((s, row) => s + (parseFloat(row[kpi.calculation.denominator]) || 0), 0);
    return den > 0 ? (num / den) * 100 : 0;
  }
  
  return 0;
}

async function loadCharts() {
  if (!props.design?.charts) return;
  
  for (const chart of props.design.charts) {
    try {
      const data = await loadChartData(chart);
      chartData.value[chart.id] = data;
    } catch (err) {
      console.error(`Failed to load chart ${chart.id}:`, err);
    }
  }
}

async function loadChartData(chart) {
  const res = await authFetch(`/api/workbooks/${props.workbookId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sheet: chart.source_sheet,
      filters: buildFiltersPayload(),
      offset: 0,
      limit: 10000,
    }),
  });
  
  const result = await res.json();
  return result.rows || [];
}

async function loadAllRecordsTotal() {
  if (!props.design?.main_table?.sheet) return;
  const res = await authFetch(`/api/workbooks/${props.workbookId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sheet: props.design.main_table.sheet,
      filters: {},
      offset: 0,
      limit: 1,
    }),
  });
  if (res.ok) {
    const result = await res.json();
    allRecordsTotal.value = result.total ?? 0;
  }
}

async function loadMainTable() {
  if (!props.design?.main_table?.sheet) return;
  
  const queryBody = {
    sheet: props.design.main_table.sheet,
    filters: buildFiltersPayload(),
    sort: sortField.value ? { field: sortField.value, direction: sortDirection.value } : null,
    offset: (currentPage.value - 1) * pageSize.value,
    limit: pageSize.value,
  };
  const res = await authFetch(`/api/workbooks/${props.workbookId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(queryBody),
  });
  
  if (!res.ok) {
    const errText = await res.text();
    console.error('[SmartDashboard] query failed', res.status, errText);
    tableData.value = [];
    totalRecords.value = 0;
    return;
  }

  const result = await res.json();
  tableData.value = result.rows || [];
  totalRecords.value = result.total ?? tableData.value.length;
}

function buildFiltersPayload() {
  const payload = {};
  
  for (const [key, value] of Object.entries(filterValues.value)) {
    if (!value) continue;
    
    if (key.endsWith('_from') || key.endsWith('_to')) {
      const field = key.replace(/_from$|_to$/, '');
      if (!payload[field]) payload[field] = { type: 'date_range' };
      if (key.endsWith('_from')) payload[field].start = value;
      if (key.endsWith('_to')) payload[field].end = value;
    } else {
      payload[key] = [value];
    }
  }

  const activeFiveM = fiveMColumns.value.filter((col) => fiveMSelections.value[col]);
  if (activeFiveM.length) {
    payload.__fiveM__ = {
      type: 'five_m',
      active: activeFiveM,
    };
  }

  for (const [field, value] of Object.entries(columnFilters.value)) {
    if (value === '' || value == null) continue;
    if (isFiveMColumn(field) || filterExcludedColumns.value.has(field)) continue;
    const meta = columnMeta.value[field];
    if (meta?.type === 'enum') {
      payload[field] = [value];
    } else {
      const trimmed = String(value).trim();
      if (trimmed) {
        payload[field] = { type: 'contains', value: trimmed };
      }
    }
  }

  for (const col of displayColumns.value) {
    if (columnFilterType(col) !== 'date') continue;
    const from = columnDateFilters.value[`${col}_from`];
    const to = columnDateFilters.value[`${col}_to`];
    if (from || to) {
      payload[col] = { type: 'date_range', start: from || undefined, end: to || undefined };
    }
  }

  if (showAnalytics.value && analyticsDateField.value && (analyticsDateFrom.value || analyticsDateTo.value)) {
    payload[analyticsDateField.value] = {
      type: 'date_range',
      start: analyticsDateFrom.value || undefined,
      end: analyticsDateTo.value || undefined,
    };
  }
  
  return payload;
}

function clearAnalyticsDateRange() {
  analyticsDateFrom.value = '';
  analyticsDateTo.value = '';
  applyAnalyticsDateRange();
}

async function applyAnalyticsDateRange() {
  if (!showAnalytics.value) return;
  await loadKPIs();
  await loadCharts();
}

function setSort(col, direction) {
  if (sortField.value === col && sortDirection.value === direction) {
    sortField.value = '';
    sortDirection.value = 'asc';
  } else {
    sortField.value = col;
    sortDirection.value = direction;
  }
  currentPage.value = 1;
  loadMainTable();
}

function onPageSizeChange() {
  currentPage.value = 1;
  loadMainTable();
}

function rowRowId(row) {
  return row['序号'] ?? row['__row_id'] ?? JSON.stringify(row);
}

function rowSelectKey(row) {
  const rowId = row['序号'];
  const dbId = row['__db_id'];
  if (rowId == null && dbId == null) return '';
  return `${rowId ?? ''}::${dbId ?? ''}`;
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

function buildDeleteTarget(row) {
  const target = {};
  if (row['序号'] != null) target.row_id = row['序号'];
  if (row['__db_id'] != null) target.db_id = row['__db_id'];
  return target;
}

const closeStatusOptions = [
  { value: '待选择', label: '待选择' },
  { value: 'Open', label: 'Open（未结案）' },
  { value: 'Close', label: 'Close（已结案）' },
];

function isClosedStatus(val) {
  const s = String(val || '').trim();
  return s === 'Close' || s === '已结案' || s.toLowerCase() === 'close';
}

function isOpenStatus(val) {
  const s = String(val || '').trim();
  return s === 'Open' || s.toLowerCase() === 'open' || s === '未结案';
}

function normalizeCloseStatus(val) {
  if (isClosedStatus(val)) return 'Close';
  if (isOpenStatus(val)) return 'Open';
  return '待选择';
}

function closeStatusClass(val) {
  const norm = normalizeCloseStatus(val);
  if (norm === 'Close') return 'st-close';
  if (norm === 'Open') return 'st-open';
  return 'st-pending';
}

async function setCloseStatus(row, next) {
  const col = closeStatusColumn.value;
  if (!col || col !== '是否结案' || !props.workbookId) return;
  const rowId = row['序号'];
  if (rowId == null) {
    alert('无法识别行序号');
    return;
  }
  const normalized = normalizeCloseStatus(next);
  if (normalizeCloseStatus(row[col]) === normalized) return;

  const token = rowRowId(row);
  statusUpdating.value = token;
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sheet: props.design?.main_table?.sheet,
        row_key: '序号',
        row_id: rowId,
        field: col,
        value: normalized,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '更新失败');
    const idx = tableData.value.findIndex((r) => r['序号'] === rowId);
    if (idx >= 0 && data.row) {
      tableData.value[idx] = { ...tableData.value[idx], ...data.row };
    } else {
      await loadMainTable();
    }
  } catch (err) {
    alert(err.message || '更新结案状态失败');
  } finally {
    statusUpdating.value = null;
  }
}

function applyFilters() {
  currentPage.value = 1;
  filtersActive.value = Object.keys(buildFiltersPayload()).length > 0;
  loadMainTable();
}

let debounceTimer;
function debouncedApplyFilters() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(applyFilters, 500);
}

function formatKpiValue(kpi) {
  const value = kpiValues.value[kpi.id] || 0;
  
  if (kpi.format === 'percent') {
    return value.toFixed(1) + '%';
  } else if (kpi.format === 'int') {
    return Math.round(value).toLocaleString();
  } else {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
}

const CHART_COLORS = ['#7c5cbf', '#9b6fd4', '#2d8a62', '#b45309', '#6b4aa8', '#c0392b', '#0891b2', '#ca8a04', '#9333ea', '#059669'];

function buildChartOption(chart) {
  const data = chartData.value[chart.id] || [];
  const aggregated = aggregateChartData(data, chart);
  let chartType = chart.type || 'bar';
  // AI 有时把分布图标成 bar，自动纠正为 pie
  if (chartType !== 'pie' && chart.aggregation === 'count' && !chart.y_field) {
    if ((chart.title || '').includes('分布') || (chart.title || '').includes('占比')) {
      chartType = 'pie';
    }
  }

  // 饼图：每块不同颜色
  if (chartType === 'pie') {
    const pieData = aggregated.labels.map((name, i) => ({
      name: String(name),
      value: aggregated.values[i] ?? 0,
    }));
    return {
      color: CHART_COLORS,
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: {
        type: 'scroll',
        orient: 'vertical',
        right: 10,
        top: 20,
        bottom: 20,
      },
      series: [{
        name: chart.title,
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['40%', '50%'],
        data: pieData.map((d, i) => ({
          ...d,
          itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] },
        })),
        label: { formatter: '{b}\n{d}%' },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' },
        },
      }],
    };
  }

  // 折线图 / 柱状图
  const isLine = chartType === 'line';
  const manyLabels = aggregated.labels.length > 6;
  return {
    color: CHART_COLORS,
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, bottom: manyLabels ? 80 : 50, top: 30 },
    xAxis: {
      type: 'category',
      data: aggregated.labels,
      axisLabel: {
        rotate: manyLabels ? 35 : 0,
        interval: 0,
        fontSize: 11,
        width: 72,
        overflow: 'truncate',
      },
    },
    yAxis: { type: 'value' },
    dataZoom: manyLabels ? [{ type: 'slider', start: 0, end: 50, bottom: 10 }] : undefined,
    series: [{
      type: isLine ? 'line' : 'bar',
      data: aggregated.values,
      smooth: isLine,
      barMaxWidth: 36,
      itemStyle: isLine ? undefined : {
        color: (params) => CHART_COLORS[params.dataIndex % CHART_COLORS.length],
      },
      areaStyle: isLine ? { opacity: 0.08 } : undefined,
    }],
  };
}

function aggregateChartData(data, chart) {
  const groups = {};

  for (const row of data) {
    const key = row[chart.x_field] ?? '未知';
    const label = String(key).trim() || '未知';
    if (!groups[label]) groups[label] = [];
    groups[label].push(row);
  }

  let labels = Object.keys(groups);
  let values = labels.map((label) => {
    const group = groups[label];
    if (chart.aggregation === 'count') return group.length;
    if (chart.aggregation === 'sum' && chart.y_field) {
      return group.reduce((sum, row) => sum + (parseFloat(row[chart.y_field]) || 0), 0);
    }
    if (chart.aggregation === 'avg' && chart.y_field) {
      const sum = group.reduce((s, row) => s + (parseFloat(row[chart.y_field]) || 0), 0);
      return group.length > 0 ? sum / group.length : 0;
    }
    return group.length;
  });

  // 类别过多时只保留 Top N，其余合并为「其他」
  const MAX_CATEGORIES = 10;
  if (labels.length > MAX_CATEGORIES) {
    const paired = labels.map((l, i) => ({ label: l, value: values[i] }));
    paired.sort((a, b) => b.value - a.value);
    const top = paired.slice(0, MAX_CATEGORIES);
    const rest = paired.slice(MAX_CATEGORIES);
    const restSum = rest.reduce((s, x) => s + x.value, 0);
    labels = top.map((x) => x.label);
    values = top.map((x) => x.value);
    if (restSum > 0) {
      labels.push('其他');
      values.push(restSum);
    }
  }

  return { labels, values };
}

function formatDateOnly(value) {
  if (value == null || value === '') return '';
  const s = String(value).trim();
  const m = s.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s].*)?$/);
  return m ? m[1] : s;
}

function formatCellRaw(value, col = '') {
  if (value == null || value === '') return '-';
  if (col === '月份' || /^\d{1,2}月$/.test(String(value).trim())) {
    return formatMonthDisplay(value);
  }
  const dateOnly = formatDateOnly(value);
  if (dateOnly && /^\d{4}-\d{2}-\d{2}$/.test(dateOnly)) {
    return dateOnly;
  }
  if (typeof value === 'number') {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  let text = String(value);
  if (/!\[[^\]]*\]\(data:image\//.test(text) || /<img[\s>]/i.test(text)) {
    text = text
      .replace(/!\[[^\]]*\]\([^)]+\)/g, '[图片]')
      .replace(/<img[^>]*>/gi, '[图片]');
  }
  return text;
}

function formatCellValue(value, col = '') {
  const text = formatCellRaw(value, col);
  if (text === '-') return text;
  return text.length > 120 ? `${text.slice(0, 120)}…` : text;
}

function cellHoverTitle(value, col = '') {
  const full = formatCellRaw(value, col);
  if (isReadonlyTableColumn(col)) {
    return full !== '-' ? full : '请在编辑中修改';
  }
  if (full === '-') return '';
  if (LONG_TEXT_COLUMNS.has(col)) return full;
  const display = formatCellValue(value, col);
  return full !== display ? full : '';
}

function getRowClass(row) {
  // Custom row styling based on data
  // E.g., highlight overdue items, closed items, etc.
  return '';
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--;
    loadMainTable();
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
    loadMainTable();
  }
}

function editRow(row) {
  editingRow.value = row;
  editDialogOpen.value = true;
}

async function deleteRow(row) {
  const key = tableRowKey.value;
  const rowId = row[key];
  const dbId = row['__db_id'];
  if (rowId == null && dbId == null) {
    alert('无法识别行标识');
    return;
  }
  const label = key === '__db_id' ? `记录 #${rowId}` : `${key} ${rowId}`;
  if (!confirm(`确定删除${label} 这条记录吗？`)) return;
  try {
    await performDeleteRows([buildDeleteTarget(row)]);
    const next = new Map(selectedRows.value);
    next.delete(rowSelectKey(row));
    selectedRows.value = next;
  } catch (err) {
    alert(err.message || '删除失败');
  }
}

async function deleteSelectedRows() {
  const targets = [...selectedRows.value.values()].filter((t) => t.row_id != null || t.db_id != null);
  if (!targets.length) {
    alert('所选行无法识别，请刷新后重试');
    return;
  }
  if (!confirm(`确定删除选中的 ${targets.length} 条记录吗？`)) return;
  batchDeleting.value = true;
  try {
    await performDeleteRows(targets);
    clearRowSelection();
  } catch (err) {
    alert(err.message || '批量删除失败');
  } finally {
    batchDeleting.value = false;
  }
}

async function performDeleteRows(targets) {
  const payload = {
    sheet: props.design?.main_table?.sheet,
    row_key: '序号',
  };
  if (targets.length === 1 && (targets[0].row_id != null || targets[0].db_id != null)) {
    Object.assign(payload, targets[0]);
  } else {
    payload.rows = targets;
  }
  const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
    method: 'DELETE',
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '删除失败');
  await loadMainTable();
  emit('refresh', data);
}

async function onEditSaved(data) {
  editDialogOpen.value = false;
  editingRow.value = null;
  const rowId = data?.row?.['序号'];
  if (rowId != null) {
    const idx = tableData.value.findIndex((r) => r['序号'] === rowId);
    if (idx >= 0 && data.row) {
      tableData.value[idx] = { ...tableData.value[idx], ...data.row };
    } else {
      await loadMainTable();
    }
  } else {
    await loadMainTable();
  }
  emit('refresh', data);
}

async function exportData() {
  const sheet = props.design?.main_table?.sheet;
  if (!props.workbookId || !sheet) {
    alert('无法导出：未找到主表');
    return;
  }
  tableExporting.value = true;
  try {
    const title = props.spec?.title || props.design?.title || '明细';
    await authDownload(
      `/api/workbooks/${props.workbookId}/export`,
      `${title}-当前筛选.xlsx`,
      {
        method: 'POST',
        body: JSON.stringify({
          mode: 'filtered',
          sheet,
          filters: buildFiltersPayload(),
          sort: sortField.value
            ? { field: sortField.value, direction: sortDirection.value }
            : null,
        }),
        timeout: 120000,
      },
    );
  } catch (err) {
    alert(err.message || '导出失败');
  } finally {
    tableExporting.value = false;
  }
}

async function onEntrySaved(data) {
  if (data?.form && entrySheet.value) {
    entrySheet.value.form = data.form;
    if (data.filters) entrySheet.value.filters = data.filters;
    entrySheet.value.row_count = data.row_count;
  }
  await loadColumnMeta();
  // 新记录在末尾：按序号降序并回到第 1 页，确保刚录入的行可见
  sortField.value = '序号';
  sortDirection.value = 'desc';
  currentPage.value = 1;
  await loadDashboardData();
  emit('refresh', data);
}

async function onModalEntrySaved(data) {
  entryModalOpen.value = false;
  await onEntrySaved(data);
}

// Watch design / spec changes
watch(
  () => [props.design, props.spec, props.workbookId, props.viewMode],
  () => {
    if (props.design && props.workbookId) {
      currentPage.value = 1;
      if (showOperations.value) {
        initializeFilters();
        initializeColumnFilters();
      }
      loadDashboardData();
    }
  },
  { deep: true }
);

watch(displayColumns, () => {
  filtersReady.value = false;
  initializeColumnFilters();
  initFiveMSelections();
  filtersReady.value = true;
});

watch(columnFilters, () => {
  if (!filtersReady.value || !showOperations.value) return;
  debouncedApplyFilters();
}, { deep: true });

watch(columnDateFilters, () => {
  if (!filtersReady.value || !showOperations.value) return;
  debouncedApplyFilters();
}, { deep: true });

watch(fiveMSelections, () => {
  if (!filtersReady.value || !showOperations.value) return;
  debouncedApplyFilters();
}, { deep: true });
</script>

<style scoped>
.smart-dashboard {
  padding: 0;
  max-width: none;
  margin: 0;
}

.smart-dashboard.has-workbench .dashboard-header {
  text-align: left;
  margin-bottom: 0.5rem;
  padding: 0 2px;
}

.smart-dashboard.has-workbench .dashboard-header h1 {
  font-size: 1.125rem;
  display: inline;
  margin: 0 0.75rem 0 0;
}

.smart-dashboard.has-workbench .purpose {
  display: inline;
  font-size: 0.8125rem;
}

.smart-dashboard.has-workbench .kpis-section {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.smart-dashboard.has-workbench .kpi-card {
  padding: 0.625rem 0.75rem;
}

.smart-dashboard.has-workbench .kpi-value {
  font-size: 1.375rem;
}

.smart-dashboard.has-workbench .charts-section {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.smart-dashboard.has-workbench .chart-card {
  padding: 0.75rem;
  margin-bottom: 0;
}

.smart-dashboard.has-workbench .chart-card h3 {
  font-size: 0.9375rem;
  margin-bottom: 0.5rem;
}

.analytics-toolbar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  margin-bottom: 12px;
}

.analytics-toolbar label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.analytics-toolbar input[type="date"] {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 14px;
}

.analytics-toolbar .range-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.analytics-toolbar .range-sep {
  font-size: 13px;
  color: var(--muted);
}

.analytics-toolbar .hint {
  color: var(--muted);
  font-size: 13px;
}

.smart-dashboard.analytics-view {
  padding: 0 2px;
}

.smart-dashboard.analytics-view .dashboard-header {
  text-align: left;
  margin-bottom: 0.75rem;
}

.smart-dashboard.analytics-view .dashboard-header h1 {
  font-size: 1.125rem;
  margin: 0 0 0.25rem;
}

.smart-dashboard.analytics-view .purpose {
  font-size: 0.8125rem;
  margin: 0;
}

.smart-dashboard.analytics-view .kpis-section {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.625rem;
  margin-bottom: 0.75rem;
}

.smart-dashboard.analytics-view .kpi-card {
  padding: 0.75rem;
}

.smart-dashboard.analytics-view .kpi-value {
  font-size: 1.5rem;
}

.smart-dashboard.analytics-view .charts-section {
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0;
}

.smart-dashboard.analytics-view .chart-card {
  padding: 1rem;
  margin-bottom: 0;
  min-height: 320px;
}

.smart-dashboard.analytics-view .chart-card h3 {
  font-size: 1rem;
  margin-bottom: 0.75rem;
}

.dashboard-header {
  text-align: center;
  margin-bottom: 2rem;
}

.dashboard-header h1 {
  font-size: 2rem;
  margin: 0 0 0.5rem 0;
  color: #1f2937;
}

.purpose {
  color: #6b7280;
  font-size: 1rem;
}

.card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 1.5rem;
}

.entry-page {
  margin-top: 8px;
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(42, 36, 56, 0.42);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px 16px;
  overflow-y: auto;
}
.entry-modal {
  width: min(920px, 96vw);
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0;
}
.entry-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.entry-modal-head h3 {
  margin: 0;
  font-size: 15px;
}
.entry-modal .icon-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  color: var(--muted);
}
.entry-modal-body {
  overflow-y: auto;
  flex: 1;
  padding: 0 4px 12px;
}
.entry-modal-body :deep(.entry-card),
.entry-modal-body :deep(.entry) {
  border: 0;
  box-shadow: none;
  margin: 0;
  padding: 8px 12px;
}
.entry-modal-body :deep(.entry-head) {
  display: none;
}

.has-workbench .workbench.card {
  margin-bottom: 0;
  border-radius: 6px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

/* Filters */
.filters-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.filters-section h2 {
  font-size: 1.125rem;
  margin: 0;
}

.table-filter-bar {
  background: var(--bg-accent);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 8px 10px;
}

.filter-item label {
  display: block;
  font-weight: 550;
  margin-bottom: 3px;
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.filter-control {
  width: 100%;
  box-sizing: border-box;
  padding: 5px 7px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  min-width: 0;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.date-range .filter-control {
  flex: 1;
  min-width: 0;
  padding: 4px 4px;
  font-size: 11px;
}

.date-sep {
  flex-shrink: 0;
  color: var(--muted);
  font-size: 11px;
}

.filter-bar-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}

.filter-bar-actions .primary-btn,
.filter-bar-actions .ghost-btn {
  padding: 5px 14px;
  font-size: 12px;
}

.filter-count-badge {
  margin-left: 4px;
  padding: 5px 12px;
  border-radius: 6px;
  background: var(--primary-light, #ede9fe);
  color: var(--primary-2, #4c1d95);
  font-size: 13px;
  font-weight: 600;
}

.filter-item.five-m-item {
  max-width: 120px;
}

.five-m-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.five-m-filter-btn {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  min-width: 28px;
  cursor: pointer;
  color: var(--muted);
}

.five-m-filter-btn.on {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.five-m-filter-btn:hover:not(.on) {
  border-color: var(--primary);
  color: var(--primary);
}

/* KPIs */
.kpis-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.kpi-card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  text-align: center;
}

.kpi-label {
  font-size: 0.875rem;
  color: #6b7280;
  margin-bottom: 0.5rem;
}

.kpi-value {
  font-size: 2rem;
  font-weight: 700;
  color: #1f2937;
}

.kpi-trend {
  margin-top: 0.5rem;
  font-size: 0.875rem;
}

.kpi-trend .up {
  color: #10b981;
}

.kpi-trend .down {
  color: #ef4444;
}

/* Charts */
.charts-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

.chart-card {
  min-height: 300px;
}

.chart-card h3 {
  margin: 0 0 1rem 0;
  font-size: 1.125rem;
}

/* Workbench: 表格纵向自然展开，页面滚动；仅横向溢出时表格内滚动 */
.workbench {
  position: relative;
  padding: 0;
  overflow: visible;
}

.workbench-layout {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow: visible;
}

.panel-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-height: 40px;
  padding: 0.45rem 0.625rem;
  border-bottom: 1px solid var(--line);
  background: #fff;
  flex-shrink: 0;
}

.panel-topbar h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workbench.has-entry .entry-panel {
  position: sticky;
  top: 8px;
  width: 240px;
  min-width: 220px;
  max-width: 260px;
  flex-shrink: 0;
  align-self: flex-start;
  max-height: calc(100vh - 24px);
  z-index: 3;
  background: var(--bg-accent);
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 4px 0 16px rgba(15, 23, 42, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.workbench.has-entry .table-panel {
  flex: 1;
  min-width: 0;
}

.entry-panel :deep(.entry-sidebar) {
  flex: 1;
  min-height: 0;
  border-right: none;
}

.table-panel {
  min-width: 0;
  padding: 0 0.625rem 1rem;
  overflow: visible;
}

.table-topbar {
  margin: 0 -0.625rem;
  padding-left: 0.625rem;
  padding-right: 0.625rem;
}

.column-picker-wrap {
  position: relative;
}

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
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.column-picker-list {
  overflow-y: auto;
  padding: 8px 0;
}

.column-picker-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
}

.column-picker-item:hover {
  background: var(--bg-accent);
}

.column-picker-item input {
  flex-shrink: 0;
}

.workbench.table-only .table-panel {
  flex: 1;
  width: 100%;
}

/* Table */
.workbench.table-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 1000;
  margin: 0;
  border-radius: 0;
  display: flex;
  flex-direction: column;
  max-width: none;
  overflow: hidden;
}

.workbench.table-fullscreen {
  height: 100vh;
  min-height: 0;
}

.workbench.table-fullscreen .workbench-layout {
  flex: 1;
  min-height: 0;
}

.workbench.table-fullscreen .table-panel {
  overflow: hidden;
}

.workbench.table-fullscreen .table-wrapper {
  flex: 1;
  max-height: none;
  margin-bottom: 0.75rem;
}

.table-hint {
  margin: 0 0 0.375rem;
  font-size: 0.75rem;
  color: #9ca3af;
  flex-shrink: 0;
}

.table-actions {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}

.entry-panel-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0.25rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.entry-panel-toggle:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.entry-panel-toggle.on {
  background: var(--primary-light, #ede9fe);
  border-color: var(--primary);
  color: var(--primary);
}

.entry-panel-toggle .toggle-icon {
  font-size: 13px;
  line-height: 1;
}

.table-actions .ghost-btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.table-wrapper {
  overflow-x: auto;
  overflow-y: visible;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  margin-bottom: 0.375rem;
  max-width: 100%;
  -webkit-overflow-scrolling: touch;
}

.table-wrapper input,
.table-wrapper button,
.table-wrapper select {
  user-select: auto;
  cursor: auto;
}

.table-loading {
  padding: 2rem;
  text-align: center;
  color: #6b7280;
}

.empty-row {
  text-align: center;
  color: #9ca3af;
  padding: 2rem !important;
}

.data-table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.workbench.table-fullscreen .data-table thead {
  position: sticky;
  top: 0;
  z-index: 2;
}

.data-table th {
  background: var(--primary-light);
  padding: 0.3rem 0.5rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
  vertical-align: bottom;
  font-size: 0.8125rem;
}

.header-labels th {
  border-bottom: none;
  padding-bottom: 0.25rem;
}

.th-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
}

.col-label {
  font-weight: 600;
  white-space: nowrap;
}

.col-sort-arrows {
  display: inline-flex;
  flex-direction: column;
  gap: 0;
  line-height: 1;
  flex-shrink: 0;
}

.col-sort-btn {
  display: block;
  border: none;
  background: none;
  padding: 0;
  margin: 0;
  width: 22px;
  height: 14px;
  font-size: 11px;
  line-height: 14px;
  color: #94a3b8;
  cursor: pointer;
}

.col-sort-btn:hover {
  color: #475569;
  background: #f1f5f9;
  border-radius: 3px;
}

.col-sort-btn.active {
  color: var(--primary);
  font-weight: 700;
}

.col-sort-btn.asc {
  margin-bottom: -1px;
}

.col-sort-btn.desc {
  margin-top: -1px;
}

.data-table td {
  padding: 0.35rem 0.5rem;
  border-bottom: 1px solid #f3f4f6;
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.8125rem;
}

.data-table tbody tr:hover {
  background: var(--primary-light);
}

.actions-cell {
  white-space: nowrap;
}

.close-status-select {
  min-width: 7.5rem;
  max-width: 100%;
  padding: 0.2rem 0.35rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 0.75rem;
  background: #fff;
  cursor: pointer;
}

.close-status-select:disabled {
  opacity: 0.6;
  cursor: wait;
}

.close-status-select.st-pending {
  color: #94a3b8;
}

.close-status-select.st-open {
  color: #d97706;
  border-color: #fcd34d;
}

.close-status-select.st-close {
  color: #16a34a;
  border-color: #86efac;
  font-weight: 600;
}

.readonly-cell {
  cursor: default;
  user-select: text;
}

.readonly-cell .cell-text {
  pointer-events: none;
}

.icon-btn {
  background: none;
  border: none;
  font-size: 1.125rem;
  cursor: pointer;
  padding: 0.25rem;
  opacity: 0.7;
}

.icon-btn:hover {
  opacity: 1;
}

.select-col {
  width: 36px;
  min-width: 36px;
  max-width: 36px;
  text-align: center;
  padding: 4px 6px !important;
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
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8125rem;
}

.danger-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex-shrink: 0;
  font-size: 0.8125rem;
}

.page-size {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.8125rem;
  color: #374151;
}

.page-size select {
  padding: 0.35rem 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
}

.pagination button {
  padding: 0.5rem 1rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.primary-btn {
  background: var(--primary);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.primary-btn:hover {
  background: var(--primary-2);
}

.ghost-btn {
  background: transparent;
  border: 1px solid var(--line);
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
}

.ghost-btn:hover {
  background: var(--primary-light);
}
</style>

<style>
body.table-fs-open {
  overflow: hidden;
}
</style>
