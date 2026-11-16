<template>
  <div
    class="oqc-analytics"
    :class="{ 'chart-theme-screen': chartTheme === 'screen', 'theme-screen': chartTheme === 'screen' }"
  >
    <div class="toolbar card">
      <label class="month-field">
        <span>统计月份</span>
        <input v-model="monthInput" type="month" @change="loadAnalytics" />
      </label>
      <button type="button" class="ghost-btn" @click="loadAnalytics">刷新</button>
      <ChartThemePicker v-model="chartTheme" />
      <span v-if="payload.subtitle" class="hint">{{ payload.subtitle }} · 数据来自抽检明细实时汇总</span>
    </div>

    <div v-if="loading" class="loading-hint">正在加载推移数据…</div>
    <div v-else-if="error" class="error-hint">{{ error }}</div>
    <template v-else>
      <section class="block card chart-block">
        <h2>{{ payload.title || "批次合格率推移图" }}</h2>
        <div class="chart-wrap-lg">
          <ChartView :option="trendChart" :theme="chartTheme" />
        </div>
      </section>

      <section class="block card">
        <h2>推移数据明细</h2>
        <div class="table-wrap">
          <table class="stat-table oqc-trend-table">
            <thead>
              <tr>
                <th class="sticky-col" colspan="2">送检单位</th>
                <th v-for="d in dayHeaders" :key="'h-' + d">{{ d }}日</th>
                <th class="ttl-col">TTL</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="block in tableBlocks" :key="block.name">
                <tr>
                  <td rowspan="3" class="unit-name">{{ block.name }}</td>
                  <td class="metric-label">送检批</td>
                  <td v-for="(cell, idx) in block.days" :key="block.name + '-s-' + idx">
                    {{ fmtCount(cell.sent) }}
                  </td>
                  <td class="ttl-col">{{ fmtCount(block.ttl.sent) }}</td>
                </tr>
                <tr>
                  <td class="metric-label">合格批</td>
                  <td v-for="(cell, idx) in block.days" :key="block.name + '-p-' + idx">
                    {{ fmtCount(cell.passed) }}
                  </td>
                  <td class="ttl-col">{{ fmtCount(block.ttl.passed) }}</td>
                </tr>
                <tr class="rate-row">
                  <td class="metric-label">合格率</td>
                  <td
                    v-for="(cell, idx) in block.days"
                    :key="block.name + '-r-' + idx"
                    :class="rateClass(cell.rate, cell.sent)"
                  >
                    {{ fmtRateCell(cell.rate, cell.sent) }}
                  </td>
                  <td class="ttl-col" :class="rateClass(block.ttl.rate, block.ttl.sent)">
                    {{ fmtRateCell(block.ttl.rate, block.ttl.sent) }}
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <section class="block card dashboard-block">
        <h2>看板汇总</h2>
        <p class="dash-hint">按所选月份 · 正常送检 · 与上方推移同源汇总</p>
        <div class="dashboard-grid">
          <div class="dash-card">
            <h3>各课室批次合格率</h3>
            <div class="chart-wrap-md">
              <ChartView :option="sectionPassChart" :theme="chartTheme" />
            </div>
          </div>
          <div class="dash-card">
            <h3>各课室 NG 占比</h3>
            <div class="chart-wrap-md">
              <ChartView :option="sectionNgChart" :theme="chartTheme" />
            </div>
          </div>
          <div class="dash-card">
            <h3>按现象不良</h3>
            <div class="chart-wrap-md">
              <ChartView :option="phenomenonChart" :theme="chartTheme" />
            </div>
          </div>
          <div class="dash-card">
            <h3>按机型不良</h3>
            <div class="chart-wrap-md">
              <ChartView :option="seriesChart" :theme="chartTheme" />
            </div>
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
const monthInput = ref("");
const chartTheme = ref(localStorage.getItem("qc-hub:chart-theme") === "screen" ? "screen" : "default");
watch(chartTheme, (value) => localStorage.setItem("qc-hub:chart-theme", value));
const payload = ref({
  title: "",
  subtitle: "",
  year: null,
  month: null,
  days_in_month: 31,
  sections: [],
  summary: null,
  dashboard: {
    section_pass_rate: [],
    section_ng_share: [],
    defect_by_phenomenon: [],
    defect_by_series: [],
  },
});

const dayHeaders = computed(() => {
  const n = payload.value.days_in_month || 31;
  return Array.from({ length: n }, (_, i) => i + 1);
});

const tableBlocks = computed(() => {
  const sections = payload.value.sections || [];
  const summary = payload.value.summary;
  if (summary) return [...sections, summary];
  return sections;
});

const dashboard = computed(() => payload.value.dashboard || {});

