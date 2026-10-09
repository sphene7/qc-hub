<template>
  <div class="interface-settings">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="settings-card">
      <h2>项目界面</h2>
      <p class="hint">控制业务模块内各用户可见的功能入口与布局，保存后全员立即生效。</p>

      <label class="setting-row">
        <div class="setting-info">
          <span class="setting-title">显示「原始分表」</span>
          <span class="setting-desc">
            关闭后，项目导航中隐藏「原始分表」Tab。
          </span>
        </div>
        <input v-model="form.show_raw_sheets" type="checkbox" class="toggle" :disabled="saving" />
      </label>

      <label class="setting-row">
        <div class="setting-info">
          <span class="setting-title">显示「导出合并表」</span>
          <span class="setting-desc">
            关闭后，项目页右上角隐藏「导出合并表」按钮（普通用户无法导出 Excel 合并包）。
          </span>
        </div>
        <input v-model="form.show_export_merged" type="checkbox" class="toggle" :disabled="saving" />
      </label>

      <div class="setting-block">
        <div class="setting-info">
          <span class="setting-title">项目导航顺序</span>
          <span class="setting-desc">
            按三个业务模块分别拖动调整 Tab 顺序。各项目仅显示其拥有的 Tab（如无抽检数据则自动跳过）。
          </span>
        </div>

        <div class="module-tabs">
          <button
            v-for="mod in moduleKeys"
            :key="mod"
            type="button"
            class="module-tab"
            :class="{ active: activeModule === mod }"
            @click="activeModule = mod"
          >
            {{ moduleLabels[mod] }}
          </button>
        </div>

        <ul class="nav-order-list">
          <li
            v-for="(key, index) in form.project_nav_orders[activeModule]"
            :key="`${activeModule}-${key}`"
            class="nav-order-item"
            :class="{
              dragging: dragModule === activeModule && dragIndex === index,
              'drag-over': dragModule === activeModule && dragOverIndex === index && dragIndex !== index,
            }"
            draggable="true"
            @dragstart="onDragStart(activeModule, index, $event)"
            @dragover.prevent="onDragOver(activeModule, index)"
            @drop.prevent="onDrop(activeModule, index)"
            @dragend="onDragEnd"
          >
            <span class="drag-handle" title="拖动排序">⋮⋮</span>
            <span class="nav-order-label">{{ navLabel(activeModule, key) }}</span>
            <span class="nav-order-key">{{ key }}</span>
          </li>
        </ul>
      </div>

      <p v-if="saveMessage" class="save-message">{{ saveMessage }}</p>

      <div class="actions">
        <button class="btn-primary" :disabled="saving || !dirty" @click="save">
          {{ saving ? "保存中..." : "保存设置" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { authFetch } from "./api.js";
import {
  BUSINESS_MODULE_KEYS,
  BUSINESS_MODULE_LABELS,
  migrateNavOrders,
  normalizeNavOrders,
  navTabLabel,
} from "./projectNav.js";

const emit = defineEmits(["updated"]);

const moduleKeys = BUSINESS_MODULE_KEYS;
const moduleLabels = BUSINESS_MODULE_LABELS;

const loading = ref(false);
const error = ref("");
const saving = ref(false);
const saveMessage = ref("");
const activeModule = ref("inspection");
const dragModule = ref(null);
const dragIndex = ref(null);
const dragOverIndex = ref(null);

const defaultOrders = () => normalizeNavOrders({});

const form = ref({
  show_raw_sheets: true,
  show_export_merged: true,
  project_nav_orders: defaultOrders(),
});
const saved = ref({
  show_raw_sheets: true,
  show_export_merged: true,
  project_nav_orders: defaultOrders(),
});

const dirty = computed(() => {
  if (form.value.show_raw_sheets !== saved.value.show_raw_sheets) return true;
  if (form.value.show_export_merged !== saved.value.show_export_merged) return true;
  return JSON.stringify(form.value.project_nav_orders) !== JSON.stringify(saved.value.project_nav_orders);
});

onMounted(loadSettings);

function navLabel(moduleKey, tabKey) {
  return navTabLabel(moduleKey, tabKey);
}

function onDragStart(moduleKey, index, event) {
  dragModule.value = moduleKey;
  dragIndex.value = index;
  dragOverIndex.value = index;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(index));
  }
}

