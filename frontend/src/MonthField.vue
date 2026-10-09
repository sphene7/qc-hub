<template>
  <div class="month-field">
    <select class="year-select" :value="yearPart" @change="onYearChange">
      <option value="">年</option>
      <option v-for="y in yearOptions" :key="y" :value="String(y)">{{ y }}年</option>
    </select>
    <select class="month-select" :value="monthPart" @change="onMonthChange">
      <option value="">月</option>
      <option v-for="m in 12" :key="m" :value="String(m)">{{ m }}月</option>
    </select>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { toMonthInputValue } from "./monthField.js";

const props = defineProps({
  modelValue: { type: String, default: "" },
  minYear: { type: Number, default: 1990 },
  maxYear: { type: Number, default: 2050 },
});

const emit = defineEmits(["update:modelValue", "change"]);

const yearOptions = computed(() => {
  const out = [];
  for (let y = props.maxYear; y >= props.minYear; y -= 1) out.push(y);
  return out;
});

const parsed = computed(() => {
  const raw = toMonthInputValue(props.modelValue, new Date().getFullYear());
  if (!raw) return { year: "", month: "" };
  const m = raw.match(/^(\d{4})-(\d{2})$/);
  if (!m) return { year: "", month: "" };
  return { year: m[1], month: String(parseInt(m[2], 10)) };
});

const yearPart = computed(() => parsed.value.year);
const monthPart = computed(() => parsed.value.month);

function emitValue(year, month) {
  if (!year || !month) {
    emit("update:modelValue", "");
    emit("change", "");
    return;
  }
  const next = `${year}-${String(month).padStart(2, "0")}`;
  emit("update:modelValue", next);
  emit("change", next);
}

function onYearChange(e) {
  const year = e.target.value;
  const month = monthPart.value || "1";
  emitValue(year, month);
}

function onMonthChange(e) {
  const month = e.target.value;
  const year = yearPart.value || String(new Date().getFullYear());
  emitValue(year, month);
}
</script>

<style scoped>
.month-field {
  display: flex;
  gap: 8px;
  width: 100%;
}

.year-select,
.month-select {
  flex: 1;
  min-width: 0;
}
</style>
