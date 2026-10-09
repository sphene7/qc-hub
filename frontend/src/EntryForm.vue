<template>
  <section :class="['entry', layout === 'sidebar' ? 'entry-sidebar' : 'card entry-card']">
    <div v-if="!hideHead" class="entry-head">
      <h2>{{ layout === 'sidebar' ? '新增记录' : '录入新记录' }}</h2>
      <p v-if="layout !== 'sidebar'" class="hint">下拉字段可输入新值；保存后新选项会自动加入下次下拉列表。带 ƒ 的列按公式自动计算。</p>
    </div>

    <form :class="['grid', layout]" @submit.prevent="submit">
      <template v-for="(block, bi) in formBlocks" :key="bi">
        <div v-if="block.type === 'fiveM'" class="field five-m-group">
          <span class="five-m-label">人机料法环 <i class="opt">可多选</i></span>
          <div class="five-m-toggles">
            <button
              v-for="f in block.fields"
              :key="f.key"
              type="button"
              class="five-m-btn"
              :class="{ on: isFiveMActive(f.key) }"
              :title="f.label"
              @click="toggleFiveM(f.key)"
            >{{ fiveMShortLabel(f) }}</button>
          </div>
        </div>
        <label v-else-if="block.type === 'ownerLink'" class="field">
          <span>工段负责人 <i class="opt">选负责人可定位模块</i></span>
          <ComboField
            v-model="ownerPicker"
            :options="ownerPickerOptions"
            placeholder="选择或输入工段负责人"
            @update:model-value="onOwnerPickerChange"
          />
        </label>
        <label v-else-if="block.type === 'categoryLink'" class="field">
          <span>类别 <i class="opt">选类别可定位分类</i></span>
          <ComboField
            v-model="categoryPicker"
            :options="categoryPickerOptions"
            placeholder="选择或输入类别"
            @update:model-value="onCategoryPickerChange"
          />
        </label>
        <label v-else-if="block.type === 'oqcSectionLink'" class="field">
          <span>送检单位 <i class="opt">选系列自动带出，可改</i></span>
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
          />
        </label>
        <label v-else-if="block.type === 'oqcHeadLink'" class="field">
          <span>课室负责人 <i class="opt">随送检单位联动</i></span>
          <ComboField
            v-model="headPicker"
            :options="headPickerOptions"
            placeholder="选择或输入课室负责人"
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
        <label v-else :class="['field', block.field.widget]">
          <span>
            {{ block.field.label }}
            <i v-if="block.field.required">*</i>
          </span>
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
          <template v-else-if="block.field.widget === 'select' && block.field.allow_custom !== false">
            <ComboField
              v-model="form[block.field.key]"
              :options="comboOptions(block.field)"
              :placeholder="modulePlaceholder(block.field)"
              @update:model-value="(v) => onFieldChange(block.field.key, v)"
              @change="(v) => onFieldChange(block.field.key, v)"
            />
          </template>
          <select
            v-else-if="block.field.widget === 'select'"
            v-model="form[block.field.key]"
            @change="preview"
          >
            <option value="">请选择</option>
            <option v-for="o in block.field.options" :key="o" :value="o">{{ o }}</option>
          </select>
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
          <RichTextField
            v-else-if="block.field.widget === 'rich_text'"
            v-model="form[block.field.key]"
            :rows="layout === 'sidebar' ? 2 : 3"
            @change="preview"
          />
          <textarea
            v-else-if="block.field.widget === 'textarea'"
            :rows="layout === 'sidebar' ? 2 : 3"
            v-model="form[block.field.key]"
            @change="preview"
          />
          <input v-else type="text" v-model="form[block.field.key]" @change="preview" />
        </label>
      </template>
    </form>

    <div v-if="computedView.length" :class="['computed', layout]">
      <div class="computed-label">自动计算</div>
      <div class="chips">
        <span v-for="c in computedView" :key="c.key">
          {{ c.label }}
          <strong>{{ display(c.key, previewRow[c.key]) }}</strong>
        </span>
      </div>
    </div>

    <div class="actions">
      <button class="primary" :disabled="saving" @click="submit">{{ saving ? "保存中…" : "保存并入表" }}</button>
      <button type="button" class="ghost" @click="reset">清空</button>
      <span v-if="message" :class="ok ? 'ok' : 'err'">{{ message }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { authFetch } from "./api.js";
import ComboField from "./ComboField.vue";
import DateField from "./DateField.vue";
import MonthField from "./MonthField.vue";
import RichTextField from "./RichTextField.vue";
import { todayDateString } from "./dateField.js";
import {
  formatMonthDisplay,
  fromMonthInputValue,
  isMonthField,
  monthFallbackYear,
  monthInputFromDate,
  todayMonthInputValue,
} from "./monthField.js";
import {
  applyOqcPickersToValues,
  getFormLookups,
  mergeFieldOptions,
  oqcShowFlags,
  onOqcDefectChange,
  onOqcModelChange,
  onOqcSectionChange,
  pickerOptions,
  buildSectionPickerOptions,
  buildConfirmerPickerOptions,
  buildPhenomenonPickerOptions,
  onOqcPhenomenonChange,
} from "./oqcForm.js";

const props = defineProps({
  workbookId: String,
  sheet: Object,
  layout: {
    type: String,
    default: 'grid', // grid | sidebar
  },
  hideHead: {
    type: Boolean,
    default: false,
  },
});
const emit = defineEmits(["saved"]);

const form = reactive({});
const previewRow = ref({});
const saving = ref(false);
const message = ref("");
const ok = ref(true);
const ownerPicker = ref("");
const categoryPicker = ref("");
const sectionPicker = ref("");
const confirmerPicker = ref("");
const headPicker = ref("");
const phenomenonPicker = ref("");
const moduleFilter = ref(null);
const classificationFilter = ref(null);
const localLookups = ref({
  module_owners: {},
  owner_modules: {},
  classification_categories: {},
  category_options: [],
  series_sections: {},
  series_confirmers: {},
  section_heads: {},
  defect_phenomena: {},
});
const lookupsLoading = ref(false);

const fields = computed(() => props.sheet?.form?.fields || []);
const visibleFields = computed(() =>
  fields.value.filter((f) => f.key !== "是否结案" && f.widget !== "toggle" && !isFiveM(f))
);
const computedFields = computed(() => props.sheet?.form?.computed || []);
const hasModuleField = computed(() => fields.value.some((f) => f.key === "模块"));
const hasOwnerComputed = computed(() => computedFields.value.some((c) => c.key === "工段负责人"));
const hasClassificationField = computed(() => fields.value.some((f) => f.key === "分类"));
const hasCategoryComputed = computed(() => computedFields.value.some((c) => c.key === "类别"));
const showOwnerField = computed(() => hasModuleField.value && hasOwnerComputed.value);
const showCategoryField = computed(() => hasClassificationField.value && hasCategoryComputed.value);
const oqcFlags = computed(() => oqcShowFlags(props.sheet));
const showOqcSectionField = computed(() => oqcFlags.value.section);
const showOqcConfirmerField = computed(() => oqcFlags.value.confirmer);
const showOqcHeadField = computed(() => oqcFlags.value.head);
const showOqcPhenomenonField = computed(() => oqcFlags.value.phenomenon);

const computedView = computed(() =>
  computedFields.value.filter((c) => {
    if (c.key === "工段负责人" && showOwnerField.value) return false;
    if (c.key === "类别" && showCategoryField.value) return false;
    if (c.key === "送检单位" && showOqcSectionField.value) return false;
    if (c.key === "确认者" && showOqcConfirmerField.value) return false;
    if (c.key === "课室负责人" && showOqcHeadField.value) return false;
    if (c.key === "现象" && showOqcPhenomenonField.value) return false;
    return c.kind !== "auto_id" || previewRow.value[c.key] != null;
  })
);

const fiveMFields = computed(() =>
  fields.value.filter((f) => f.widget === "toggle" || isFiveM(f))
);

const formLookups = computed(() => props.sheet?.form?.lookups || {});

const activeLookups = computed(() => {
  const fromForm = formLookups.value || {};
  const fromLocal = localLookups.value || {};
  return {
    module_owners: { ...(fromLocal.module_owners || {}), ...(fromForm.module_owners || {}) },
    owner_modules: { ...(fromLocal.owner_modules || {}), ...(fromForm.owner_modules || {}) },
    classification_categories: {
      ...(fromLocal.classification_categories || {}),
      ...(fromForm.classification_categories || {}),
    },
    category_options: [
      ...new Set([
        ...(fromForm.category_options || []),
        ...(fromLocal.category_options || []),
      ]),
    ],
    series_sections: { ...(fromLocal.series_sections || {}), ...(fromForm.series_sections || {}) },
    series_confirmers: { ...(fromLocal.series_confirmers || {}), ...(fromForm.series_confirmers || {}) },
    section_heads: { ...(fromLocal.section_heads || {}), ...(fromForm.section_heads || {}) },
    defect_phenomena: { ...(fromLocal.defect_phenomena || {}), ...(fromForm.defect_phenomena || {}) },
  };
});
const seriesSections = computed(() => activeLookups.value.series_sections || {});
const sectionHeads = computed(() => activeLookups.value.section_heads || {});
const sectionPickerOptions = computed(() =>
  buildSectionPickerOptions(activeLookups.value, sectionPicker.value)
);
const confirmerPickerOptions = computed(() =>
  buildConfirmerPickerOptions(activeLookups.value, confirmerPicker.value),
);
const headPickerOptions = computed(() => {
  const set = new Set(Object.values(sectionHeads.value));
  if (headPicker.value) set.add(String(headPicker.value).trim());
  return [...set].filter(Boolean).sort((a, b) => a.localeCompare(b, "zh-CN"));
});
const phenomenonPickerOptions = computed(() =>
  buildPhenomenonPickerOptions(activeLookups.value, phenomenonPicker.value),
);
const moduleOwners = computed(() => activeLookups.value.module_owners || {});
const ownerModules = computed(() => activeLookups.value.owner_modules || {});
const classificationCategories = computed(() => activeLookups.value.classification_categories || {});
const categoryToClassifications = computed(() => {
  const out = {};
  for (const [cls, cat] of Object.entries(classificationCategories.value)) {
    const key = String(cat || "").trim();
    if (!key) continue;
    if (!out[key]) out[key] = [];
    if (!out[key].includes(cls)) out[key].push(cls);
  }
  for (const list of Object.values(out)) {
    list.sort((a, b) => a.localeCompare(b, "zh-CN"));
  }
  return out;
});
const ownerPickerOptions = computed(() => {
  const owners = new Set(Object.keys(ownerModules.value));
  for (const owner of Object.values(moduleOwners.value)) {
    if (owner) owners.add(String(owner));
  }
  if (ownerPicker.value) owners.add(String(ownerPicker.value).trim());
  return [...owners].filter(Boolean).sort((a, b) => a.localeCompare(b, "zh-CN"));
});
const categoryPickerOptions = computed(() => {
  const cats = new Set(activeLookups.value.category_options || []);
  for (const cat of Object.values(classificationCategories.value)) {
    if (cat) cats.add(String(cat));
  }
  if (categoryPicker.value) cats.add(String(categoryPicker.value).trim());
  return [...cats].filter(Boolean).sort((a, b) => a.localeCompare(b, "zh-CN"));
});

const formBlocks = computed(() => {
  const blocks = [];
  let bucket = [];
  const flush = () => {
    if (bucket.length) {
      blocks.push({ type: "fiveM", fields: [...bucket] });
      bucket = [];
    }
  };
  for (const f of fields.value) {
    if (f.key === "是否结案") continue;
    if (f.widget === "toggle" || isFiveM(f)) {
      bucket.push(f);
    } else {
      flush();
      blocks.push({ type: "field", field: f });
      if (f.key === "模块" && showOwnerField.value) {
        blocks.push({ type: "ownerLink" });
      }
      if (f.key === "分类" && showCategoryField.value) {
        blocks.push({ type: "categoryLink" });
      }
      if (f.key === oqcFlags.value.modelKey && showOqcSectionField.value) {
        blocks.push({ type: "oqcSectionLink" });
        if (showOqcHeadField.value) blocks.push({ type: "oqcHeadLink" });
      }
      if (f.key === oqcFlags.value.modelKey && showOqcConfirmerField.value) {
        blocks.push({ type: "oqcConfirmerLink" });
      }
      if (f.key === "不良代码" && showOqcPhenomenonField.value) {
        blocks.push({ type: "oqcPhenomenonLink" });
      }
    }
  }
  flush();
  return blocks;
});

async function ensureLookups() {
  if (!props.workbookId) return;
  const needInspection = showOwnerField.value || showCategoryField.value;
  const needOqc =
    showOqcSectionField.value ||
    showOqcConfirmerField.value ||
    showOqcHeadField.value ||
    showOqcPhenomenonField.value;
  if (!needInspection && !needOqc) return;
  if (lookupsLoading.value) return;
  lookupsLoading.value = true;
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/code-classifications?code_sheet=代码`);
    const data = await res.json();
    if (res.ok) {
      if (data.layout === "oqc") {
        const lk = data.lookups || data;
        localLookups.value = {
          ...localLookups.value,
          series_sections: lk.series_sections || {},
          series_confirmers: lk.series_confirmers || {},
          section_heads: lk.section_heads || {},
          defect_phenomena: lk.defect_phenomena || {},
        };
      } else {
        const clsMap = { ...(data.classification_categories || {}) };
        for (const item of data.items || []) {
          if (item.classification && item.category) {
            clsMap[item.classification] = item.category;
          }
        }
        localLookups.value = {
          ...localLookups.value,
          module_owners: { ...(localLookups.value.module_owners || {}), ...(data.module_owners || {}) },
          owner_modules: { ...(localLookups.value.owner_modules || {}), ...(data.owner_modules || {}) },
          classification_categories: { ...(localLookups.value.classification_categories || {}), ...clsMap },
          category_options: [
            ...new Set([
              ...(localLookups.value.category_options || []),
              ...(data.category_options || []),
            ]),
          ],
        };
      }
    }
  } catch (err) {
    console.warn("[EntryForm] load code lookups failed", err);
  } finally {
    lookupsLoading.value = false;
  }
}

onMounted(ensureLookups);
watch(
  () => [
    props.workbookId,
    props.sheet?.name,
    showOwnerField.value,
    showCategoryField.value,
    showOqcSectionField.value,
    showOqcConfirmerField.value,
    showOqcHeadField.value,
    showOqcPhenomenonField.value,
  ],
  () => {
    ensureLookups();
  },
);

watch(
  () => props.sheet?.form?.lookups,
  (lk) => {
    if (!lk) return;
    localLookups.value = {
      ...localLookups.value,
      module_owners: { ...(localLookups.value.module_owners || {}), ...(lk.module_owners || {}) },
      owner_modules: { ...(localLookups.value.owner_modules || {}), ...(lk.owner_modules || {}) },
      classification_categories: {
        ...(localLookups.value.classification_categories || {}),
        ...(lk.classification_categories || {}),
      },
      category_options: [
        ...new Set([
          ...(localLookups.value.category_options || []),
          ...(lk.category_options || []),
        ]),
      ],
    };
  },
  { deep: true },
);

defineExpose({ refreshLookups: ensureLookups });

function isFiveM(f) {
  if (f.role === "measure") {
    return /^(人-|机-|料-|法|环境-)/.test(f.key || "");
  }
  return false;
}

function fiveMShortLabel(f) {
  const key = f.key || "";
  if (key.startsWith("人-")) return "人";
  if (key.startsWith("机-")) return "机";
  if (key.startsWith("料-")) return "料";
  if (key.startsWith("法")) return "法";
  if (key.startsWith("环境-")) return "环";
  return (f.label || key).slice(0, 2);
}

function isFiveMActive(key) {
  const v = form[key];
  return v === 1 || v === "1" || v === 1.0;
}

function toggleFiveM(key) {
  form[key] = isFiveMActive(key) ? 0 : 1;
  preview();
}

watch(
  () => props.sheet?.name,
  () => {
    reset();
  },
  { immediate: true }
);

watch(
  () => form["日期"],
  (dateStr) => {
    syncMonthFromDate(dateStr);
  },
);

watch(
  () => props.sheet?.form?.lookups,
  () => {
    ownerPicker.value = "";
    categoryPicker.value = "";
    moduleFilter.value = null;
    classificationFilter.value = null;
  },
);

function comboOptions(field) {
  let opts = [...(field.options || [])];
  if (field.key === "模块") {
    for (const mod of Object.keys(moduleOwners.value)) {
      if (mod && !opts.includes(mod)) opts.push(mod);
    }
    if (moduleFilter.value?.length) {
      opts = opts.filter((o) => moduleFilter.value.includes(o));
    }
  }
  if (field.key === "分类") {
    for (const cls of Object.keys(classificationCategories.value)) {
      if (cls && !opts.includes(cls)) opts.push(cls);
    }
    if (classificationFilter.value?.length) {
      opts = opts.filter((o) => classificationFilter.value.includes(o));
    }
  }
  if (field.key === "机种" || field.key === "系列" || field.key === "不良代码") {
    return mergeFieldOptions(field, activeLookups.value, form[field.key]);
  }
  const cur = form[field.key];
  if (cur && String(cur).trim() && !opts.includes(cur)) {
    opts.unshift(String(cur).trim());
  }
  return opts;
}

function modulePlaceholder(field) {
  if (field.key === "分类" && classificationFilter.value?.length > 1) {
    return "该类别对应多个分类，请选择";
  }
  if (field.key !== "模块") return `选择或输入${field.label}`;
  if (moduleFilter.value?.length > 1) return "该负责人对应多个模块，请选择";
  return "选择或输入模块";
}

function onOwnerPickerChange(owner) {
  const name = String(owner || "").trim();
  if (!name) {
    moduleFilter.value = null;
    return;
  }
  const mods = ownerModules.value[name] || [];
  if (mods.length === 1) {
    form["模块"] = mods[0];
    moduleFilter.value = mods;
    preview();
  } else if (mods.length > 1) {
    moduleFilter.value = mods;
    if (!mods.includes(form["模块"])) {
      form["模块"] = "";
    }
  } else {
    moduleFilter.value = null;
  }
}

function onCategoryPickerChange(category) {
  const cat = String(category || "").trim();
  if (!cat) {
    classificationFilter.value = null;
    return;
  }
  const clss = categoryToClassifications.value[cat] || [];
  if (clss.length === 1) {
    form["分类"] = clss[0];
    classificationFilter.value = clss;
    preview();
  } else if (clss.length > 1) {
    classificationFilter.value = clss;
    if (!clss.includes(form["分类"])) {
      form["分类"] = "";
    }
  } else {
    classificationFilter.value = null;
  }
}

function onSectionPickerChange(section) {
  const pickers = { section: sectionPicker.value, head: headPicker.value };
  onOqcSectionChange(section, activeLookups.value, pickers);
  sectionPicker.value = pickers.section || "";
  headPicker.value = pickers.head || "";
  preview();
}

function monthFieldDef() {
  return fields.value.find((f) => isMonthField(f) || f.key === "月份");
}

function syncMonthFromDate(dateStr) {
  const monthField = monthFieldDef();
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
  if (key === "模块") {
    const owner = moduleOwners.value[String(value || "").trim()];
    if (owner) ownerPicker.value = owner;
    moduleFilter.value = owner ? ownerModules.value[owner] || null : null;
  }
  if (key === "分类") {
    const cat = classificationCategories.value[String(value || "").trim()];
    if (cat) categoryPicker.value = cat;
    classificationFilter.value = cat ? categoryToClassifications.value[cat] || null : null;
  }
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

function payload() {
  const values = {};
  for (const f of fields.value) {
    if (f.key === "是否结案") continue;
    const v = form[f.key];
    if (f.widget === "toggle" || isFiveM(f)) {
      values[f.key] = isFiveMActive(f.key) ? 1 : 0;
      continue;
    }
    if (isMonthField(f)) {
      values[f.key] = v === "" || v === undefined ? null : fromMonthInputValue(v);
      continue;
    }
    values[f.key] = v === "" || v === undefined ? null : v;
  }
  values["是否结案"] = "待选择";
  if (showCategoryField.value && categoryPicker.value) {
    values["类别"] = categoryPicker.value;
  }
  if (showOqcSectionField.value && sectionPicker.value) {
    values["送检单位"] = sectionPicker.value;
  }
  if (showOqcConfirmerField.value && confirmerPicker.value) {
    values["确认者"] = confirmerPicker.value;
  }
  if (showOqcHeadField.value && headPicker.value) {
    values["课室负责人"] = headPicker.value;
  }
  if (showOqcPhenomenonField.value && phenomenonPicker.value) {
    values["现象"] = phenomenonPicker.value;
  }
  return values;
}

async function preview() {
  if (!props.workbookId || !props.sheet) return;
  const body = { sheet: props.sheet.name, values: payload() };
  console.log("[EntryForm] preview-row request", body);
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/preview-row`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    const data = await res.json();
    console.log("[EntryForm] preview-row response", res.status, data);
    if (res.ok) {
      previewRow.value = data.row || {};
      const owner = previewRow.value["工段负责人"];
      if (owner) ownerPicker.value = String(owner);
      const category = previewRow.value["类别"];
      if (category) categoryPicker.value = String(category);
      const section = previewRow.value["送检单位"];
      if (section) sectionPicker.value = String(section);
      const confirmer = previewRow.value["确认者"];
      if (confirmer) confirmerPicker.value = String(confirmer);
      const head = previewRow.value["课室负责人"];
      if (head) headPicker.value = String(head);
      const phen = previewRow.value["现象"];
      if (phen) phenomenonPicker.value = String(phen);
      const codeFromRow = previewRow.value["不良代码"];
      if (codeFromRow) form["不良代码"] = String(codeFromRow);
    }
  } catch (err) {
    console.warn("[EntryForm] preview-row error", err);
  }
}

