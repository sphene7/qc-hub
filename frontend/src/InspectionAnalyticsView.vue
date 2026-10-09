<template>
  <div ref="analyticsRoot" class="inspection-analytics" :class="{ 'theme-screen': chartTheme === 'screen', 'chart-theme-screen': chartTheme === 'screen' }">
    <div class="toolbar card">
      <label class="range-field">
        <span>统计日期</span>
        <div class="range-inputs">
          <input v-model="dateFromInput" type="date" @change="loadAnalytics" />
          <span class="range-sep">至</span>
          <input v-model="dateToInput" type="date" @change="loadAnalytics" />
        </div>
      </label>
      <label>
        <span>5M / 单日分析</span>
        <input v-model="focusDateInput" type="date" @change="loadAnalytics" />
      </label>
      <button type="button" class="ghost-btn" @click="loadAnalytics">刷新</button>
      <ChartThemePicker v-model="chartTheme" />
      <button
        v-if="dateFromInput || dateToInput"
        type="button"
        class="ghost-btn"
        @click="clearDateRange"
      >清除日期</button>
      <span v-if="activeRangeHint" class="hint">{{ activeRangeHint }}</span>
      <span v-else-if="fiveMSummary.focus_date" class="hint">
        当前分析日：{{ formatFocusDate(fiveMSummary.focus_date) }} · 共 {{ fiveMSummary.total || 0 }} 件
      </span>
    </div>

    <div v-if="loading" class="loading-hint">正在加载统计数据…</div>
    <div v-else-if="error" class="error-hint">{{ error }}</div>
    <template v-else>
      <div class="dashboard-grid">
        <!-- 第一行：责任单位全宽 -->
        <section class="panel card panel-units">
          <h2 class="panel-title">责任单位结案状况</h2>
          <div class="table-wrap">
            <table class="stat-table unit-table">
              <thead>
                <tr>
                  <th rowspan="2">责任单位</th>
                  <th rowspan="2">类别</th>
                  <th v-for="m in unitSummary.months" :key="'m-' + m" colspan="1">{{ m }}</th>
                  <th v-if="unitSummary.focus_date">{{ dayColumnLabel }}</th>
                  <th>TTL</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="unit in unitSummary.rows" :key="unit.unit">
                  <tr>
                    <td rowspan="3" class="unit-name">{{ unit.unit }}</td>
                    <td>问题件数</td>
                    <td v-for="m in unitSummary.months" :key="unit.unit + '-t-' + m">
                      {{ fmtInt(unit.months[m]?.total) }}
                    </td>
                    <td v-if="unitSummary.focus_date">{{ fmtInt(unit.day?.total) }}</td>
                    <td>{{ fmtInt(unit.ttl?.total) }}</td>
                  </tr>
                  <tr>
                    <td>结案件数</td>
                    <td v-for="m in unitSummary.months" :key="unit.unit + '-c-' + m">
                      {{ fmtInt(unit.months[m]?.closed) }}
                    </td>
                    <td v-if="unitSummary.focus_date">{{ fmtInt(unit.day?.closed) }}</td>
                    <td>{{ fmtInt(unit.ttl?.closed) }}</td>
                  </tr>
                  <tr class="rate-row">
                    <td>结案率</td>
                    <td
                      v-for="m in unitSummary.months"
                      :key="unit.unit + '-r-' + m"
                      :class="rateClass(unit.months[m]?.close_rate)"
                    >
                      {{ fmtRate(unit.months[m]?.close_rate) }}
                    </td>
                    <td v-if="unitSummary.focus_date" :class="rateClass(unit.day?.close_rate)">
                      {{ fmtRate(unit.day?.close_rate) }}
                    </td>
                    <td :class="rateClass(unit.ttl?.close_rate)">{{ fmtRate(unit.ttl?.close_rate) }}</td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 第二行：5M 全宽 -->
        <section class="panel card panel-fivem">
          <h2 class="panel-title">5M 问题分布 · {{ dayColumnLabel }}</h2>
          <div class="five-m-layout">
            <div class="chart-wrap chart-wrap-fivem">
              <ChartView :option="fiveMChart" :theme="chartTheme" />
            </div>
            <div class="table-wrap five-m-table-wrap">
              <table class="stat-table">
                <thead>
                  <tr>
                    <th>5M</th>
                    <th>问题件数</th>
                    <th>占比</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in fiveMSummary.items" :key="item.key">
                    <td>{{ item.full_label }}</td>
                    <td>{{ fmtInt(item.count) }}</td>
                    <td>{{ fmtRate(item.share) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-if="fiveMDetailEntries.length" class="five-m-details">
            <div v-for="entry in fiveMDetailEntries" :key="entry.key" class="detail-card">
              <h3>{{ entry.label }} · 明细</h3>
              <div class="table-wrap">
                <table class="stat-table compact">
                  <thead>
                    <tr>
                      <th>问题点描述</th>
                      <th>件数</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in entry.items" :key="row.description">
                      <td class="desc-cell" :title="row.description">{{ row.description }}</td>
                      <td>{{ fmtInt(row.count) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <!-- 第三行：类别 + 模块负责人 对称双栏 -->
        <section class="panel card panel-category">
          <h2 class="panel-title">各类别问题结案状况</h2>
          <div class="panel-stack">
            <div class="table-wrap">
              <table class="stat-table">
                <thead>
                  <tr>
                    <th>问题类别</th>
                    <th>件数</th>
                    <th>占比</th>
                    <th>close</th>
                    <th>结案率</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in categorySummary"
                    :key="row.category"
                    :class="{ total: row.is_total, 'rate-low': isLowRate(row.close_rate) }"
                  >
                    <td>{{ row.category }}</td>
                    <td>{{ fmtInt(row.total) }}</td>
                    <td>{{ fmtRate(row.share) }}</td>
                    <td>{{ fmtInt(row.closed) }}</td>
                    <td>{{ fmtRate(row.close_rate) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="chart-wrap chart-wrap-lg">
              <ChartView :option="categoryChart" :theme="chartTheme" />
            </div>
          </div>
        </section>

        <section class="panel card panel-module">
          <h2 class="panel-title">各模块负责人结案状况</h2>
          <div class="panel-stack">
            <div class="table-wrap">
              <table class="stat-table">
                <thead>
                  <tr>
                    <th>模块</th>
                    <th>模块负责人</th>
                    <th>问题点件数</th>
                    <th>close</th>
                    <th>结案率</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in moduleOwnerSummary"
                    :key="row.label"
                    :class="{ total: row.is_total, 'rate-low': isLowRate(row.close_rate) }"
                  >
                    <td>{{ row.module }}</td>
                    <td>{{ row.owner }}</td>
                    <td>{{ fmtInt(row.total) }}</td>
                    <td>{{ fmtInt(row.closed) }}</td>
                    <td>{{ fmtRate(row.close_rate) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="chart-wrap chart-wrap-lg">
              <ChartView :option="moduleOwnerChart" :theme="chartTheme" />
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { authFetch } from "./api.js";
import ChartView from "./ChartView.vue";
import ChartThemePicker from "./ChartThemePicker.vue";

const props = defineProps({
  workbookId: String,
  sheet: { type: String, default: "" },
});

const chartTheme = ref(localStorage.getItem("qc-hub:chart-theme") === "screen" ? "screen" : "default");
const analyticsRoot = ref(null);
watch(chartTheme, async (value) => {
  localStorage.setItem("qc-hub:chart-theme", value);
  await nextTick();
  debugScreenLayout();
});

const loading = ref(true);
const error = ref("");
const dateFromInput = ref("");
const dateToInput = ref("");
const focusDateInput = ref("");
const unitSummary = ref({ months: [], focus_date: null, rows: [] });
const fiveMSummary = ref({ focus_date: null, items: [], details: {}, total: 0 });
const categorySummary = ref([]);
const moduleOwnerSummary = ref([]);

function fmtInt(v) {
  if (v == null || Number.isNaN(v)) return "-";
  return Math.round(Number(v)).toLocaleString();
}

function fmtRate(v) {
  if (v == null || Number.isNaN(v)) return "-";
  return `${(Number(v) * 100).toFixed(2)}%`;
}

function isLowRate(v) {
  return v != null && !Number.isNaN(v) && Number(v) < 0.9;
}

function rateClass(v) {
  if (v == null || Number.isNaN(v)) return "";
  if (v >= 0.9) return "rate-good";
  if (v >= 0.7) return "rate-mid";
  return "rate-low-cell";
}

function dataRows(rows) {
  return (rows || []).filter((r) => !r.is_total);
}

function formatFocusDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

const dayColumnLabel = computed(() => {
  if (!unitSummary.value.focus_date) return "当日";
  return formatFocusDate(unitSummary.value.focus_date);
});

const activeRangeHint = computed(() => {
  const from = dateFromInput.value;
  const to = dateToInput.value;
  if (!from && !to) return "";
  const fmt = (iso) => {
    if (!iso) return "…";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };
  if (from && to) return `已筛选：${fmt(from)} 至 ${fmt(to)}`;
  if (from) return `已筛选：${fmt(from)} 起`;
  return `已筛选：至 ${fmt(to)}`;
});

function clearDateRange() {
  dateFromInput.value = "";
  dateToInput.value = "";
  loadAnalytics();
}

const fiveMDetailEntries = computed(() => {
  const details = fiveMSummary.value.details || {};
  const items = fiveMSummary.value.items || [];
  return items
    .filter((item) => (details[item.key] || []).length > 0)
    .map((item) => ({
      key: item.key,
      label: item.full_label,
      items: details[item.key],
    }));
});

const fiveMChart = computed(() => {
  const items = fiveMSummary.value.items || [];
  const palette =
    chartTheme.value === "screen"
      ? ["#c4b5fd", "#a5b4fc", "#ddd6fe", "#e9d5ff", "#b794f6"]
      : ["#62c4dd", "#7fa7df", "#ce91a4", "#d8b979", "#61c9ae"];
  return {
    color: palette,
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { orient: "vertical", right: 8, top: "middle", textStyle: { fontSize: 11 } },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["40%", "50%"],
        data: items.map((item) => ({
          name: item.full_label,
          value: item.count,
          itemStyle: { color: palette[items.indexOf(item) % palette.length] },
        })),
        label: { formatter: "{b}\n{d}%", fontSize: 11 },
      },
    ],
  };
});

function comboChartFromRows(rows, labels, labelKey = "label") {
  const categories = rows.map((r) => r[labelKey] || r.category || r.module);
  return {
    color: ["#5b9bd5", "#70ad47", "#ed7d31"],
    tooltip: { trigger: "axis" },
    legend: { data: ["问题点件数", "close", "结案率"], bottom: 0 },
    grid: { left: 48, right: 48, bottom: 72, top: 36 },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { rotate: 35, interval: 0, fontSize: 10 },
    },
    yAxis: [
      { type: "value", name: "件数" },
      { type: "value", name: "结案率", axisLabel: { formatter: "{value}%" }, max: 120 },
    ],
    series: [
      {
        name: "问题点件数",
        type: "bar",
        data: rows.map((r) => r.total),
        barGap: "10%",
        barMaxWidth: 22,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "close",
        type: "bar",
        data: rows.map((r) => r.closed),
        barMaxWidth: 22,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "结案率",
        type: "line",
        yAxisIndex: 1,
        data: rows.map((r) =>
          r.close_rate != null ? Number((r.close_rate * 100).toFixed(2)) : null
        ),
        label: { show: true, formatter: "{c}%", fontSize: 10 },
      },
    ],
  };
}

const categoryChart = computed(() => {
  const rows = dataRows(categorySummary.value);
  return comboChartFromRows(rows, rows.map((r) => r.category), "category");
});

const moduleOwnerChart = computed(() => {
  const rows = dataRows(moduleOwnerSummary.value);
  return comboChartFromRows(rows, rows.map((r) => r.label));
});

async function loadAnalytics() {
  loading.value = true;
  error.value = "";
  try {
    const params = new URLSearchParams();
    if (props.sheet) params.set("sheet", props.sheet);
    if (dateFromInput.value) params.set("date_from", dateFromInput.value);
    if (dateToInput.value) params.set("date_to", dateToInput.value);
    if (focusDateInput.value) params.set("date", focusDateInput.value);
    const q = params.toString() ? `?${params.toString()}` : "";
    const res = await authFetch(`/api/workbooks/${props.workbookId}/inspection-analytics${q}`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "加载失败");
    }
    const data = await res.json();
    unitSummary.value = data.unit_summary || { months: [], focus_date: null, rows: [] };
    fiveMSummary.value = data.five_m_summary || { focus_date: null, items: [], details: {}, total: 0 };
    categorySummary.value = data.category_summary || [];
    moduleOwnerSummary.value = data.module_owner_summary || [];
    if (!focusDateInput.value && unitSummary.value.focus_date) {
      focusDateInput.value = unitSummary.value.focus_date.slice(0, 10);
    }
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    loading.value = false;
    await nextTick();
    debugScreenLayout();
  }
}

onMounted(() => {
  loadAnalytics();
  window.addEventListener("resize", debugScreenLayout);
});

onBeforeUnmount(() => window.removeEventListener("resize", debugScreenLayout));

function debugScreenLayout() {
  if (chartTheme.value !== "screen" || !analyticsRoot.value) return;
  const root = analyticsRoot.value;
  const overflow = [...root.querySelectorAll(".table-wrap, .detail-card, .five-m-details")]
    .map((node) => ({ className: node.className, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth }))
    .filter((item) => item.scrollWidth > item.clientWidth);
  console.info("[InspectionAnalytics] screen layout", {
    viewport: window.innerWidth,
    rootClientWidth: root.clientWidth,
    rootScrollWidth: root.scrollWidth,
    overflow,
  });
}

defineExpose({ refresh: loadAnalytics });
</script>

<style scoped>
.inspection-analytics {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.toolbar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
}

.toolbar label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.toolbar input[type="date"] {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 14px;
}

.range-field .range-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.range-sep {
  font-size: 13px;
  color: var(--muted);
}

.toolbar .hint {
  color: var(--muted);
  font-size: 13px;
}

/* —— 统一分区布局 —— */
.dashboard-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;
}

.panel-title {
  margin: 0 0 14px;
  font-size: 16px;
  font-weight: 700;
  color: var(--primary-2, #4c1d95);
}

.panel-stack {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.five-m-layout {
  display: grid;
  grid-template-columns: minmax(260px, 1.15fr) minmax(200px, 0.85fr);
  gap: 16px;
  align-items: start;
}

.five-m-details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.detail-card h3 {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--muted);
}

.table-wrap {
  overflow: auto;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}

.stat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: #fff;
}

.stat-table th,
.stat-table td {
  border: 1px solid #94a3b8;
  padding: 5px 8px;
  text-align: center;
  white-space: nowrap;
}

.stat-table th {
  background: #31859b;
  color: #fff;
  font-weight: 600;
}

.stat-table.compact .desc-cell {
  text-align: left;
  max-width: 280px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.unit-name {
  font-weight: 700;
  background: #f8fafc;
  vertical-align: middle;
}

.rate-row td {
  font-weight: 600;
}

.rate-good {
  background: #e8f5e9;
  color: #2e7d32;
}

.rate-mid {
  background: #fff8e1;
  color: #f57f17;
}

.rate-low-cell,
.stat-table tr.rate-low td:last-child {
  background: #fce4ec;
  color: #c62828;
}

.stat-table tr.total td {
  font-weight: 700;
  background: #f8fafc;
}

.chart-wrap :deep(.chart) {
  height: 280px;
}

.chart-wrap-fivem :deep(.chart) {
  height: 300px;
}

.chart-wrap-lg :deep(.chart) {
  height: 340px;
}

.ghost-btn {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 7px 12px;
  cursor: pointer;
}

.loading-hint,
.error-hint {
  padding: 24px;
  text-align: center;
  color: var(--muted);
}

.error-hint {
  color: #c62828;
}

@media (min-width: 1280px) {
  .dashboard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-areas:
      "units units"
      "fivem fivem"
      "category module";
  }

  .panel-units { grid-area: units; }
  .panel-fivem { grid-area: fivem; }
  .panel-category { grid-area: category; }
  .panel-module { grid-area: module; }
}

@media (max-width: 1100px) {
  .panel-stack,
  .five-m-layout {
    grid-template-columns: 1fr;
  }
}

/* —— 科技大屏：浅紫透明 + 星座背景 + 清澈/模糊对比 —— */
.theme-screen {
  --screen-bg-deep: #120a22;
  --screen-bg-mid: #1e1238;
  --screen-bg-light: #2a1a4a;
  --screen-glass: linear-gradient(
    145deg,
    rgba(255, 255, 255, .07) 0%,
    rgba(255, 255, 255, .02) 42%,
    rgba(255, 255, 255, .035) 100%
  );
  --screen-glass-clear: linear-gradient(
    160deg,
    rgba(255, 255, 255, .055) 0%,
    rgba(255, 255, 255, .008) 55%,
    rgba(255, 255, 255, .025) 100%
  );
  --screen-border: rgba(255, 255, 255, .14);
  --screen-border-bright: rgba(255, 255, 255, .22);
  --screen-blur-soft: blur(5px);
  --screen-blur-clear: blur(2px);
  --screen-text: #f5f0ff;
  --screen-muted: rgba(237, 233, 254, .62);
  --screen-title: #ede9fe;
  position: relative;
  isolation: isolate;
  padding: 20px;
  border-radius: 16px;
  color: var(--screen-text);
  background-color: var(--screen-bg-deep);
  background-image:
    linear-gradient(145deg, #1a0f32 0%, #2d1b52 28%, #3d2868 52%, #251740 78%, #140c26 100%),
    radial-gradient(ellipse 90% 70% at 8% -10%, rgba(196, 181, 253, .22), transparent 55%),
    radial-gradient(ellipse 80% 60% at 92% 108%, rgba(167, 139, 250, .18), transparent 50%),
    radial-gradient(ellipse 55% 45% at 50% 42%, rgba(221, 214, 254, .08), transparent 62%),
    var(--screen-constellation);
  background-size: auto, auto, auto, auto, 900px 600px;
  background-repeat: no-repeat, no-repeat, no-repeat, no-repeat, repeat;
  background-attachment: local;
}

.theme-screen::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  pointer-events: none;
  background:
    radial-gradient(circle at 22% 18%, rgba(196, 181, 253, .14) 0, transparent 38%),
    radial-gradient(circle at 78% 82%, rgba(167, 139, 250, .10) 0, transparent 36%);
  filter: blur(28px);
  opacity: .85;
}

.theme-screen::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  pointer-events: none;
  opacity: .35;
  background: repeating-linear-gradient(0deg, rgba(237, 233, 254, .012) 0 1px, transparent 1px 6px);
}

/* 工具栏：清透玻璃，几乎不磨砂 */
.theme-screen .toolbar {
  background: var(--screen-glass-clear);
  border: 1px solid var(--screen-border-bright);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .12);
  backdrop-filter: var(--screen-blur-clear);
  -webkit-backdrop-filter: var(--screen-blur-clear);
}

.theme-screen .toolbar,
.theme-screen .toolbar label,
.theme-screen .toolbar .hint,
.theme-screen .range-sep {
  color: var(--screen-muted);
}

/* 数据面板：透明玻璃（轻 blur，避免磨砂发浑） */
.theme-screen :deep(.card) {
  background: var(--screen-glass) !important;
  background-image: none !important;
  border: 1px solid var(--screen-border);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .10) !important;
  backdrop-filter: var(--screen-blur-soft) saturate(110%);
  -webkit-backdrop-filter: var(--screen-blur-soft) saturate(110%);
}

