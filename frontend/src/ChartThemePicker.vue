<template>
  <label class="chart-theme-picker">
    <span>展示风格</span>
    <select :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option value="default">标准</option>
      <option value="screen">科技大屏</option>
    </select>
  </label>
</template>

<script setup>
defineProps({ modelValue: { type: String, default: "default" } });
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.chart-theme-picker { display: grid; gap: 4px; font-size: 12px; color: var(--muted); }
.chart-theme-picker select { min-width: 108px; border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; background: #fff; color: var(--ink); font: inherit; }
</style>
