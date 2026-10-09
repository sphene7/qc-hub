<template>
  <div ref="rootRef" class="view-menu-wrap">
    <button type="button" class="ghost-btn view-menu-btn" @click.stop="open = !open">
      视图
      <span v-if="badge" class="view-badge">{{ badge }}</span>
    </button>
    <div v-if="open" class="view-menu-panel" @click.stop>
      <div class="view-menu-section">
        <div class="view-menu-head">
          <span>显示列</span>
          <button type="button" class="link-btn" @click="showAll">全部显示</button>
        </div>
        <div class="view-menu-list">
          <label v-for="col in columns" :key="col" class="view-menu-item">
            <input
              type="checkbox"
              :checked="!hiddenSet.has(col)"
              @change="toggleColumn(col)"
            />
            <span>{{ col }}</span>
          </label>
        </div>
      </div>
      <label v-if="showFilterToggle" class="view-menu-filter-toggle">
        <input type="checkbox" :checked="filtersOpen" @change="$emit('update:filtersOpen', $event.target.checked)" />
        <span>显示筛选栏</span>
      </label>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";

const props = defineProps({
  columns: { type: Array, default: () => [] },
  hiddenColumns: { type: Array, default: () => [] },
  filtersOpen: { type: Boolean, default: false },
  filtersActive: { type: Boolean, default: false },
  showFilterToggle: { type: Boolean, default: true },
});

const emit = defineEmits(["update:hiddenColumns", "update:filtersOpen"]);

const rootRef = ref(null);
const open = ref(false);

const hiddenSet = computed(() => new Set(props.hiddenColumns));

const visibleCount = computed(() => props.columns.filter((c) => !hiddenSet.value.has(c)).length);

const badge = computed(() => {
  const parts = [];
  if (props.columns.length && visibleCount.value < props.columns.length) {
    parts.push(`${visibleCount.value}/${props.columns.length}`);
  }
  if (props.filtersActive) parts.push("筛");
  return parts.join(" · ");
});

function toggleColumn(col) {
  const set = new Set(props.hiddenColumns);
  if (set.has(col)) set.delete(col);
  else set.add(col);
  emit("update:hiddenColumns", [...set]);
}

function showAll() {
  emit("update:hiddenColumns", []);
}

function onDocumentClick(e) {
  if (!open.value) return;
  if (rootRef.value && !rootRef.value.contains(e.target)) open.value = false;
}

onMounted(() => document.addEventListener("click", onDocumentClick));
onUnmounted(() => document.removeEventListener("click", onDocumentClick));
</script>

<style scoped>
.view-menu-wrap {
  position: relative;
}

.view-menu-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.view-badge {
  font-size: 11px;
  color: var(--muted);
  font-weight: 500;
}

.view-menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 40;
  width: min(320px, 80vw);
  max-height: min(460px, 65vh);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.view-menu-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid var(--line);
}

.view-menu-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 600;
  background: #fafafa;
}

.link-btn {
  border: none;
  background: none;
  color: var(--primary);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.view-menu-list {
  overflow-y: auto;
  padding: 4px 0;
}

.view-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
}

.view-menu-item:hover {
  background: var(--bg-accent);
}

.view-menu-filter-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
}

.view-menu-filter-toggle input {
  accent-color: var(--primary);
}
</style>