.theme-screen :deep(.card.panel) {
  border-radius: 12px;
}

.theme-screen .panel-title {
  color: var(--screen-title);
  letter-spacing: .02em;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(216, 180, 254, .16);
}

.theme-screen .five-m-details {
  border-top-color: rgba(216, 180, 254, .16);
}

/* 5M 明细小卡：最透、几乎不 blur，防止与父级叠磨砂 */
.theme-screen .detail-card {
  background: var(--screen-glass-clear);
  border: 1px solid rgba(255, 255, 255, .12);
  border-top-color: rgba(255, 255, 255, .20);
  border-radius: 10px;
  padding: 12px;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .08);
}

.theme-screen .detail-card h3 {
  color: var(--screen-muted);
}

/* 表格区：几乎全透明，仅保留细线分隔 */
.theme-screen .table-wrap {
  border-color: rgba(216, 180, 254, .16);
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  box-shadow: none;
}

.theme-screen .stat-table {
  background: transparent;
  color: var(--screen-text);
  table-layout: fixed;
}

.theme-screen .stat-table th {
  background: rgba(255, 255, 255, .04);
  color: rgba(245, 240, 255, .92);
  border-color: rgba(255, 255, 255, .10);
  font-weight: 500;
}

.theme-screen .stat-table td {
  background: transparent;
  border-color: rgba(216, 180, 254, .10);
}

