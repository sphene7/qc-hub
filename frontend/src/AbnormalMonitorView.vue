<template>
  <div class="abnormal-monitor chart-theme-screen theme-screen">
    <div class="monitor-header card">
      <div>
        <h1>异常监控大屏</h1>
        <p class="hint">KK · 客诉 · 抽检 — 异常结案率 / NG率 · 月度趋势 · 未结案清单</p>
      </div>
      <div class="header-actions">
        <button type="button" class="ghost-btn" :disabled="loading" @click="loadData">刷新</button>
        <button type="button" class="ghost-btn" @click="toggleBrowserFullscreen">
          {{ isBrowserFullscreen ? '退出全屏' : '全屏' }}
        </button>
        <button type="button" class="ghost-btn" @click="handleBack">返回首页</button>
      </div>
    </div>

    <div v-if="loading" class="loading-hint">正在加载监控数据…</div>
    <div v-else-if="error" class="error-hint">{{ error }}</div>
    <div v-else-if="!currentPanel" class="loading-hint">暂无可访问的业务模块数据</div>

    <div v-else class="monitor-body">
      <div class="monitor-main">
        <div class="module-badge card">{{ currentPanel.label }} · {{ currentPanel.metric_label }}</div>

        <div class="monitor-grid">
          <section class="zone zone-pie card">
            <h2 class="panel-title">{{ currentPanel.metric_label }}分布</h2>
            <div class="pie-wrap">
              <ChartView :option="pieChart" theme="screen" />
            </div>
            <div class="summary-stats">
              <span>总计 {{ fmtInt(currentPanel.summary?.total) }}</span>
              <span>{{ currentPanel.module === 'sampling' ? 'NG' : '未结' }} {{ fmtInt(currentPanel.summary?.open) }}</span>
            </div>
          </section>

          <section class="zone zone-trend card">
            <h2 class="panel-title">月度异常/完成件数 · 结案率趋势</h2>
            <div class="trend-wrap">
              <ChartView :option="trendChart" theme="screen" />
            </div>
          </section>

          <section class="zone zone-list card">
            <div class="list-head">
              <h2 class="panel-title">未结案清单</h2>
              <div class="list-tools">
                <span class="hint">{{ currentPanel.open_items?.length || 0 }} 条</span>
                <button type="button" class="ghost-btn" @click="toggleSort">
                  时间 {{ sort === 'desc' ? '↓ 新→旧' : '↑ 旧→新' }}
                </button>
              </div>
            </div>
            <div ref="scrollWrap" class="scroll-wrap" @mouseenter="pauseScroll" @mouseleave="resumeScroll">
              <table class="stat-table monitor-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>摘要</th>
                    <th>责任单位</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in displayRows" :key="row._key">
                    <td>{{ fmtDate(row.date) }}</td>
                    <td class="desc-cell" :title="row.title">{{ row.title }}</td>
                    <td>{{ row.unit }}</td>
                    <td><span class="status-tag">{{ row.status }}</span></td>
                  </tr>
                  <tr v-if="!displayRows.length">
                    <td colspan="4" class="empty-cell">暂无未结案记录</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </div>

      <aside class="page-flip card" aria-label="模块翻页">
        <button type="button" class="flip-btn" :disabled="pageIndex <= 0" @click="prevPage" aria-label="上一模块">
          <span class="chev">▲</span>
        </button>
        <div class="flip-indicator">
          <span class="flip-current">{{ pageIndex + 1 }}</span>
          <span class="flip-sep">/</span>
          <span class="flip-total">{{ panels.length }}</span>
        </div>
        <button
          type="button"
          class="flip-btn"
          :disabled="pageIndex >= panels.length - 1"
          @click="nextPage"
          aria-label="下一模块"
        >
          <span class="chev">▼</span>
        </button>
        <div class="flip-labels">
          <span
            v-for="(p, i) in panels"
            :key="p.module"
            class="flip-label"
            :class="{ on: i === pageIndex }"
            @click="pageIndex = i"
          >{{ p.label }}</span>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import ChartView from "./ChartView.vue";
import { authFetch } from "./api.js";

const emit = defineEmits(["back"]);

const loading = ref(false);
const error = ref("");
const panels = ref([]);
const pageIndex = ref(0);
const sort = ref("desc");
const scrollWrap = ref(null);
const isBrowserFullscreen = ref(Boolean(document.fullscreenElement));
let scrollTimer = null;
let scrollPaused = false;

const currentPanel = computed(() => panels.value[pageIndex.value] || null);

