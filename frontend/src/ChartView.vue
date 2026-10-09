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

function themedOption(option) {
  if (props.theme !== "screen") return option;
  const next = { ...option };
  const axis = (value) => {
    if (!value) return value;
    const item = {
      ...value,
      axisLine: { ...(value.axisLine || {}), lineStyle: { ...(value.axisLine?.lineStyle || {}), color: "rgba(216, 180, 254, .32)" } },
      axisLabel: { ...(value.axisLabel || {}), color: "rgba(237, 233, 254, .58)" },
      splitLine: { ...(value.splitLine || {}), lineStyle: { ...(value.splitLine?.lineStyle || {}), color: "rgba(216, 180, 254, .08)" } },
      nameTextStyle: { ...(value.nameTextStyle || {}), color: "rgba(237, 233, 254, .58)" },
    };
    return item;
  };
  next.backgroundColor = "transparent";
  next.color = ["#c4b5fd", "#a5b4fc", "#ddd6fe", "#e9d5ff", "#b794f6", "#d8b4fe"];
  next.textStyle = { ...(next.textStyle || {}), color: "#f5f0ff" };
  next.tooltip = { ...(next.tooltip || {}), backgroundColor: "rgba(30, 18, 56, .88)", borderColor: "rgba(216, 180, 254, .32)", textStyle: { color: "#f5f0ff" } };
  next.legend = { ...(next.legend || {}), textStyle: { ...(next.legend?.textStyle || {}), color: "rgba(237, 233, 254, .62)" } };
  next.xAxis = Array.isArray(next.xAxis) ? next.xAxis.map(axis) : axis(next.xAxis);
  next.yAxis = Array.isArray(next.yAxis) ? next.yAxis.map(axis) : axis(next.yAxis);
  next.series = (next.series || []).map((series) => ({ ...series, label: { ...(series.label || {}), color: "rgba(245, 240, 255, .85)" } }));
  return next;
}
</script>

<style scoped>
.chart { width: 100%; height: 240px; }
</style>