function onDragOver(moduleKey, index) {
  if (dragModule.value !== moduleKey) return;
  dragOverIndex.value = index;
}

function onDrop(moduleKey, index) {
  if (dragModule.value !== moduleKey) return;
  const from = dragIndex.value;
  if (from == null || from === index) return;
  const order = [...form.value.project_nav_orders[moduleKey]];
  const [item] = order.splice(from, 1);
  order.splice(index, 0, item);
  form.value.project_nav_orders = {
    ...form.value.project_nav_orders,
    [moduleKey]: order,
  };
  dragIndex.value = index;
  dragOverIndex.value = index;
}

function onDragEnd() {
  dragModule.value = null;
  dragIndex.value = null;
  dragOverIndex.value = null;
}

async function loadSettings() {
  loading.value = true;
  error.value = "";
  try {
    const res = await authFetch("/api/admin/settings");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载失败");
    const orders = migrateNavOrders(data);
    form.value = {
      show_raw_sheets: data.show_raw_sheets !== false,
      show_export_merged: data.show_export_merged !== false,
      project_nav_orders: orders,
    };
    saved.value = {
      show_raw_sheets: form.value.show_raw_sheets,
      show_export_merged: form.value.show_export_merged,
      project_nav_orders: JSON.parse(JSON.stringify(orders)),
    };
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  saveMessage.value = "";
  try {
    const res = await authFetch("/api/admin/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        show_raw_sheets: form.value.show_raw_sheets,
        show_export_merged: form.value.show_export_merged,
        project_nav_orders: form.value.project_nav_orders,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    const orders = migrateNavOrders(data.settings || form.value);
    saved.value = {
      show_raw_sheets: form.value.show_raw_sheets,
      show_export_merged: form.value.show_export_merged,
      project_nav_orders: JSON.parse(JSON.stringify(orders)),
    };
    form.value.project_nav_orders = orders;
    saveMessage.value = data.message || "已保存";
    emit("updated");
  } catch (err) {
    error.value = err.message;
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.interface-settings {
  min-height: 200px;
}

.loading,
.error {
  text-align: center;
  padding: 40px 20px;
}

.error {
  color: var(--danger);
  background: #fee;
  border-radius: 8px;
}

.settings-card {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 24px;
}

.settings-card h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

.hint {
  margin: 0 0 20px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.setting-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 0;
  border-top: 1px solid var(--line);
  cursor: pointer;
}

.setting-block {
  padding: 16px 0;
  border-top: 1px solid var(--line);
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  margin-bottom: 12px;
}

.setting-title {
  font-weight: 600;
  color: var(--ink);
}

.setting-desc {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
}

.toggle {
  width: 18px;
  height: 18px;
  margin-top: 4px;
  accent-color: var(--primary);
  flex-shrink: 0;
}

.module-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.module-tab {
  padding: 8px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fafafa;
  color: var(--ink);
  font-size: 13px;
  cursor: pointer;
}

.module-tab.active {
  border-color: var(--primary);
  background: var(--primary-light, #ede9fe);
  color: var(--primary);
  font-weight: 600;
}

.nav-order-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-order-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fafafa;
  cursor: grab;
  user-select: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.nav-order-item.dragging {
  opacity: 0.55;
  cursor: grabbing;
}

.nav-order-item.drag-over {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-light);
}

.drag-handle {
  color: var(--muted);
  font-size: 14px;
  letter-spacing: -2px;
  flex-shrink: 0;
}

.nav-order-label {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
}

.nav-order-key {
  font-size: 11px;
  color: var(--muted);
  font-family: ui-monospace, monospace;
}

.save-message {
  margin: 12px 0 0;
  color: #16a34a;
  font-size: 13px;
}

.actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.btn-primary {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  background: var(--primary);
  color: white;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