async function submit() {
  message.value = "";
  for (const f of visibleFields.value) {
    if (f.required && (form[f.key] === undefined || form[f.key] === "" || form[f.key] == null)) {
      ok.value = false;
      message.value = `请填写 ${f.label}`;
      return;
    }
  }
  saving.value = true;
  const body = { sheet: props.sheet.name, values: payload() };
  console.log("[EntryForm] POST /rows request", body);
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/rows`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    const data = await res.json();
    console.log("[EntryForm] POST /rows response", res.status, data);
    if (!res.ok) throw new Error(data.detail || "保存失败");
    ok.value = true;
    message.value = "已写入明细，统计已更新";
    previewRow.value = data.row || {};
    emit("saved", data);
    reset(false);
  } catch (err) {
    ok.value = false;
    message.value = String(err.message || err);
    console.error("[EntryForm] POST /rows failed", err);
  } finally {
    saving.value = false;
  }
}

function reset(clearMsg = true) {
  for (const k of Object.keys(form)) delete form[k];
  for (const f of fields.value) {
    if (f.widget === "date") form[f.key] = todayDateString();
  }
  syncMonthFromDate(form["日期"]);
  for (const f of fields.value) {
    if (isMonthField(f) && (form[f.key] === undefined || form[f.key] === "")) {
      form[f.key] = todayMonthInputValue();
    }
  }
  for (const f of fiveMFields.value) {
    form[f.key] = 0;
  }
  previewRow.value = {};
  ownerPicker.value = "";
  categoryPicker.value = "";
  moduleFilter.value = null;
  classificationFilter.value = null;
  if (clearMsg) message.value = "";
  preview();
}

function display(key, v) {
  if (v == null || v === "") return "—";
  const field = fields.value.find((f) => f.key === key);
  if (isMonthField(field)) return formatMonthDisplay(v, monthFallbackYear(form));
  const col = (props.sheet?.columns || []).find((c) => c.key === key);
  if (col?.type === "percent" && typeof v === "number") {
    const p = Math.abs(v) <= 1 ? v * 100 : v;
    return p.toFixed(1) + "%";
  }
  return String(v);
}
</script>

<style scoped>
.entry-head h2 { margin: 0 0 4px; font-size: 15px; }
.hint { margin: 0 0 12px; color: var(--muted); font-size: 12px; }
.grid {
  display: grid;
  gap: 12px;
}
.grid.grid {
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
}
.grid.sidebar {
  grid-template-columns: 1fr;
}
.field { display: grid; gap: 6px; font-size: 12px; color: var(--muted); }
.field.textarea,
.field.rich_text { grid-column: 1 / -1; }
.field i { color: var(--danger); font-style: normal; }
.field i.opt { color: #94a3b8; font-weight: 400; font-size: 10px; }
.five-m-group { gap: 4px; }
.five-m-label { line-height: 1.2; font-weight: 500; }
.five-m-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.five-m-btn {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
  min-width: 32px;
  line-height: 1.2;
}
.five-m-btn.on {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.five-m-btn:hover:not(.on) {
  border-color: var(--primary);
  color: var(--primary);
}
input, select, textarea {
  border: 1px solid var(--line); border-radius: 8px; padding: 7px 8px; background: #fff; color: var(--ink); width: 100%;
}
.combo { display: grid; gap: 6px; }
.computed { margin-top: 14px; }
.computed-label { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chips span {
  background: var(--bg-accent); border-radius: 999px; padding: 4px 10px; font-size: 12px; color: var(--muted);
}
.chips strong { color: var(--primary); margin-left: 4px; }
.actions { display: flex; gap: 10px; align-items: center; margin-top: 16px; flex-wrap: wrap; }
.primary {
  background: var(--primary); color: #fff; border: 0; border-radius: 8px; padding: 8px 16px; cursor: pointer;
}
.ghost { border: 1px solid var(--line); background: #fff; border-radius: 8px; padding: 8px 12px; cursor: pointer; }
.ok { color: var(--ok); font-size: 13px; }
.err { color: var(--danger); font-size: 13px; }

.entry-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  padding: 8px 10px;
  overflow: hidden;
}
.entry-sidebar .entry-head h2 {
  font-size: 13px;
  font-weight: 650;
  margin: 0 0 4px;
  color: var(--ink);
}
.entry-sidebar .grid.sidebar {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
  gap: 4px;
  align-content: start;
  grid-auto-rows: min-content;
}
.entry-sidebar .field {
  gap: 1px;
  font-size: 11px;
  align-self: start;
  width: 100%;
}
.entry-sidebar .five-m-btn {
  padding: 3px 8px;
  font-size: 11px;
  min-width: 28px;
  height: 24px;
}
.entry-sidebar .five-m-toggles {
  gap: 3px;
}
.entry-sidebar input,
.entry-sidebar select,
.entry-sidebar textarea {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.25;
  height: 26px;
  min-height: 26px;
  box-sizing: border-box;
}
.entry-sidebar textarea {
  height: auto;
  min-height: 44px;
  resize: vertical;
  padding: 4px 6px;
}
.entry-sidebar .combo {
  gap: 3px;
}
.entry-sidebar .custom-input {
  font-size: 11px;
  height: 24px;
  min-height: 24px;
  color: var(--muted);
}
.entry-sidebar .computed {
  margin-top: 4px;
  flex-shrink: 0;
}
.entry-sidebar .computed.sidebar {
  margin-top: 4px;
}
.entry-sidebar .computed-label {
  font-size: 10px;
  margin-bottom: 2px;
  color: #94a3b8;
}
.entry-sidebar .chips {
  gap: 3px;
}
.entry-sidebar .chips span {
  padding: 1px 6px;
  font-size: 10px;
}
.entry-sidebar .actions {
  flex-shrink: 0;
  padding-top: 6px;
  border-top: 1px solid #f3f4f6;
  margin-top: 4px;
  gap: 4px;
}
.entry-sidebar .primary,
.entry-sidebar .ghost {
  padding: 5px 8px;
  font-size: 11px;
  border-radius: 6px;
}
.entry-sidebar .primary {
  flex: 1;
}
.entry-sidebar .ok,
.entry-sidebar .err {
  font-size: 11px;
}
.entry-card {
  /* wrapped by .card in grid layout */
}
</style>
