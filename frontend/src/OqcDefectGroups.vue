<template>
  <div class="defect-groups">
    <div class="defect-groups-head">
      <span class="title">不良明细</span>
      <i class="hint">每组：位置 + 现象 + 数量 + 检验员；可新增多组</i>
    </div>

    <div
      v-for="(g, i) in model"
      :key="i"
      class="defect-row"
    >
      <div class="defect-row-head">
        <span class="idx">第 {{ i + 1 }} 组</span>
        <button
          v-if="model.length > 1"
          type="button"
          class="link-btn"
          title="删除本组"
          @click="remove(i)"
        >删除</button>
      </div>
      <div class="defect-fields">
        <label class="field">
          <span>不良位置</span>
          <ComboField
            :model-value="g.location"
            :options="locationOptions"
            placeholder="外观部位 / 性能工序"
            @update:model-value="(v) => patch(i, 'location', v)"
            @change="(v) => patch(i, 'location', v)"
          />
        </label>
        <label class="field">
          <span>不良现象</span>
          <ComboField
            :model-value="g.phenomenon"
            :options="phenomenonOptionsFor(g.phenomenon)"
            placeholder="输入关键字筛选，如「刮」"
            @update:model-value="(v) => patch(i, 'phenomenon', v)"
            @change="(v) => patch(i, 'phenomenon', v)"
          />
        </label>
        <label class="field qty">
          <span>数量</span>
          <input
            type="number"
            step="any"
            min="0"
            inputmode="decimal"
            :value="g.qty"
            placeholder="数量"
            @input="patch(i, 'qty', $event.target.value)"
            @change="emitChange"
          />
        </label>
        <label class="field">
          <span>检验员</span>
          <ComboField
            :model-value="g.inspector"
            :options="inspectorOptionsFor(g.inspector)"
            placeholder="发现人 / 可多组各选"
            @update:model-value="(v) => patch(i, 'inspector', v)"
            @change="(v) => patch(i, 'inspector', v)"
          />
        </label>
      </div>
    </div>

    <div class="defect-footer">
      <button type="button" class="add-btn" @click="add">+ 添加不良</button>
      <span v-if="filledCount > 0" class="sum">
        共 {{ filledCount }} 种 · 数量合计 {{ qtySum }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import ComboField from "./ComboField.vue";
import {
  buildPhenomenonPickerOptions,
  emptyDefectGroup,
  filledDefectGroups,
} from "./oqcForm.js";

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [emptyDefectGroup()],
  },
  lookups: {
    type: Object,
    default: () => ({}),
  },
  locationOptions: {
    type: Array,
    default: () => [],
  },
  inspectorOptions: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["update:modelValue", "change"]);

const model = computed(() =>
  Array.isArray(props.modelValue) && props.modelValue.length
    ? props.modelValue
    : [emptyDefectGroup()],
);

const filled = computed(() => filledDefectGroups(model.value));
const filledCount = computed(() => filled.value.length);
const qtySum = computed(() => {
  let total = 0;
  for (const g of filled.value) {
    const n = Number(g.qty);
    if (!Number.isNaN(n)) total += n;
  }
  return total;
});

function phenomenonOptionsFor(current) {
  return buildPhenomenonPickerOptions(props.lookups, current);
}

function inspectorOptionsFor(current) {
  const set = new Set((props.inspectorOptions || []).map((v) => String(v || "").trim()).filter(Boolean));
  const cur = String(current || "").trim();
  if (cur) set.add(cur);
  for (const g of model.value || []) {
    const n = String(g.inspector || "").trim();
    if (n) set.add(n);
  }
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

function emitGroups(next) {
  emit("update:modelValue", next);
  emit("change", next);
}

function emitChange() {
  emit("change", model.value);
}

function patch(index, key, value) {
  const next = model.value.map((g, i) =>
    i === index ? { ...g, [key]: value == null ? "" : value } : { ...g },
  );
  emitGroups(next);
}

function add() {
  emitGroups([...model.value, emptyDefectGroup()]);
}

function remove(index) {
  if (model.value.length <= 1) return;
  const next = model.value.filter((_, i) => i !== index);
  emitGroups(next.length ? next : [emptyDefectGroup()]);
}
</script>

<style scoped>
.defect-groups {
  grid-column: 1 / -1;
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px dashed var(--line);
  border-radius: 10px;
  background: #fafbfc;
}
.defect-groups-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}
.defect-groups-head .title {
  font-size: 12px;
  font-weight: 650;
  color: var(--ink);
}
.defect-groups-head .hint {
  font-size: 11px;
  color: #94a3b8;
  font-style: normal;
}
.defect-row {
  display: grid;
  gap: 6px;
  padding: 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--line);
}
.defect-row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.idx {
  font-size: 11px;
  color: var(--muted);
  font-weight: 600;
}
.link-btn {
  border: 0;
  background: transparent;
  color: var(--danger);
  cursor: pointer;
  font-size: 11px;
  padding: 0 2px;
}
.defect-fields {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.3fr) minmax(64px, 0.45fr) minmax(0, 1fr);
  gap: 8px;
}
.field {
  display: grid;
  gap: 4px;
  font-size: 11px;
  color: var(--muted);
}
.field input {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 7px 8px;
  background: #fff;
  color: var(--ink);
  width: 100%;
  box-sizing: border-box;
}
.defect-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.add-btn {
  border: 1px dashed var(--primary);
  background: #fff;
  color: var(--primary);
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}
.add-btn:hover {
  background: color-mix(in srgb, var(--primary) 8%, #fff);
}
.sum {
  font-size: 11px;
  color: var(--muted);
}

@media (max-width: 640px) {
  .defect-fields {
    grid-template-columns: 1fr;
  }
}
</style>