.theme-screen .stat-table td,
.theme-screen .stat-table th {
  overflow: hidden;
  text-overflow: ellipsis;
}

.theme-screen .unit-name,
.theme-screen .stat-table tr.total td {
  background: rgba(255, 255, 255, .04);
}

.theme-screen .rate-good {
  background: rgba(167, 243, 208, .08);
  color: #bbf7d0;
}

.theme-screen .rate-mid {
  background: rgba(253, 230, 138, .07);
  color: #fde68a;
}

.theme-screen .rate-low-cell,
.theme-screen .stat-table tr.rate-low td:last-child {
  background: rgba(251, 207, 232, .08);
  color: #fbcfe8;
}

.theme-screen .theme-picker select,
.theme-screen .toolbar input[type="date"],
.theme-screen .ghost-btn {
  background: rgba(255, 255, 255, .06);
  color: var(--screen-text);
  border-color: rgba(216, 180, 254, .22);
}

.theme-screen .ghost-btn:hover {
  background: rgba(255, 255, 255, .10);
}

.theme-screen :deep(.chart) {
  height: 320px;
}

.theme-screen .chart-wrap-fivem :deep(.chart) {
  height: 300px;
}

.theme-screen .chart-wrap-lg :deep(.chart) {
  height: 360px;
}

.theme-screen .panel,
.theme-screen .table-wrap,
.theme-screen .detail-card {
  min-width: 0;
  max-width: 100%;
}

.theme-screen .detail-card {
  overflow: hidden;
}
</style>
