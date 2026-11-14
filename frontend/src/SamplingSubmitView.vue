<template>
  <div class="smp-page">
    <div class="smp-toolbar card">
      <button v-if="canSubmit" type="button" class="smp-btn smp-btn-primary" @click="openNew">
        + 新增送检
      </button>
      <div class="smp-stats">
        <span class="smp-stat">今日我登记 <strong>{{ todayMine }}</strong> 条</span>
        <span class="smp-stat">待抽检 <strong>{{ pending }}</strong> 张</span>
        <span class="smp-stat">本月 <strong>{{ monthCount }}</strong> 张</span>
        <span v-if="dept" class="smp-stat">课室 <strong>{{ dept }}</strong></span>
      </div>
      <span class="smp-spacer"></span>
      <button
        type="button"
        class="smp-btn smp-btn-ghost"
        :disabled="loading || exporting || !filtered.length"
        title="按当前筛选条件导出（含日期）"
        @click="exportFiltered"
      >
        {{ exporting ? '导出中…' : '导出当前筛选' }}
      </button>
      <button type="button" class="smp-btn smp-btn-ghost" :disabled="loading" @click="load">刷新</button>
    </div>

    <div v-if="notice" class="smp-notice">{{ notice }}</div>
    <div v-if="error" class="smp-error">{{ error }}</div>

    <div class="smp-filters card">
      <div class="smp-search"><input v-model="filters.partNo" placeholder="部番" /></div>
      <div class="smp-search"><input v-model="filters.model" placeholder="机种" /></div>
      <div class="smp-search">
        <ComboField v-model="filters.dept" :options="options.送检单位 || []" placeholder="送检单位" />
      </div>
      <div class="smp-seg">
        <button
          v-for="opt in statusOptions"
          :key="opt.key"
          type="button"
          :class="{ active: status === opt.key }"
          @click="status = opt.key"
        >
          {{ opt.label }}
        </button>
      </div>
      <div class="smp-seg">
        <button
          v-for="opt in presetOptions"
          :key="opt.key"
          type="button"
          :class="{ active: preset === opt.key }"
          @click="applyPreset(opt.key)"
        >
          {{ opt.label }}
        </button>
      </div>
      <label class="smp-daterange">
        送检日期
        <input v-model="filters.from" type="date" @change="preset = ''" />
        ~
        <input v-model="filters.to" type="date" @change="preset = ''" />
      </label>
      <label class="smp-check">
        <input v-model="filters.mine" type="checkbox" />
        只看我的
      </label>
      <button type="button" class="smp-reset" @click="resetFilters">清空</button>
      <span class="smp-count">共 {{ filtered.length }} 条</span>
    </div>

    <div class="card smp-table-card">
      <div class="smp-table-wrap">
        <table class="smp-table">
          <thead>
            <tr>
              <th class="ops">操作</th>
              <th>送检单号</th>
              <th>送检日期</th>
              <th>部番</th>
              <th>送检类型</th>
              <th>机种</th>
              <th>事业部</th>
              <th>送检单位</th>
              <th class="num">送检数量</th>
              <th class="num">检验数量</th>
              <th class="num">同批次数</th>
              <th class="num">抽检人数</th>
              <th class="num">异常</th>
              <th>状态</th>
              <th>送检员</th>
              <th>完成日期</th>
              <th>登记人</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="17"><div class="smp-empty">加载中…</div></td></tr>
            <tr v-else-if="!filtered.length">
              <td colspan="17">
                <div class="smp-empty">
                  <span class="smp-empty-icon">📋</span>
                  没有符合条件的送检单
                </div>
              </td>
            </tr>
            <template v-else>
              <tr v-for="e in filtered" :key="e.送检单号" class="clickable" @click="openEdit(e)">
                <td class="ops" @click.stop>
                  <button
                    v-if="canInspect"
                    type="button"
                    class="quick-btn"
                    title="跳到抽检登记并选中这张送检单"
                    @click="quickInspect(e)"
                  >
                    抽检登记
                  </button>
                  <button v-if="canSubmit" type="button" class="smp-link" @click="openEdit(e)">编辑</button>
                  <button v-if="canDelete" type="button" class="smp-link danger" @click="remove(e)">
                    删除
                  </button>
                </td>
                <td class="mono">{{ e.送检单号 }}</td>
                <td>{{ e.送检日期 || e.日期 }}</td>
                <td class="mono">{{ e.部番 || e.机种 || "-" }}</td>
                <td>{{ e.送检类型 || "-" }}</td>
                <td>{{ e.机种 || "-" }}</td>
                <td><span v-if="e.事业部" class="bu-tag">{{ e.事业部 }}</span><span v-else>-</span></td>
                <td>{{ e.送检单位 || "-" }}</td>
                <td class="num">{{ e.送检数量 ?? "-" }}</td>
                <td class="num">{{ e.检验数量 ?? "-" }}</td>
                <td class="num">{{ e.同批送检次数 ?? "-" }}</td>
                <td class="num">{{ (e.抽检 || []).length }}</td>
                <td class="num">{{ defectCount(e) || "-" }}</td>
                <td>
                  <span class="smp-badge" :class="statusOf(e).cls">{{ statusOf(e).label }}</span>
                </td>
                <td>{{ e.送检员 || "-" }}</td>
                <td>{{ e.完成日期 || "-" }}</td>
                <td>{{ e.登记人 || "-" }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="modal.open" class="smp-overlay">
      <div class="smp-modal">
        <div class="smp-modal-head">
          <h3>{{ modal.id ? `编辑 ${modal.id}` : "新增送检单" }}</h3>
          <button type="button" class="smp-modal-close" @click="closeModal">✕</button>
        </div>
        <div class="smp-modal-body">
          <div class="smp-section">
            <p class="smp-section-title">送检信息</p>
            <div class="smp-grid">
              <label class="smp-field">
                <span>送检日期</span>
                <input v-model="form.日期" type="datetime-local" />
              </label>
              <label class="smp-field">
                <span>送检类型</span>
                <ComboField v-model="form.送检类型" :options="options.送检类型 || []" placeholder="选择或输入" />
              </label>
              <label class="smp-field">
                <span>部番<span class="smp-required">*</span></span>
                <ComboField
                  v-model="form.部番"
                  :options="options.部番 || []"
                  placeholder="如 T5724-A1"
                  @change="onPartNoChange"
                  @update:model-value="onPartNoChange"
                />
              </label>
              <label class="smp-field">
                <span>机种（部番 - 前）</span>
                <input :value="form.机种" readonly class="readonly" />
              </label>
              <label class="smp-field">
                <span>事业部</span>
                <ComboField v-model="form.事业部" :options="options.事业部 || []" placeholder="按部番自动匹配" />
              </label>
              <label class="smp-field">
                <span>送检单位</span>
                <input v-if="dept" v-model="form.送检单位" readonly class="locked" />
                <ComboField
                  v-else
                  v-model="form.送检单位"
                  :options="options.送检单位 || []"
                  placeholder="选择或输入送检单位"
                />
              </label>
              <label class="smp-field">
                <span>送检数量<span class="smp-required">*</span></span>
                <input v-model="form.送检数量" type="number" min="0" step="any" />
              </label>
              <label class="smp-field">
                <span>同批送检次数</span>
                <input
                  :value="form.同批送检次数"
                  type="number"
                  min="1"
                  readonly
                  class="readonly"
                  title="同一天、同部番自动递增：1、2、3…"
                />
              </label>
              <label class="smp-field">
                <span>是否紧急出货</span>
                <select v-model="form.是否紧急出货">
                  <option value="">-</option>
                  <option value="是">是</option>
                  <option value="否">否</option>
                </select>
              </label>
              <label class="smp-field">
                <span>确认者</span>
                <ComboField
                  v-model="form.确认者"
                  :options="options.确认者 || []"
                  placeholder="选择或输入确认者"
                />
              </label>
              <label class="smp-field">
                <span>课室负责人</span>
                <ComboField
                  v-model="form.课室负责人"
                  :options="options.课室负责人 || []"
                  placeholder="选择或输入课室负责人"
                />
              </label>
              <label class="smp-field">
                <span>送检员</span>
                <ComboField
                  v-model="form.送检员"
                  :options="options.送检员 || []"
                  placeholder="选择或输入送检员"
                />
              </label>
              <label class="smp-field full">
                <span>层别备注</span>
                <input v-model="form.层别备注" />
              </label>
            </div>
          </div>
          <div v-if="modal.error" class="smp-modal-error">{{ modal.error }}</div>
        </div>
        <div class="smp-modal-foot">
          <button type="button" class="smp-btn smp-btn-ghost" @click="closeModal">取消</button>
          <button type="button" class="smp-btn smp-btn-primary" :disabled="saving" @click="save">
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { authFetch } from "./api.js";
import ComboField from "./ComboField.vue";
import {
  createSubmission,
  defectCount,
  deleteSubmission,
  downloadCsv,
  inRange,
  loadSampling,
  matchKeyword,
  meName,
  splitDateTime,
  submissionStatus,
  todayStr,
  updateSubmission,
} from "./samplingApi.js";

const DEPT_CACHE_KEY = "qc-hub:last-submit-dept";

const props = defineProps({
  workbookId: String,
  canCreate: { type: Boolean, default: false },
  canUpdate: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
  canInspect: { type: Boolean, default: false },
  canSubmit: { type: Boolean, default: false },
  dept: { type: String, default: "" },
});

const router = useRouter();
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const entries = ref([]);
const options = ref({});
const filters = ref({ partNo: "", model: "", dept: "", from: "", to: "", mine: false });
const status = ref("all");
const preset = ref("");
const modal = ref({ open: false, id: "", error: "", version: null });
const form = ref(blankForm());

const statusOptions = [
  { key: "all", label: "全部" },
  { key: "todo", label: "待抽检" },
  { key: "ng", label: "有异常" },
  { key: "ok", label: "正常" },
];
const presetOptions = [
  { key: "", label: "不限日期" },
  { key: "yesterday", label: "昨天" },
  { key: "today", label: "今天" },
  { key: "7d", label: "近7天" },
  { key: "month", label: "本月" },
];
const exporting = ref(false);

const statusOf = submissionStatus;
const lookups = computed(() => options.value.lookups || {});

function isoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function applyPreset(key) {
  preset.value = key;
  const now = new Date();
  if (key === "yesterday") {
    const y = new Date(now);
    y.setDate(y.getDate() - 1);
    const day = isoDate(y);
    filters.value.from = day;
    filters.value.to = day;
  } else if (key === "today") {
    filters.value.from = isoDate(now);
    filters.value.to = isoDate(now);
  } else if (key === "7d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 6);
    filters.value.from = isoDate(start);
    filters.value.to = isoDate(now);
  } else if (key === "month") {
    filters.value.from = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
    filters.value.to = isoDate(now);
  } else {
    filters.value.from = "";
    filters.value.to = "";
  }
}

function exportFiltered() {
  const rows = filtered.value;
  if (!rows.length) {
    alert("当前筛选没有可导出的送检记录");
    return;
  }
  if (!filters.value.from && !filters.value.to) {
    const ok = confirm(`未选日期，将导出当前筛选的全部 ${rows.length} 条，是否继续？\n（导昨天：先点「昨天」再导出）`);
    if (!ok) return;
  }
  exporting.value = true;
  try {
    const headers = [
      "送检单号", "送检日期", "送检时间", "送检类型", "部番", "机种", "事业部", "送检单位",
      "送检数量", "检验数量", "同批送检次数", "是否紧急出货", "确认者", "课室负责人", "送检员",
      "层别备注", "抽检人数", "异常", "状态", "完成日期", "完成时间", "登记人",
    ];
    const data = rows.map((e) => {
      const submit = splitDateTime(e.送检日期 || e.日期);
      const done = splitDateTime(e.完成日期);
      return [
        e.送检单号,
        submit.date,
        submit.time,
        e.送检类型,
        e.部番,
        e.机种,
        e.事业部,
        e.送检单位,
        e.送检数量,
        e.检验数量 ?? "",
        e.同批送检次数,
        e.是否紧急出货,
        e.确认者,
        e.课室负责人,
        e.送检员,
        e.层别备注,
        (e.抽检 || []).length,
        defectCount(e),
        statusOf(e)?.label || statusOf(e),
        done.date,
        done.time,
        e.登记人,
      ];
    });
    const from = filters.value.from || "all";
    const to = filters.value.to || from;
    downloadCsv(`送检记录_${from}_${to}.csv`, headers, data);
  } finally {
    exporting.value = false;
  }
}

const filtered = computed(() =>
  entries.value.filter((e) => {
    if (!inRange(e.日期, filters.value.from, filters.value.to)) return false;
    if (filters.value.mine && (e.登记人 || "") !== meName()) return false;
    const inspected = (e.抽检 || []).length > 0;
    const bad = defectCount(e) > 0;
    if (status.value === "todo" && inspected) return false;
    if (status.value === "ng" && !bad) return false;
    if (status.value === "ok" && (!inspected || bad)) return false;
    return (
      matchKeyword(filters.value.partNo, e.部番) &&
      matchKeyword(filters.value.model, e.机种) &&
      matchKeyword(filters.value.dept, e.送检单位)
    );
  }),
);
const todayMine = computed(() => {
  const today = todayStr();
  return entries.value.filter((e) => String(e.日期 || "").slice(0, 10) === today && (e.登记人 || "") === meName()).length;
});
const pending = computed(() => entries.value.filter((e) => !(e.抽检 || []).length).length);
const monthCount = computed(() => {
  const month = todayStr().slice(0, 7);
  return entries.value.filter((e) => String(e.日期 || "").slice(0, 7) === month).length;
});

function nowLocalStr() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function lastDept() {
  if (props.dept) return props.dept;
  try {
    return localStorage.getItem(DEPT_CACHE_KEY) || "";
  } catch {
    return "";
  }
}

function rememberDept(value) {
  if (props.dept) return;
  const v = String(value || "").trim();
  if (!v) return;
  try {
    localStorage.setItem(DEPT_CACHE_KEY, v);
  } catch {
    /* ignore */
  }
}

function blankForm() {
  return {
    日期: nowLocalStr(),
    送检类型: "",
    部番: "",
    机种: "",
    事业部: "",
    送检单位: lastDept(),
    送检数量: "",
    同批送检次数: "",
    是否紧急出货: "",
    层别备注: "",
    确认者: "",
    课室负责人: "",
    送检员: "",
  };
}

/** 同一天、同部番：已有最大同批次数 + 1 */
function computeBatchSeq(dayValue, partNo, excludeCode = "") {
  const day = String(dayValue || "").slice(0, 10);
  const part = String(partNo || "").trim();
  if (!day || !part) return "";
  let maxSeq = 0;
  for (const e of entries.value) {
    if (excludeCode && e.送检单号 === excludeCode) continue;
    if (String(e.日期 || e.送检日期 || "").slice(0, 10) !== day) continue;
    if (String(e.部番 || "").trim() !== part) continue;
    const n = Number(e.同批送检次数);
    if (Number.isFinite(n) && n > maxSeq) maxSeq = n;
  }
  return maxSeq + 1;
}

function refreshBatchSeq() {
  if (!modal.value.open) return;
  // 编辑且未改日期/部番时保留原值；新增或日期/部番变化时重算
  form.value.同批送检次数 = computeBatchSeq(
    form.value.日期,
    form.value.部番,
    modal.value.id || "",
  );
}

function applyLookupsFromModel() {
  const model = String(form.value.机种 || "").trim();
  const part = String(form.value.部番 || "").trim();
  const lu = lookups.value;
  const sectionMap = lu.series_sections || {};
  const confirmerMap = lu.series_confirmers || {};
  const headMap = lu.section_heads || {};

  const section =
    sectionMap[part] ||
    sectionMap[model] ||
    Object.entries(sectionMap).find(([k]) => part.startsWith(k) || model.startsWith(k))?.[1] ||
    "";
  if (section && !props.dept) {
    form.value.送检单位 = section;
  }

  const confirmer =
    confirmerMap[part] ||
    confirmerMap[model] ||
    Object.entries(confirmerMap).find(([k]) => part.startsWith(k) || model.startsWith(k))?.[1] ||
    "";
  if (confirmer) form.value.确认者 = confirmer;

  const unit = String(form.value.送检单位 || "").trim();
  if (unit && headMap[unit]) form.value.课室负责人 = headMap[unit];
}

async function onPartNoChange() {
  const part = String(form.value.部番 || "").trim();
  form.value.机种 = part.split("-")[0];
  applyLookupsFromModel();
  refreshBatchSeq();
  if (!part || !props.workbookId) return;
  try {
    const res = await authFetch(
      `/api/workbooks/${props.workbookId}/sampling/business-unit?model=${encodeURIComponent(part)}`,
    );
    const data = await res.json();
    if (res.ok && data.business_unit) form.value.事业部 = data.business_unit;
  } catch {
    /* 匹配失败不阻塞填写 */
  }
}

watch(
  () => form.value.送检单位,
  (unit) => {
    const headMap = lookups.value.section_heads || {};
    const key = String(unit || "").trim();
    if (key && headMap[key]) form.value.课室负责人 = headMap[key];
  },
);

watch(
  () => form.value.日期,
  () => {
    if (modal.value.open) refreshBatchSeq();
  },
);

function flash(message) {
  notice.value = message;
  setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 4000);
}

