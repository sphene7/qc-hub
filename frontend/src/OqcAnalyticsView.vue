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

const SECTION_COLORS = {
  变焦一课: "#548235",
  变焦二课: "#ed7d31",
  变焦三课: "#5b9bd5",
  试做课: "#44546a",
  试验课: "#44546a",
};

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
  const series = sections.map((sec) => ({
    name: sec.name,
    type: "line",
    connectNulls: false,
    symbol: "circle",
    symbolSize: 5,
    lineStyle: { width: 2 },
    itemStyle: { color: SECTION_COLORS[sec.name] },
    data: (sec.days || []).map((cell) => {
      if (cell.rate == null || !cell.sent) return null;
      return Number((Number(cell.rate) * 100).toFixed(2));
    }),
  }));

  return {
    color: Object.values(SECTION_COLORS),
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
</style>
