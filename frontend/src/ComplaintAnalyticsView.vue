<template>
  <div
    class="complaint-analytics"
    :class="{ 'chart-theme-screen': chartTheme === 'screen', 'theme-screen': chartTheme === 'screen' }"
  >
    <div class="toolbar card">
      <label class="range-field">
        <span>统计日期</span>
        <div class="range-inputs">
          <input v-model="dateFromInput" type="date" @change="loadAnalytics" />
          <span class="range-sep">至</span>
          <input v-model="dateToInput" type="date" @change="loadAnalytics" />
        </div>
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
    </div>

    <div v-if="loading" class="loading-hint">正在加载统计数据…</div>
    <div v-else-if="error" class="error-hint">{{ error }}</div>
    <template v-else>
      <!-- 月度推移 -->
      <section class="block card">
        <h2>月度推移</h2>
        <div class="split-layout">
          <div class="table-wrap table-wrap-lg">
            <table class="stat-table">
              <thead>
                <tr>
                  <th>月度</th>
                  <th>已结案</th>
                  <th>跟进中</th>
                  <th>未结案</th>
                  <th>总件数</th>
                  <th>结案率</th>
                  <th>结案平均天数</th>
                  <th>总结案天数</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in monthlyTrend"
                  :key="row.month"
                  :class="{ total: row.is_total, 'rate-low': isLowRate(row.close_rate) }"
                >
                  <td>{{ row.month }}</td>
                  <td>{{ fmtInt(row.closed) }}</td>
                  <td>{{ fmtInt(row.ongoing) }}</td>
                  <td>{{ fmtInt(row.open) }}</td>
                  <td>{{ fmtInt(row.total) }}</td>
                  <td>{{ fmtRate(row.close_rate) }}</td>
                  <td>{{ fmtDays(row.avg_close_days) }}</td>
                  <td>{{ fmtDays(row.sum_close_days) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="chart-wrap chart-wrap-lg">
            <ChartView :option="monthlyTrendChart" :theme="chartTheme" />
          </div>
        </div>
      </section>

      <!-- 各担当 -->
      <section class="block card">
        <h2>各担当客诉结案状况</h2>
        <div class="chart-wrap chart-wrap-wide">
          <ChartView :option="staffChart" :theme="chartTheme" />
        </div>
        <div class="table-wrap">
          <table class="stat-table">
            <thead>
              <tr>
                <th>客户担当</th>
                <th>客诉总件数</th>
                <th>结案件数</th>
                <th>累计结案率</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in staffSummary"
                :key="row.staff"
                :class="{ total: row.is_total, 'rate-low': isLowRate(row.close_rate) }"
              >
                <td>{{ row.staff }}</td>
                <td>{{ fmtInt(row.total) }}</td>
                <td>{{ fmtInt(row.closed) }}</td>
                <td>{{ fmtRate(row.close_rate) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 月度汇总 + 系列 -->
      <section class="block card bottom-grid">
        <div class="bottom-left">
          <h2>月度汇总</h2>
          <div class="table-wrap">
            <table class="stat-table">
              <thead>
                <tr>
                  <th>月份</th>
                  <th>客诉总件数</th>
                  <th>结案件数</th>
                  <th>累计结案率</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in monthlySummary"
                  :key="'sum-' + row.month"
                  :class="{ total: row.is_total, 'rate-low': isLowRate(row.close_rate) }"
                >
                  <td>{{ row.month }}</td>
                  <td>{{ fmtInt(row.total) }}</td>
                  <td>{{ fmtInt(row.closed) }}</td>
                  <td>{{ fmtRate(row.close_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="chart-wrap">
            <ChartView :option="monthlySummaryChart" :theme="chartTheme" />
          </div>
        </div>
        <div class="bottom-right">
          <h2>系列 · 计数</h2>
          <div class="table-wrap">
            <table class="stat-table">
              <thead>
                <tr>
                  <th>系列</th>
                  <th>计数项:产品线</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in seriesCounts" :key="row.series">
                  <td>{{ row.series }}</td>
                  <td>{{ fmtInt(row.count) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { authFetch } from "./api.js";
import ChartView from "./ChartView.vue";
import ChartThemePicker from "./ChartThemePicker.vue";

const props = defineProps({
  workbookId: String,
  sheet: { type: String, default: "" },
});

const loading = ref(true);
const error = ref("");
const dateFromInput = ref("");
const dateToInput = ref("");
const chartTheme = ref(localStorage.getItem("qc-hub:chart-theme") === "screen" ? "screen" : "default");
watch(chartTheme, (value) => localStorage.setItem("qc-hub:chart-theme", value));
const monthlyTrend = ref([]);
const staffSummary = ref([]);
const monthlySummary = ref([]);
const seriesCounts = ref([]);

function fmtInt(v) {
  if (v == null || Number.isNaN(v)) return "-";
  return Math.round(Number(v)).toLocaleString();
}

function fmtDays(v) {
  if (v == null || Number.isNaN(v)) return "-";
  return Number(v).toFixed(2);
}

function fmtRate(v) {
  if (v == null || Number.isNaN(v)) return "-";
  return `${(Number(v) * 100).toFixed(2)}%`;
}

function isLowRate(v) {
  return v != null && !Number.isNaN(v) && Number(v) < 0.9;
}

function dataRows(rows) {
  return (rows || []).filter((r) => !r.is_total);
}

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

const monthlyTrendChart = computed(() => {
  const rows = dataRows(monthlyTrend.value);
  const labels = rows.map((r) => r.month);
  const daysLabel = (v) => (v == null || Number.isNaN(v) ? "" : Number(v).toFixed(2));
  return {
    color: ["#9dc3e6", "#5b9bd5", "#a5a5a5", "#ed7d31"],
    tooltip: {
      trigger: "axis",
      formatter(params) {
        if (!params?.length) return "";
        let html = `${params[0].axisValue}<br/>`;
        for (const p of params) {
          let val = p.value;
          if (p.seriesName === "结案平均天数") val = daysLabel(val);
          else if (p.seriesName === "结案率" && val != null) val = `${val}%`;
          else if (val == null) val = "-";
          html += `${p.marker}${p.seriesName}: ${val}<br/>`;
        }
        return html;
      },
    },
    legend: { data: ["客诉总件数", "已结案", "结案平均天数", "结案率"], bottom: 0 },
    grid: { left: 48, right: 48, bottom: 56, top: 36 },
    xAxis: { type: "category", data: labels },
    yAxis: [
      { type: "value", name: "件数/天数" },
      { type: "value", name: "结案率", axisLabel: { formatter: "{value}%" }, max: 120 },
    ],
    series: [
      {
        name: "客诉总件数",
        type: "bar",
        data: rows.map((r) => r.total),
        barMaxWidth: 22,
        barGap: "15%",
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "已结案",
        type: "bar",
        data: rows.map((r) => r.closed),
        barMaxWidth: 22,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "结案平均天数",
        type: "line",
        data: rows.map((r) => (r.avg_close_days != null ? Number(Number(r.avg_close_days).toFixed(2)) : null)),
        label: { show: true, fontSize: 10, formatter: (p) => daysLabel(p.value) },
      },
      {
        name: "结案率",
        type: "line",
        yAxisIndex: 1,
        data: rows.map((r) => (r.close_rate != null ? Number((r.close_rate * 100).toFixed(2)) : null)),
        label: { show: true, formatter: "{c}%", fontSize: 10 },
      },
    ],
  };
});

const staffChart = computed(() => {
  const rows = dataRows(staffSummary.value);
  const labels = rows.map((r) => r.staff);
  return {
    color: ["#5b9bd5", "#ffc000", "#ed7d31"],
    tooltip: { trigger: "axis" },
    legend: { data: ["客诉总件数", "结案件数", "累计结案率"], bottom: 0 },
    grid: { left: 48, right: 48, bottom: 72, top: 36 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { rotate: 35, interval: 0, fontSize: 11 },
    },
    yAxis: [
      { type: "value", name: "件数" },
      { type: "value", name: "结案率", axisLabel: { formatter: "{value}%" }, max: 120 },
    ],
    series: [
      {
        name: "客诉总件数",
        type: "bar",
        data: rows.map((r) => r.total),
        barGap: "10%",
        barMaxWidth: 22,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "结案件数",
        type: "bar",
        data: rows.map((r) => r.closed),
        barMaxWidth: 22,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "累计结案率",
        type: "line",
        yAxisIndex: 1,
        data: rows.map((r) => (r.close_rate != null ? Number((r.close_rate * 100).toFixed(2)) : null)),
        label: { show: true, formatter: "{c}%", fontSize: 10 },
      },
    ],
  };
});

const monthlySummaryChart = computed(() => {
  const rows = dataRows(monthlySummary.value);
  const labels = rows.map((r) => r.month);
  return {
    color: ["#5b9bd5", "#ffc000", "#70ad47"],
    tooltip: { trigger: "axis" },
    legend: { data: ["客诉总件数", "结案件数", "累计结案率"], bottom: 0 },
    grid: { left: 48, right: 48, bottom: 48, top: 36 },
    xAxis: { type: "category", data: labels },
    yAxis: [
      { type: "value", name: "件数" },
      { type: "value", name: "结案率", axisLabel: { formatter: "{value}%" }, max: 120 },
    ],
    series: [
      {
        name: "客诉总件数",
        type: "bar",
        data: rows.map((r) => r.total),
        barMaxWidth: 24,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "结案件数",
        type: "bar",
        data: rows.map((r) => r.closed),
        barMaxWidth: 24,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "累计结案率",
        type: "line",
        yAxisIndex: 1,
        data: rows.map((r) => (r.close_rate != null ? Number((r.close_rate * 100).toFixed(2)) : null)),
        label: { show: true, formatter: "{c}%", fontSize: 10 },
      },
    ],
  };
});

async function loadAnalytics() {
  loading.value = true;
  error.value = "";
  try {
    const params = new URLSearchParams();
    if (props.sheet) params.set("sheet", props.sheet);
    if (dateFromInput.value) params.set("date_from", dateFromInput.value);
    if (dateToInput.value) params.set("date_to", dateToInput.value);
    const q = params.toString() ? `?${params.toString()}` : "";
    const res = await authFetch(`/api/workbooks/${props.workbookId}/complaint-analytics${q}`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "加载失败");
    }
    const data = await res.json();
    monthlyTrend.value = data.monthly_trend || [];
    staffSummary.value = data.staff_summary || [];
    monthlySummary.value = data.monthly_summary || [];
    seriesCounts.value = data.series_counts || [];
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    loading.value = false;
  }
}

onMounted(loadAnalytics);

defineExpose({ refresh: loadAnalytics });
</script>

<style scoped>
.complaint-analytics {
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

.ghost-btn {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 7px 12px;
  font-size: 13px;
  color: var(--primary);
  cursor: pointer;
}

.hint {
  font-size: 12px;
  color: var(--muted);
  align-self: center;
}

.block h2 {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 700;
  color: var(--primary-2, #4c1d95);
}

.split-layout {
  display: grid;
  grid-template-columns: minmax(420px, 1.1fr) minmax(360px, 1fr);
  gap: 16px;
  align-items: start;
}

.bottom-grid {
  display: grid;
  grid-template-columns: minmax(380px, 1.2fr) minmax(260px, 0.8fr);
  gap: 20px;
}

.bottom-left,
.bottom-right {
  min-width: 0;
}

.table-wrap {
  overflow: auto;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
}

.table-wrap-lg {
  max-height: none;
}

.stat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: #fff;
}

.stat-table th,
.stat-table td {
  border: 1px solid #94a3b8;
  padding: 6px 10px;
  text-align: center;
  white-space: nowrap;
}

.stat-table th {
  background: #31859b;
  color: #fff;
  font-weight: 600;
}

.stat-table tr.total td {
  font-weight: 700;
  background: #f8fafc;
}

.stat-table tr.rate-low td:last-child {
  background: #fce4ec;
  color: #c62828;
}

.chart-wrap {
  margin-top: 12px;
}

.chart-wrap :deep(.chart) {
  height: 280px;
}

.chart-wrap-lg :deep(.chart) {
  height: 360px;
}

.chart-wrap-wide {
  margin-top: 0;
  margin-bottom: 12px;
}

.chart-wrap-wide :deep(.chart) {
  height: 340px;
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

@media (max-width: 1100px) {
  .split-layout,
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}
</style>
