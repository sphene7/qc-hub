<template>
  <div ref="root" class="combo-field">
    <input
      type="text"
      :value="modelValue"
      :placeholder="placeholder"
      autocomplete="off"
      @input="onInput"
      @focus="onFocus"
      @blur="onBlur"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter.prevent="selectHighlighted"
      @keydown.escape="close"
    />
    <ul v-if="open && filtered.length" class="combo-dropdown">
      <li
        v-for="(opt, i) in filtered"
        :key="opt"
        :class="{ on: i === highlight }"
        @mousedown.prevent="pick(opt)"
      >
        {{ opt }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "change"]);

const root = ref(null);
const open = ref(false);
const highlight = ref(0);

const filtered = computed(() => {
  const q = String(props.modelValue || "").trim().toLowerCase();
  const opts = props.options || [];
  if (!q) return opts;
  return opts.filter((o) => String(o).toLowerCase().includes(q));
});

watch(filtered, () => {
  highlight.value = 0;
});

function onInput(e) {
  emit("update:modelValue", e.target.value);
  open.value = true;
}

function onFocus() {
  open.value = true;
}

function onBlur() {
  window.setTimeout(() => {
    open.value = false;
  }, 120);
}

function pick(opt) {
  emit("update:modelValue", opt);
  emit("change", opt);
  open.value = false;
}

function close() {
  open.value = false;
}

function move(dir) {
  if (!open.value || !filtered.value.length) return;
  const n = filtered.value.length;
  highlight.value = (highlight.value + dir + n) % n;
}

function selectHighlighted() {
  if (open.value && filtered.value[highlight.value]) {
    pick(filtered.value[highlight.value]);
  } else {
    open.value = false;
    emit("change", props.modelValue);
  }
}

function onDocMouseDown(e) {
  if (root.value && !root.value.contains(e.target)) {
    open.value = false;
  }
}

onMounted(() => document.addEventListener("mousedown", onDocMouseDown));
onUnmounted(() => document.removeEventListener("mousedown", onDocMouseDown));
</script>

<style scoped>
.combo-field {
  position: relative;
  width: 100%;
}
.combo-field input {
  width: 100%;
}
.combo-dropdown {
  position: absolute;
  z-index: 40;
  left: 0;
  right: 0;
  top: calc(100% + 2px);
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: #fff;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
  max-height: 200px;
  overflow-y: auto;
}
.combo-dropdown li {
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  color: var(--ink, #1e293b);
}
.combo-dropdown li.on,
.combo-dropdown li:hover {
  background: var(--primary-light, #ede7f6);
  color: var(--primary, #7c5cbf);
}
</style>