const SECTION_COLORS = {
  变焦一课: "#548235",
  变焦二课: "#ed7d31",
  变焦三课: "#5b9bd5",
  试做课: "#44546a",
  试验课: "#44546a",
  红外: "#7030a0",
  消费三课: "#00b0f0",
};

const FALLBACK_COLORS = ["#548235", "#ed7d31", "#5b9bd5", "#44546a", "#7030a0", "#00b0f0", "#c45911", "#70ad47"];

function sectionColor(name, idx = 0) {
  return SECTION_COLORS[name] || FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
}

function fmtCount(v) {
  const n = Number(v);
  if (v == null || Number.isNaN(n) || n === 0) return "-";
  return Math.round(n).toString();
}

function fmtRateCell(rate, sent) {
  const s = Number(sent);
  if (rate == null || Number.isNaN(Number(rate)) || !s) return "-";
  const pct = Number(rate) * 100;
  if (pct >= 99.95) return "100%";
  return `${pct.toFixed(1)}%`;
}

function rateClass(rate, sent) {
  const s = Number(sent);
  if (rate == null || Number.isNaN(Number(rate)) || !s) return "";
  if (Number(rate) >= 0.9995) return "rate-good";
  return "rate-low-cell";
}

const trendChart = computed(() => {
  const sections = payload.value.sections || [];
  const days = payload.value.days_in_month || 31;
  const xLabels = Array.from({ length: days }, (_, i) => `${i + 1}日`);
  const series = sections.map((sec, idx) => ({
    name: sec.name,
    type: "line",
    connectNulls: false,
    symbol: "circle",
    symbolSize: 5,
    lineStyle: { width: 2 },
    itemStyle: { color: sectionColor(sec.name, idx) },
    data: (sec.days || []).map((cell) => {
      if (cell.rate == null || !cell.sent) return null;
      return Number((Number(cell.rate) * 100).toFixed(2));
    }),
  }));

  return {
    color: sections.map((s, i) => sectionColor(s.name, i)),
    tooltip: {
      trigger: "axis",
      valueFormatter: (v) => (v == null ? "-" : `${Number(v).toFixed(1)}%`),
    },
    legend: { top: 4, data: sections.map((s) => s.name) },
    grid: { left: 48, right: 24, top: 48, bottom: 36 },
    xAxis: {
      type: "category",
      data: xLabels,
      axisLabel: { interval: 0, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      min: 60,
      max: 110,
      axisLabel: { formatter: "{value}%" },
    },
    series,
  };
});

const sectionPassChart = computed(() => {
  const rows = dashboard.value.section_pass_rate || [];
  if (!rows.length) {
    return emptyChartOption("暂无课室合格率数据");
  }
  return {
    color: rows.map((r, i) => sectionColor(r.name, i)),
    tooltip: {
      trigger: "axis",
      formatter(params) {
        const p = params?.[0];
        if (!p) return "";
        const row = rows[p.dataIndex];
        const rate = row?.rate != null ? `${(row.rate * 100).toFixed(1)}%` : "-";
        return `${p.name}<br/>合格率: ${rate}<br/>合格批/抽检批: ${fmtCount(row?.passed)}/${fmtCount(row?.sent)}`;
      },
    },
    grid: { left: 48, right: 16, top: 28, bottom: 48 },
    xAxis: {
      type: "category",
      data: rows.map((r) => r.name),
      axisLabel: { interval: 0, fontSize: 11, rotate: rows.length > 5 ? 20 : 0 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { formatter: "{value}%" },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 36,
        data: rows.map((r, i) => ({
          value: r.rate != null ? Number((r.rate * 100).toFixed(2)) : null,
          itemStyle: { color: sectionColor(r.name, i) },
        })),
        label: {
          show: true,
          position: "top",
          fontSize: 10,
          formatter: (p) => (p.value == null ? "" : `${p.value}%`),
        },
      },
    ],
  };
});

const sectionNgChart = computed(() => {
  const rows = (dashboard.value.section_ng_share || []).filter((r) => Number(r.value) > 0);
  if (!rows.length) {
    return emptyChartOption("本月无 NG");
  }
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0, type: "scroll" },
    series: [
      {
        type: "pie",
        radius: ["36%", "62%"],
        center: ["50%", "46%"],
        data: rows.map((r, i) => ({
          name: r.name,
          value: r.value,
          itemStyle: { color: sectionColor(r.name, i) },
        })),
        label: { formatter: "{b}\n{d}%", fontSize: 11 },
      },
    ],
  };
});

