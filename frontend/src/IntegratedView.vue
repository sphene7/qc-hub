<template>
  <div class="integrated-view">
    <div class="view-header">
      <h2>{{ mainSheet.label || mainSheet.name }}</h2>
      <span class="badge">整合视图</span>
      <span class="info">已整合 {{ lookupSheets.length }} 个配置表</span>
      <button class="primary-btn" @click="showAddForm = true">+ 新增数据</button>
    </div>

    <!-- Data Table -->
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="col in displayColumns" :key="col.key">
              {{ col.label }}
              <span v-if="isLookupColumn(col.key)" class="lookup-indicator" title="关联配置表">🔗</span>
            </th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in displayData" :key="idx">
            <td v-for="col in displayColumns" :key="col.key">
              <span v-if="editingRow !== idx">
                {{ formatValue(row[col.key]) }}
              </span>
              <input 
                v-else-if="!isLookupColumn(col.key) && col.role !== 'measure'"
                v-model="editingData[col.key]"
                type="text"
                class="edit-input"
              />
              <select 
                v-else-if="isLookupColumn(col.key)"
                v-model="editingData[col.key]"
                class="edit-select"
              >
                <option value="">-- 请选择 --</option>
                <option 
                  v-for="opt in getLookupOptions(col.key)" 
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </option>
              </select>
              <span v-else>{{ formatValue(row[col.key]) }}</span>
            </td>
            <td class="actions">
              <template v-if="editingRow !== idx">
                <button class="icon-btn" @click="startEdit(idx, row)" title="编辑">✏️</button>
                <button class="icon-btn" @click="deleteRow(idx)" title="删除">🗑️</button>
              </template>
              <template v-else>
                <button class="icon-btn" @click="saveEdit" title="保存">💾</button>
                <button class="icon-btn" @click="cancelEdit" title="取消">❌</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add/Edit Form Modal -->
    <div v-if="showAddForm" class="modal-overlay" @click.self="showAddForm = false">
      <div class="modal-content">
        <h3>新增数据</h3>
        <form @submit.prevent="addRow" class="data-form">
          <div v-for="col in inputColumns" :key="col.key" class="form-group">
            <label>{{ col.label }}</label>
            
            <!-- Lookup field → Dropdown -->
            <select 
              v-if="isLookupColumn(col.key)"
              v-model="formData[col.key]"
              :required="col.role === 'dimension'"
            >
              <option value="">-- 请选择 --</option>
              <option 
                v-for="opt in getLookupOptions(col.key)" 
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
            
            <!-- Date field -->
            <DateField
              v-else-if="col.role === 'date'"
              v-model="formData[col.key]"
            />
            
            <!-- Measure field (read-only if calculated) -->
            <input 
              v-else-if="col.role === 'measure'"
              v-model="formData[col.key]"
              type="number"
              step="any"
              :readonly="col.semantic === 'calculated'"
            />
            
            <!-- Text field -->
            <input 
              v-else
              v-model="formData[col.key]"
              type="text"
              :required="col.role === 'dimension'"
            />
          </div>
          
          <div class="form-actions">
            <button type="submit" class="primary-btn">保存</button>
            <button type="button" class="ghost-btn" @click="showAddForm = false">取消</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { authFetch } from './api';
import DateField from './DateField.vue';

const props = defineProps({
  workbookId: String,
  mainSheet: Object,      // { name, label, columns, ... }
  lookupSheets: Array,    // [{ name, data }, ...]
  fieldMappings: Array,   // [{ main_col, lookup_sheet, lookup_key_col, ... }, ...]
  queryResult: Object,    // Data from backend
});

const emit = defineEmits(['refresh']);

const showAddForm = ref(false);
const formData = ref({});
const editingRow = ref(null);
const editingData = ref({});

// Display columns (exclude hidden technical columns)
const displayColumns = computed(() => {
  return props.mainSheet.columns.filter(c => 
    !c.key.startsWith('_') && c.role !== 'id'
  );
});