async function load(silent = false) {
  if (!props.workbookId) return;
  if (!silent) loading.value = true;
  error.value = "";
  try {
    const data = await loadSampling(props.workbookId);
    entries.value = data.entries || [];
    options.value = data.options || {};
  } catch (err) {
    error.value = err.message;
  } finally {
    if (!silent) loading.value = false;
  }
}

function openNew() {
  form.value = blankForm();
  if (props.dept) form.value.送检单位 = props.dept;
  modal.value = { open: true, id: "", error: "", version: null };
  refreshBatchSeq();
}

function openEdit(entry) {
  if (!props.canSubmit) return;
  const next = blankForm();
  for (const key of Object.keys(next)) {
    if (entry[key] !== undefined && entry[key] !== null) next[key] = entry[key];
  }
  if (entry.送检日期 && !next.日期) next.日期 = entry.送检日期;
  if (typeof next.日期 === "string" && next.日期.includes(" ")) {
    next.日期 = next.日期.replace(" ", "T");
  }
  form.value = next;
  modal.value = { open: true, id: entry.送检单号, error: "", version: entry.版本 ?? null };
}

function closeModal() {
  modal.value = { open: false, id: "", error: "", version: null };
}

function resetFilters() {
  filters.value = { partNo: "", model: "", dept: "", from: "", to: "", mine: false };
  status.value = "all";
  preset.value = "";
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    const payload = { ...form.value };
    if (modal.value.id && modal.value.version != null) {
      payload.expected_version = modal.value.version;
    }
    const data = modal.value.id
      ? await updateSubmission(props.workbookId, modal.value.id, payload)
      : await createSubmission(props.workbookId, payload);
    await load(true);
    rememberDept(form.value.送检单位);
    flash(`已保存 ${data.submission?.送检单号 || ""}`);
    closeModal();
  } catch (err) {
    modal.value.error = err.message;
    if (String(err.message).includes("刷新")) await load();
  } finally {
    saving.value = false;
  }
}

async function remove(entry) {
  if (!confirm(`确定删除 ${entry.送检单号}？其抽检与异常记录会一并删除。`)) return;
  try {
    await deleteSubmission(props.workbookId, entry.送检单号);
    await load(true);
    flash(`已删除 ${entry.送检单号}`);
  } catch (err) {
    error.value = err.message;
  }
}

function quickInspect(entry) {
  router.push({
    name: "project-view",
    params: { wid: props.workbookId, tab: "inspect" },
    query: { sid: entry.送检单号 },
  });
}

function onKeydown(ev) {
  if (ev.key === "Escape" && modal.value.open) closeModal();
}

onMounted(() => {
  load();
  window.addEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>