function paretoChart(rows, emptyText) {
  if (!rows?.length) return emptyChartOption(emptyText);
  return {
    tooltip: {
      trigger: "axis",
      formatter(params) {
        if (!params?.length) return "";
        let html = `${params[0].axisValue}<br/>`;
        for (const p of params) {
          let val = p.value;
          if (p.seriesName === "累积占比" && val != null) val = `${val}%`;
          else if (val == null) val = "-";
          html += `${p.marker}${p.seriesName}: ${val}<br/>`;
        }
        return html;
      },
    },
    legend: { data: ["不良件数", "累积占比"], top: 0 },
    grid: { left: 48, right: 48, top: 36, bottom: 56 },
    xAxis: {
      type: "category",
      data: rows.map((r) => r.name),
      axisLabel: {
        interval: 0,
        fontSize: 10,
        rotate: rows.length > 6 ? 28 : 0,
        formatter: (v) => (String(v).length > 8 ? `${String(v).slice(0, 8)}…` : v),
      },
    },
    yAxis: [
      { type: "value", name: "件数", minInterval: 1 },
      {
        type: "value",
        name: "累积占比",
        min: 0,
        max: 100,
        axisLabel: { formatter: "{value}%" },
      },
    ],
    series: [
      {
        name: "不良件数",
        type: "bar",
        barMaxWidth: 28,
        data: rows.map((r) => r.count),
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "累积占比",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        data: rows.map((r) =>
          r.cum_ratio != null ? Number((Number(r.cum_ratio) * 100).toFixed(1)) : null,
        ),
        label: { show: true, formatter: "{c}%", fontSize: 10 },
      },
    ],
  };
}

const phenomenonChart = computed(() =>
  paretoChart(dashboard.value.defect_by_phenomenon, "本月无现象不良"),
);

const seriesChart = computed(() =>
  paretoChart(dashboard.value.defect_by_series, "本月无机型不良"),
);

function emptyChartOption(text) {
  return {
    title: {
      text: text,
      left: "center",
      top: "middle",
      textStyle: { color: "#94a3b8", fontSize: 13, fontWeight: 400 },
    },
    xAxis: { show: false },
    yAxis: { show: false },
    series: [],
  };
}

function monthInputFromPayload(year, month) {
  if (!year || !month) return "";
  return `${year}-${String(month).padStart(2, "0")}`;
}

async function loadAnalytics() {
  if (!props.workbookId) return;
  loading.value = true;
  error.value = "";
  try {
    const params = new URLSearchParams();
    if (props.sheet) params.set("sheet", props.sheet);
    if (monthInput.value) {
      const [y, m] = monthInput.value.split("-");
      if (y) params.set("year", y);
      if (m) params.set("month", String(Number(m)));
    }
    const res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-analytics?${params}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载失败");
    payload.value = data;
    if (!monthInput.value) {
      monthInput.value = monthInputFromPayload(data.year, data.month);
    }
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    loading.value = false;
  }
}

onMounted(loadAnalytics);
watch(
  () => [props.workbookId, props.sheet],
  () => loadAnalytics(),
);
</script>

<style scoped>
.oqc-analytics {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  padding: 12px 16px;
}

.month-field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.month-field input {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 10px;
}

.block {
  padding: 16px 18px 20px;
}

.block h2 {
  margin: 0 0 12px;
  font-size: 16px;
}

.hint {
  color: var(--muted);
  font-size: 13px;
}

.table-wrap {
  overflow: auto;
  max-width: 100%;
}

.stat-table {
  border-collapse: collapse;
  width: max-content;
  min-width: 100%;
  font-size: 12px;
}

.stat-table th,
.stat-table td {
  border: 1px solid #d0d7de;
  padding: 4px 6px;
  text-align: center;
  white-space: nowrap;
}

.stat-table th {
  background: #31859b;
  color: #fff;
  font-weight: 600;
}

.unit-name {
  font-weight: 700;
  background: #f8fafc;
  vertical-align: middle;
  min-width: 72px;
}

.metric-label {
  background: #f3f6f8;
  font-weight: 600;
  min-width: 56px;
}

.rate-row td {
  font-weight: 600;
}

.rate-good {
  background: #e8f5e9;
  color: #2e7d32;
}

.rate-low-cell {
  background: #ffc7ce;
  color: #c00000;
}

.ttl-col {
  background: #fffde7;
  font-weight: 700;
}

.chart-wrap-lg :deep(.chart) {
  height: 360px;
}

.chart-wrap-md :deep(.chart) {
  height: 280px;
}

.dashboard-block .dash-hint {
  margin: -4px 0 14px;
  color: var(--muted);
  font-size: 12.5px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.dash-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 12px 8px;
  background: #fcfdff;
}

.dash-card h3 {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 650;
  color: #334155;
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

@media (max-width: 960px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
