<template>
  <div v-if="visible" class="modal-backdrop" @mousedown.self="close">
    <div class="dialog modal-panel" role="dialog" aria-modal="true">
      <div class="dialog-head">
        <h3>{{ title }}</h3>
        <button type="button" class="icon-btn" @click="close">✕</button>
      </div>

      <form class="dialog-body" @submit.prevent="save">
        <template v-for="(block, bi) in formBlocks" :key="bi">
          <label v-if="block.type === 'field'" :class="['field', block.field.widget]">
            <span>{{ block.field.label }}<i v-if="block.field.required">*</i></span>
            <DateField
              v-if="block.field.widget === 'date'"
              v-model="form[block.field.key]"
              @update:model-value="onDateFieldChange"
            />
            <MonthField
              v-else-if="isMonthField(block.field)"
              v-model="form[block.field.key]"
              @change="preview"
            />
            <ComboField
              v-else-if="block.field.widget === 'select' && block.field.allow_custom !== false"
              v-model="form[block.field.key]"
              :options="comboOptions(block.field)"
              :placeholder="'选择或输入' + block.field.label"
              @update:model-value="(v) => onFieldChange(block.field.key, v)"
              @change="(v) => onFieldChange(block.field.key, v)"
            />
            <select
              v-else-if="block.field.widget === 'select'"
              v-model="form[block.field.key]"
              @change="preview"
            >
              <option value="">请选择</option>
              <option v-for="o in comboOptions(block.field)" :key="o" :value="o">{{ o }}</option>
            </select>
            <RichTextField
              v-else-if="block.field.widget === 'rich_text'"
              v-model="form[block.field.key]"
              rows="3"
              @change="preview"
            />
            <textarea
              v-else-if="block.field.widget === 'textarea'"
              v-model="form[block.field.key]"
              rows="3"
              @change="preview"
            />
            <input
              v-else-if="block.field.widget === 'number'"
              type="number"
              step="any"
              min="0"
              inputmode="decimal"
              v-model="form[block.field.key]"
              :placeholder="'输入' + block.field.label"
              @change="preview"
            />
            <input v-else type="text" v-model="form[block.field.key]" @change="preview" />
          </label>

          <label v-else-if="block.type === 'oqcSectionLink'" class="field">
            <span>送检单位 <i class="opt">选机种自动带出，可改</i></span>
            <ComboField
              v-model="sectionPicker"
              :options="sectionPickerOptions"
              placeholder="选择或输入送检单位"
              @update:model-value="onSectionPickerChange"
            />
          </label>
          <label v-else-if="block.type === 'oqcConfirmerLink'" class="field">
            <span>确认者 <i class="opt">随机种联动负责人（类别管理第三页）</i></span>
            <ComboField
              v-model="confirmerPicker"
              :options="confirmerPickerOptions"
              placeholder="选择或输入确认者"
              @change="preview"
            />
          </label>
          <label v-else-if="block.type === 'oqcHeadLink'" class="field">
            <span>课室负责人 <i class="opt">随送检单位联动</i></span>
            <ComboField
              v-model="headPicker"
              :options="headPickerOptions"
              placeholder="选择或输入课室负责人"
              @change="preview"
            />
          </label>
          <label v-else-if="block.type === 'oqcPhenomenonLink'" class="field">
            <span>现象 <i class="opt">与不良代码互相联动</i></span>
            <ComboField
              v-model="phenomenonPicker"
              :options="phenomenonPickerOptions"
              placeholder="选择或输入现象"
              @update:model-value="onPhenomenonPickerChange"
              @change="onPhenomenonPickerChange"
            />
          </label>
        </template>

        <div v-if="computedPreview.length" class="computed">
          <div class="computed-label">自动计算（保存后更新）</div>
          <div class="chips">
            <span v-for="c in computedPreview" :key="c.key">
              {{ c.label }} <strong>{{ displayVal(c.key) }}</strong>
            </span>
          </div>
        </div>
      </form>

      <div class="dialog-actions">
        <button type="button" class="primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
        <button type="button" class="ghost" @click="close">取消</button>
        <span v-if="message" :class="ok ? 'ok' : 'err'">{{ message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { authFetch } from "./api.js";
import ComboField from "./ComboField.vue";
import DateField from "./DateField.vue";
import MonthField from "./MonthField.vue";
import RichTextField from "./RichTextField.vue";
import { toDateInputValue } from "./dateField.js";
import {
  formatMonthDisplay,
  fromMonthInputValue,
  isMonthField,
  monthFallbackYear,
  monthInputFromDate,
  toMonthInputValue,
} from "./monthField.js";
import {
  applyOqcPickersToValues,
  buildSectionPickerOptions,
  buildConfirmerPickerOptions,
  buildPhenomenonPickerOptions,
  getFormLookups,
  onOqcPhenomenonChange,
  mergeFieldOptions,
  oqcShowFlags,
  onOqcDefectChange,
  onOqcModelChange,
  onOqcSectionChange,
  pickerOptions,
  syncOqcPickersFromRow,
} from "./oqcForm.js";

const props = defineProps({
  visible: Boolean,
  workbookId: String,
  sheet: Object,
  row: Object,
  rowKey: { type: String, default: "序号" },
  title: { type: String, default: "编辑记录" },
});

const emit = defineEmits(["close", "saved"]);

const form = reactive({});
const saving = ref(false);
const message = ref("");
const ok = ref(true);
const previewRow = ref({});
const sectionPicker = ref("");
const confirmerPicker = ref("");
const headPicker = ref("");
const phenomenonPicker = ref("");
const localLookups = ref({});

const computedKeys = computed(() =>
  new Set((props.sheet?.form?.computed || []).map((c) => c.key))
);

const editableFields = computed(() =>
  (props.sheet?.form?.fields || []).filter(
    (f) => f.key !== "是否结案" && f.widget !== "toggle" && !computedKeys.value.has(f.key)
  )
);

const oqcFlags = computed(() => oqcShowFlags(props.sheet));
const activeLookups = computed(() => getFormLookups(props.sheet, localLookups.value));

const formBlocks = computed(() => {
  const blocks = [];
  for (const f of editableFields.value) {
    blocks.push({ type: "field", field: f });
    if (f.key === oqcFlags.value.modelKey && oqcFlags.value.section) {
      blocks.push({ type: "oqcSectionLink" });
      if (oqcFlags.value.head) blocks.push({ type: "oqcHeadLink" });
    }
    if (f.key === oqcFlags.value.modelKey && oqcFlags.value.confirmer) {
      blocks.push({ type: "oqcConfirmerLink" });
    }
    if (f.key === "不良代码" && oqcFlags.value.phenomenon) {
      blocks.push({ type: "oqcPhenomenonLink" });
    }
  }
  return blocks;
});

const computedPreview = computed(() =>
  (props.sheet?.form?.computed || []).filter((c) => {
    if (c.key === "送检单位" && oqcFlags.value.section) return false;
    if (c.key === "确认者" && oqcFlags.value.confirmer) return false;
    if (c.key === "课室负责人" && oqcFlags.value.head) return false;
    if (c.key === "现象" && oqcFlags.value.phenomenon) return false;
    return c.kind !== "auto_id";
  })
);

const sectionPickerOptions = computed(() =>
  buildSectionPickerOptions(activeLookups.value, sectionPicker.value)
);
const confirmerPickerOptions = computed(() =>
  buildConfirmerPickerOptions(activeLookups.value, confirmerPicker.value),
);
const headPickerOptions = computed(() =>
  pickerOptions(activeLookups.value.section_heads, headPicker.value)
);
const phenomenonPickerOptions = computed(() =>
  buildPhenomenonPickerOptions(activeLookups.value, phenomenonPicker.value),
);

async function ensureLookups() {
  if (!props.workbookId || !oqcFlags.value.modelKey) return;
  if (Object.keys(activeLookups.value.series_sections || {}).length) return;
  try {
    const res = await authFetch(
      `/api/workbooks/${props.workbookId}/code-classifications?code_sheet=代码`
    );
    const data = await res.json();
    if (res.ok && data.layout === "oqc") {
      const lk = data.lookups || data;
      localLookups.value = {
        series_sections: lk.series_sections || {},
        series_confirmers: lk.series_confirmers || {},
        section_heads: lk.section_heads || {},
        defect_phenomena: lk.defect_phenomena || {},
      };
    }
  } catch (err) {
    console.warn("[EditRowDialog] load OQC lookups failed", err);
  }
}

onMounted(ensureLookups);

watch(
  () => [props.visible, props.row, props.sheet?.name],
  () => {
    if (!props.visible || !props.row) return;
    message.value = "";
    ensureLookups();
    for (const k of Object.keys(form)) delete form[k];
    for (const f of editableFields.value) {
      const v = props.row[f.key];
      if (f.widget === "date") {
        form[f.key] = toDateInputValue(v);
      } else if (isMonthField(f)) {
        form[f.key] = toMonthInputValue(v, monthFallbackYear(props.row));
      } else {
        form[f.key] = v == null ? "" : String(v);
      }
    }
    const pickers = { section: "", confirmer: "", head: "", phenomenon: "", defectCode: "" };
    syncOqcPickersFromRow(props.row, pickers, activeLookups.value);
    sectionPicker.value = pickers.section || "";
    confirmerPicker.value = pickers.confirmer || "";
    headPicker.value = pickers.head || "";
    phenomenonPicker.value = pickers.phenomenon || "";
    if (pickers.defectCode) form["不良代码"] = pickers.defectCode;
    previewRow.value = { ...props.row };
    syncMonthFromDate(form["日期"]);
    preview();
  },
  { immediate: true }
);

watch(
  () => form["日期"],
  (dateStr) => {
    syncMonthFromDate(dateStr);
  },
);

function comboOptions(field) {
  if (field.key === "机种" || field.key === "系列" || field.key === "不良代码") {
    return mergeFieldOptions(field, activeLookups.value, form[field.key]);
  }
  let opts = [...(field.options || [])];
  const cur = form[field.key];
  if (cur && String(cur).trim() && !opts.includes(String(cur).trim())) {
    opts.unshift(String(cur).trim());
  }
  return opts;
}

function onSectionPickerChange(section) {
  const pickers = { section: sectionPicker.value, head: headPicker.value };
  onOqcSectionChange(section, activeLookups.value, pickers);
  sectionPicker.value = pickers.section || "";
  headPicker.value = pickers.head || "";
  preview();
}

function syncMonthFromDate(dateStr) {
  const monthField = editableFields.value.find((f) => isMonthField(f) || f.key === "月份");
  if (!monthField) return;
  const next = monthInputFromDate(dateStr);
  if (next) form[monthField.key] = next;
}

function onDateFieldChange(dateStr) {
  syncMonthFromDate(dateStr);
  preview();
}

function onFieldChange(key, value) {
  form[key] = value;
  if (key === "日期") syncMonthFromDate(value);
  if (key === "系列" || key === "机种") {
    const pickers = {
      section: sectionPicker.value,
      confirmer: confirmerPicker.value,
      head: headPicker.value,
    };
    onOqcModelChange(value, activeLookups.value, pickers);
    sectionPicker.value = pickers.section || "";
    confirmerPicker.value = pickers.confirmer || "";
    headPicker.value = pickers.head || "";
  }
  if (key === "不良代码") {
    const pickers = { phenomenon: phenomenonPicker.value };
    onOqcDefectChange(value, activeLookups.value, pickers);
    phenomenonPicker.value = pickers.phenomenon || "";
  }
  preview();
}

function onPhenomenonPickerChange(value) {
  phenomenonPicker.value = value == null ? "" : String(value);
  const pickers = { defectCode: "" };
  const code = onOqcPhenomenonChange(phenomenonPicker.value, activeLookups.value, pickers);
  if (code) form["不良代码"] = code;
  preview();
}

function displayVal(key) {
  const v = previewRow.value[key];
  if (v == null || v === "") return "—";
  const field = editableFields.value.find((f) => f.key === key);
  if (field?.widget === "date") return toDateInputValue(v) || "—";
  if (isMonthField(field)) return formatMonthDisplay(v, monthFallbackYear(previewRow.value));
  return String(v);
}

function payload() {
  const values = {};
  for (const f of editableFields.value) {
    const v = form[f.key];
    if (isMonthField(f)) {
      values[f.key] = v === "" || v === undefined ? null : fromMonthInputValue(v);
      continue;
    }
    values[f.key] = v === "" || v === undefined ? null : v;
  }
  applyOqcPickersToValues(values, oqcFlags.value, {
    section: sectionPicker.value,
    confirmer: confirmerPicker.value,
    head: headPicker.value,
    phenomenon: phenomenonPicker.value,
  });
  return values;
}

async function preview() {
  if (!props.workbookId || !props.sheet || !props.visible) return;
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/preview-row`, {
      method: "POST",
      body: JSON.stringify({ sheet: props.sheet.name, values: payload() }),
    });
    const data = await res.json();
    if (res.ok) {
      previewRow.value = { ...(props.row || {}), ...(data.row || {}) };
    }
  } catch (err) {
    console.warn("[EditRowDialog] preview failed", err);
  }
}

async function save() {
  message.value = "";
  for (const f of editableFields.value) {
    if (f.required && (form[f.key] === undefined || form[f.key] === "" || form[f.key] == null)) {
      ok.value = false;
      message.value = `请填写 ${f.label}`;
      return;
    }
  }
  const rowId = props.row?.[props.rowKey];
  if (rowId == null) {
    ok.value = false;
    message.value = "无法识别行标识";
    return;
  }
  saving.value = true;
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
      method: "PUT",
      body: JSON.stringify({
        sheet: props.sheet?.name,
        row_key: props.rowKey,
        row_id: rowId,
        values: payload(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    ok.value = true;
    message.value = "已保存";
    emit("saved", data);
    close();
  } catch (err) {
    ok.value = false;
    message.value = String(err.message || err);
  } finally {
    saving.value = false;
  }
}

function close() {
  emit("close");
}
</script>

<style scoped>
.dialog {
  width: min(720px, 96vw);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}
.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.dialog-head h3 { margin: 0; font-size: 15px; }
.icon-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  color: var(--muted);
}
.dialog-body {
  padding: 14px 16px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.field { display: grid; gap: 6px; font-size: 12px; color: var(--muted); }
.field.textarea,
.field.rich_text { grid-column: 1 / -1; }
.field i { color: var(--danger); font-style: normal; }
.field .opt { color: var(--muted); font-style: normal; font-weight: normal; }
input, select, textarea {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 7px 8px;
  background: #fff;
  color: var(--ink);
  width: 100%;
}
.computed { grid-column: 1 / -1; margin-top: 4px; }
.computed-label { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chips span {
  background: var(--bg-accent);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--muted);
}
.chips strong { color: var(--primary); margin-left: 4px; }
.dialog-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
}
.primary {
  background: var(--primary);
  color: #fff;
  border: 0;
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
}
.ghost {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}
.ok { color: var(--ok); font-size: 13px; }
.err { color: var(--danger); font-size: 13px; }
</style>