const displayRows = computed(() => {
  const items = currentPanel.value?.open_items || [];
  const doubled = items.length > 6 ? [...items, ...items] : items;
  return doubled.map((row, i) => ({ ...row, _key: `${row.id}-${i}` }));
});

const pieChart = computed(() => {
  const panel = currentPanel.value;
  const slices = (panel?.summary?.pie || []).filter((s) => s.value > 0);
  const center = panel?.summary?.pie_center || "—";
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0, type: "scroll" },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["50%", "46%"],
        avoidLabelOverlap: true,
        label: { show: true, formatter: "{b}\n{d}%", fontSize: 11 },
        data: slices.length ? slices : [{ name: "暂无数据", value: 1, itemStyle: { color: "rgba(255,255,255,.12)" } }],
        itemStyle: { borderColor: "rgba(30,18,56,.35)", borderWidth: 2 },
      },
      {
        type: "pie",
        radius: ["0%", "0%"],
        label: {
          show: true,
          position: "center",
          formatter: () => `{a|${center}}\n{b|${panel?.metric_label || ""}}`,
          rich: {
            a: { fontSize: 22, fontWeight: 700, color: "#f5f0ff", lineHeight: 30 },
            b: { fontSize: 12, color: "rgba(237,233,254,.62)", lineHeight: 18 },
          },
        },
        data: [{ value: 1, name: "" }],
        silent: true,
      },
    ],
  };
});

const trendChart = computed(() => {
  const rows = currentPanel.value?.monthly_trend || [];
  const labels = rows.map((r) => r.month);
  return {
    tooltip: {
      trigger: "axis",
      formatter(params) {
        if (!params?.length) return "";
        let html = `${params[0].axisValue}<br/>`;
        for (const p of params) {
          let val = p.value;
          if (p.seriesName === "结案率" && val != null) val = `${val}%`;
          else if (val == null) val = "-";
          html += `${p.marker}${p.seriesName}: ${val}<br/>`;
        }
        return html;
      },
    },
    legend: { data: ["异常件数", "完成件数", "结案率"], bottom: 0 },
    grid: { left: 48, right: 48, bottom: 56, top: 36 },
    xAxis: { type: "category", data: labels },
    yAxis: [
      { type: "value", name: "件数" },
      { type: "value", name: "结案率", axisLabel: { formatter: "{value}%" }, max: 100 },
    ],
    series: [
      {
        name: "异常件数",
        type: "bar",
        data: rows.map((r) => r.abnormal),
        barMaxWidth: 22,
        barGap: "15%",
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "完成件数",
        type: "bar",
        data: rows.map((r) => r.completed ?? r.closed),
        barMaxWidth: 22,
        label: { show: true, position: "top", fontSize: 10 },
      },
      {
        name: "结案率",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        data: rows.map((r) => (r.close_rate != null ? Number((r.close_rate * 100).toFixed(1)) : null)),
        label: { show: true, formatter: "{c}%", fontSize: 10 },
      },
    ],
  };
});

function fmtInt(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString();
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function prevPage() {
  if (pageIndex.value > 0) pageIndex.value -= 1;
}

function nextPage() {
  if (pageIndex.value < panels.value.length - 1) pageIndex.value += 1;
}

function toggleSort() {
  sort.value = sort.value === "desc" ? "asc" : "desc";
  loadData();
}

function pauseScroll() {
  scrollPaused = true;
}

function resumeScroll() {
  scrollPaused = false;
}

function startAutoScroll() {
  stopAutoScroll();
  scrollTimer = window.setInterval(() => {
    const el = scrollWrap.value;
    if (!el || scrollPaused) return;
    const max = el.scrollHeight - el.clientHeight;
    if (max <= 4) return;
    if (el.scrollTop >= max - 1) {
      el.scrollTop = 0;
    } else {
      el.scrollTop += 1;
    }
  }, 40);
}

function stopAutoScroll() {
  if (scrollTimer) {
    clearInterval(scrollTimer);
    scrollTimer = null;
  }
}

function syncBrowserFullscreen() {
  isBrowserFullscreen.value = Boolean(document.fullscreenElement);
}

async function enterBrowserFullscreen() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen?.();
    }
  } catch {
    /* ignore */
  }
  syncBrowserFullscreen();
}

async function toggleBrowserFullscreen() {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen?.();
    } else {
      await document.documentElement.requestFullscreen?.();
    }
  } catch {
    /* ignore */
  }
  syncBrowserFullscreen();
}

