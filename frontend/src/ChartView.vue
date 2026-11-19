<template>
  <div ref="el" class="chart"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps({
  option: { type: Object, default: () => ({}) },
  theme: { type: String, default: "default" },
});
const el = ref(null);
let chart;

onMounted(() => {
  initChart();
  window.addEventListener("resize", resize);
});

watch(
  () => props.option,
  (opt) => chart && chart.setOption(themedOption(opt || {}), true),
  { deep: true }
);

watch(
  () => props.theme,
  () => {
    if (!el.value) return;
    initChart();
  },
);

onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  chart?.dispose();
});

function resize() {
  chart?.resize();
}

function initChart() {
  chart?.dispose();
  chart = echarts.init(el.value);
  chart.setOption(themedOption(props.option || {}), true);
}

/** 暗色背景用中低亮度、降饱和色，避免霓虹刺眼 */
const SCREEN_PALETTE = [
  "#8fa3c4",
  "#7eae9a",
  "#c4a574",
  "#a48fb0",
  "#79a8b5",
  "#b08a78",
  "#8a9a72",
  "#9a8490",
  "#6f95a8",
  "#b09c6e",
  "#8790a8",
  "#9a7f8c",
];

function softenHex(color, idx = 0) {
  if (!color || typeof color !== "string") return SCREEN_PALETTE[idx % SCREEN_PALETTE.length];
  const raw = color.trim();
  // 近白 / 高亮色 → 换柔和色
  if (/^#fff(f)?$/i.test(raw) || /^#f[5-9a-f]{5}$/i.test(raw) || /^#e[89a-f][d-f]/i.test(raw)) {
    return SCREEN_PALETTE[idx % SCREEN_PALETTE.length];
  }
  return raw;
}

function themedOption(option) {
  if (props.theme !== "screen") return option;
  const next = { ...option };
  const axis = (value) => {
    if (!value) return value;
    const item = {
      ...value,
      axisLine: { ...(value.axisLine || {}), lineStyle: { ...(value.axisLine?.lineStyle || {}), color: "rgba(180, 190, 220, .28)" } },
      axisLabel: { ...(value.axisLabel || {}), color: "rgba(210, 215, 230, .55)" },
      splitLine: { ...(value.splitLine || {}), lineStyle: { ...(value.splitLine?.lineStyle || {}), color: "rgba(160, 170, 200, .08)" } },
      nameTextStyle: { ...(value.nameTextStyle || {}), color: "rgba(210, 215, 230, .55)" },
    };
    return item;
  };
  next.backgroundColor = "transparent";
  next.color = SCREEN_PALETTE;
  next.textStyle = { ...(next.textStyle || {}), color: "rgba(230, 232, 240, .88)" };
  next.tooltip = {
    ...(next.tooltip || {}),
    backgroundColor: "rgba(22, 26, 38, .92)",
    borderColor: "rgba(160, 170, 200, .28)",
    textStyle: { color: "rgba(230, 232, 240, .9)" },
  };
  next.legend = {
    ...(next.legend || {}),
    textStyle: { ...(next.legend?.textStyle || {}), color: "rgba(200, 205, 220, .62)" },
  };
  next.xAxis = Array.isArray(next.xAxis) ? next.xAxis.map(axis) : axis(next.xAxis);
  next.yAxis = Array.isArray(next.yAxis) ? next.yAxis.map(axis) : axis(next.yAxis);
  next.series = (next.series || []).map((series, idx) => {
    const baseLine = series.lineStyle || {};
    const baseItem = series.itemStyle || {};
    const isPie = series.type === "pie";
    // 饼图按扇区上色，禁止整系列强制单色（否则会糊成一块）
    if (isPie) {
      const data = Array.isArray(series.data)
        ? series.data.map((d, i) => {
            if (!d || typeof d !== "object") return d;
            const own = d.itemStyle?.color;
            return {
              ...d,
              itemStyle: {
                ...(d.itemStyle || {}),
                color: own ? softenHex(own, i) : SCREEN_PALETTE[i % SCREEN_PALETTE.length],
                opacity: d.itemStyle?.opacity ?? 0.95,
              },
            };
          })
        : series.data;
      return {
        ...series,
        data,
        itemStyle: { ...baseItem, opacity: baseItem.opacity ?? 0.95 },
        label: { ...(series.label || {}), color: "rgba(220, 224, 235, .72)" },
      };
    }
    const soft = softenHex(series.itemStyle?.color || series.lineStyle?.color, idx);
    return {
      ...series,
      itemStyle: { ...baseItem, color: soft, opacity: baseItem.opacity ?? 0.92 },
      lineStyle: {
        ...baseLine,
        color: soft,
        width: baseLine.width ?? 2,
        opacity: Math.min(baseLine.opacity ?? 0.82, 0.85),
      },
      label: { ...(series.label || {}), color: "rgba(220, 224, 235, .72)" },
      // 面积/散点等避免高亮发光
      areaStyle: series.areaStyle
        ? { ...series.areaStyle, opacity: Math.min(series.areaStyle.opacity ?? 0.18, 0.22) }
        : series.areaStyle,
    };
  });
  return next;
}
</script>

<style scoped>
.chart { width: 100%; height: 240px; }
</style>