// Columns for input form
const inputColumns = computed(() => {
  return props.mainSheet.columns.filter(c => 
    !c.key.startsWith('_') && c.role !== 'id' && c.semantic !== 'calculated'
  );
});

// Data to display
const displayData = computed(() => {
  return props.queryResult?.rows || props.queryResult?.data || [];
});

// Check if a column is a lookup column
function isLookupColumn(colKey) {
  return props.fieldMappings.some(m => m.main_col === colKey);
}

// Get lookup options for a column
function getLookupOptions(colKey) {
  const mapping = props.fieldMappings.find(m => m.main_col === colKey);
  if (!mapping) return [];
  
  const lookupSheet = props.lookupSheets.find(s => s.name === mapping.lookup_sheet);
  if (!lookupSheet || !lookupSheet.data) return [];
  
  const keyCol = mapping.lookup_key_col;
  const options = [];
  const seen = new Set();
  
  for (const row of lookupSheet.data) {
    const value = row[keyCol];
    if (value != null && value !== '' && !seen.has(value)) {
      seen.add(value);
      options.push({
        value: String(value),
        label: String(value),
      });
    }
  }
  
  return options;
}

// Format value for display
function formatValue(val) {
  if (val == null || val === '') return '-';
  if (typeof val === 'number') {
    return val.toFixed(2).replace(/\.?0+$/, '');
  }
  return val;
}

// Start editing a row
function startEdit(idx, row) {
  editingRow.value = idx;
  editingData.value = { ...row };
}

// Save edit
async function saveEdit() {
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sheet: props.mainSheet.name,
        data: editingData.value,
      }),
    });
    
    if (res.ok) {
      editingRow.value = null;
      editingData.value = {};
      emit('refresh');
    } else {
      alert('保存失败');
    }
  } catch (err) {
    alert('保存失败: ' + err.message);
  }
}

// Cancel edit
function cancelEdit() {
  editingRow.value = null;
  editingData.value = {};
}

// Delete a row
async function deleteRow(idx) {
  if (!confirm('确定删除这条数据吗？')) return;
  
  // TODO: Need a delete endpoint
  alert('删除功能开发中...');
}

// Add a new row
async function addRow() {
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sheet: props.mainSheet.name,
        data: formData.value,
      }),
    });
    
    if (res.ok) {
      showAddForm.value = false;
      formData.value = {};
      emit('refresh');
    } else {
      alert('保存失败');
    }
  } catch (err) {
    alert('保存失败: ' + err.message);
  }
}

// Watch for sheet changes, reset form
watch(() => props.mainSheet, () => {
  formData.value = {};
  editingRow.value = null;
});
</script>

<style scoped>
.integrated-view {
  padding: 1rem;
}

.view-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.view-header h2 {
  margin: 0;
  font-size: 1.5rem;
}

.badge {
  background: #10b981;
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.875rem;
  font-weight: 500;
}

.info {
  color: #6b7280;
  font-size: 0.875rem;
}

.table-container {
  overflow-x: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th {
  background: #f9fafb;
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #e5e7eb;
  white-space: nowrap;
}

.data-table td {
  padding: 0.75rem;
  border-bottom: 1px solid #f3f4f6;
}

.data-table tbody tr:hover {
  background: #f9fafb;
}

.lookup-indicator {
  font-size: 0.75rem;
  opacity: 0.6;
  margin-left: 0.25rem;
}

.edit-input, .edit-select {
  width: 100%;
  padding: 0.25rem 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 4px;
}

.actions {
  white-space: nowrap;
}

.icon-btn {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem;
  opacity: 0.7;
}

.icon-btn:hover {
  opacity: 1;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin-top: 0;
}

.data-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-group label {
  font-weight: 500;
  font-size: 0.875rem;
}

.form-group input,
.form-group select {
  padding: 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 1rem;
}

.form-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.primary-btn {
  background: var(--primary);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.primary-btn:hover {
  background: #2563eb;
}

.ghost-btn {
  background: transparent;
  border: 1px solid #d1d5db;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
}

.ghost-btn:hover {
  background: #f9fafb;
}
</style>