function handleBack() {
  if (document.fullscreenElement) {
    document.exitFullscreen?.().catch(() => {});
  }
  document.body.classList.remove("monitor-fullscreen");
  document.documentElement.style.removeProperty("background");
  emit("back");
}

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const res = await authFetch(`/api/abnormal-monitor?sort=${sort.value}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载失败");
    panels.value = data.modules || [];
    if (pageIndex.value >= panels.value.length) pageIndex.value = 0;
  } catch (err) {
    error.value = err.message;
    panels.value = [];
  } finally {
    loading.value = false;
    startAutoScroll();
  }
}

watch(pageIndex, () => {
  stopAutoScroll();
  if (scrollWrap.value) scrollWrap.value.scrollTop = 0;
  startAutoScroll();
});

onMounted(() => {
  loadData();
  enterBrowserFullscreen();
  document.addEventListener("fullscreenchange", syncBrowserFullscreen);
});

onBeforeUnmount(() => {
  stopAutoScroll();
  document.removeEventListener("fullscreenchange", syncBrowserFullscreen);
  document.body.classList.remove("monitor-fullscreen");
  document.documentElement.style.removeProperty("background");
});

defineExpose({ refresh: loadData });
</script>

<style scoped>
.abnormal-monitor {
  position: fixed;
  inset: 0;
  z-index: 300;
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 12px 14px;
  box-sizing: border-box;
  border-radius: 0 !important;
}

.monitor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 16px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.monitor-header h1 {
  margin: 0;
  font-size: 22px;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.monitor-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

.monitor-main {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.module-badge {
  display: inline-block;
  padding: 5px 12px;
  margin-bottom: 8px;
  font-size: 13px;
  letter-spacing: .04em;
  flex-shrink: 0;
}

.monitor-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(0, 2fr);
  grid-template-rows: minmax(0, 38fr) minmax(0, 62fr);
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.zone {
  padding: 14px 16px;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.zone-pie {
  grid-column: 1;
  grid-row: 1;
}

.zone-trend {
  grid-column: 2;
  grid-row: 1;
}

.zone-list {
  grid-column: 1 / -1;
  grid-row: 2;
}

.panel-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
}

.pie-wrap,
.trend-wrap {
  flex: 1;
  min-height: 220px;
}

.pie-wrap :deep(.chart),
.trend-wrap :deep(.chart) {
  height: 100%;
  min-height: 220px;
}

.summary-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: rgba(237, 233, 254, .62);
  margin-top: 4px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.list-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scroll-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, .08);
}

.monitor-table {
  width: 100%;
}

.desc-cell {
  max-width: 360px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty-cell {
  text-align: center;
  padding: 24px;
  color: rgba(237, 233, 254, .5);
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  background: rgba(251, 191, 36, .15);
  color: #fde68a;
  border: 1px solid rgba(251, 191, 36, .25);
}

.page-flip {
  width: 56px;
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  align-self: stretch;
  justify-content: center;
  background: linear-gradient(180deg, rgba(255,255,255,.08) 0%, rgba(255,255,255,.03) 100%) !important;
}

.flip-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, .18);
  background: rgba(255, 255, 255, .92);
  color: #524668;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: transform .15s, opacity .15s;
}

.flip-btn:hover:not(:disabled) {
  transform: scale(1.05);
}

.flip-btn:disabled {
  opacity: .35;
  cursor: not-allowed;
}

.chev {
  font-size: 12px;
  line-height: 1;
}

.flip-indicator {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 13px;
  color: rgba(237, 233, 254, .85);
  letter-spacing: .08em;
}

.flip-current {
  font-size: 16px;
  font-weight: 700;
}

.flip-labels {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
}

.flip-label {
  font-size: 11px;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  color: rgba(237, 233, 254, .45);
  cursor: pointer;
  transition: color .15s;
}

.flip-label.on {
  color: #e9d5ff;
  font-weight: 600;
}

.loading-hint,
.error-hint {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.error-hint {
  color: #fecaca;
}

@media (max-width: 1100px) {
  .monitor-body {
    grid-template-columns: 1fr;
  }

  .page-flip {
    flex-direction: row;
    width: auto;
    justify-content: center;
    padding: 10px 16px;
  }

  .flip-indicator {
    writing-mode: horizontal-tb;
  }

  .flip-labels {
    flex-direction: row;
  }

  .flip-label {
    writing-mode: horizontal-tb;
  }

  .monitor-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto 1fr;
  }

  .zone-pie,
  .zone-trend,
  .zone-list {
    grid-column: 1;
  }

  .zone-pie { grid-row: 1; }
  .zone-trend { grid-row: 2; }
  .zone-list { grid-row: 3; }
}
</style>
