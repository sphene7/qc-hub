<template>
  <div ref="root" class="combo-field">
    <input
      ref="inputEl"
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
    <Teleport to="body">
      <ul
        v-if="open && filtered.length"
        ref="dropdownEl"
        class="combo-dropdown combo-dropdown--portal"
        :style="dropdownStyle"
        @mousedown.prevent
      >
        <li
          v-for="(opt, i) in filtered"
          :key="opt"
          :class="{ on: i === highlight }"
          @mousedown.prevent="pick(opt)"
        >
          {{ opt }}
        </li>
      </ul>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "change"]);

const root = ref(null);
const inputEl = ref(null);
const dropdownEl = ref(null);
const open = ref(false);
const highlight = ref(0);
const dropdownStyle = ref({});

const filtered = computed(() => {
  const q = String(props.modelValue || "").trim().toLowerCase();
  const opts = (props.options || []).filter((o) => {
    const s = String(o ?? "").trim().toLowerCase();
    return s && s !== "nan" && s !== "none" && s !== "nat" && s !== "null";
  });
  if (!q) return opts;
  return opts.filter((o) => String(o).toLowerCase().includes(q));
});

watch(filtered, () => {
  highlight.value = 0;
});

watch([open, filtered], async () => {
  if (!open.value || !filtered.value.length) return;
  await nextTick();
  placeDropdown();
});

function placeDropdown() {
  const el = inputEl.value || root.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  const maxH = 200;
  const gap = 2;
  const spaceBelow = window.innerHeight - rect.bottom - 8;
  const spaceAbove = rect.top - 8;
  const openUp = spaceBelow < Math.min(maxH, 120) && spaceAbove > spaceBelow;
  const height = Math.min(maxH, openUp ? spaceAbove : spaceBelow);
  dropdownStyle.value = {
    position: "fixed",
    left: `${Math.round(rect.left)}px`,
    width: `${Math.round(rect.width)}px`,
    maxHeight: `${Math.max(80, height)}px`,
    zIndex: 4000,
    ...(openUp
      ? { bottom: `${Math.round(window.innerHeight - rect.top + gap)}px`, top: "auto" }
      : { top: `${Math.round(rect.bottom + gap)}px`, bottom: "auto" }),
  };
}

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
  const inRoot = root.value && root.value.contains(e.target);
  const inDrop = dropdownEl.value && dropdownEl.value.contains(e.target);
  if (!inRoot && !inDrop) open.value = false;
}

function onReposition() {
  if (open.value) placeDropdown();
}

onMounted(() => {
  document.addEventListener("mousedown", onDocMouseDown);
  window.addEventListener("resize", onReposition);
  window.addEventListener("scroll", onReposition, true);
});
onUnmounted(() => {
  document.removeEventListener("mousedown", onDocMouseDown);
  window.removeEventListener("resize", onReposition);
  window.removeEventListener("scroll", onReposition, true);
});
</script>

<style scoped>
.combo-field {
  position: relative;
  width: 100%;
}
.combo-field input {
  width: 100%;
}
</style>

<style>
/* teleported to body — unscoped */
.combo-dropdown.combo-dropdown--portal {
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: #fff;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
  overflow-y: auto;
}
.combo-dropdown.combo-dropdown--portal li {
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  color: var(--ink, #1e293b);
}
.combo-dropdown.combo-dropdown--portal li.on,
.combo-dropdown.combo-dropdown--portal li:hover {
  background: var(--primary-light, #ede7f6);
  color: var(--primary, #7c5cbf);
}
</style>
