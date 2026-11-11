<template>
  <div class="smp-page">
    <div class="smp-toolbar card">
      <div class="smp-stats">
        <span class="smp-stat warn">未处理 <strong>{{ openCount }}</strong> 条</span>
        <span class="smp-stat">处理中 <strong>{{ doingCount }}</strong> 条</span>
        <span class="smp-stat">已结案 <strong>{{ closedCount }}</strong> 条</span>
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
      <div class="smp-search">
        <input v-model="filters.keyword" placeholder="搜索 单号 / 机种 / 检验员 / OA单号 / 责任单位" />
      </div>
      <div class="smp-seg">
        <button
          v-for="opt in statusOptions"
          :key="opt.key"
          type="button"
          :class="{ active: statusFilter === opt.key }"
          @click="statusFilter = opt.key"
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
        日期
        <input v-model="filters.from" type="date" @change="preset = ''" />
        ~
        <input v-model="filters.to" type="date" @change="preset = ''" />
      </label>
      <label class="smp-check">
        <input v-model="filters.ngOnly" type="checkbox" />
        只看 NG
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
              <th>抽检单号</th>
              <th>日期</th>
              <th>部番</th>
              <th>机种</th>
              <th>事业部</th>
              <th>检验员</th>
              <th>判定</th>
              <th class="num">不良数量</th>
              <th>OA单号</th>
              <th>责任单位</th>
              <th>结案日期</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="13"><div class="smp-empty">加载中…</div></td></tr>
            <tr v-else-if="!filtered.length">
              <td colspan="13">
                <div class="smp-empty">
                  <span class="smp-empty-icon">✅</span>
                  没有符合条件的记录
                </div>
              </td>
            </tr>
            <template v-else>
              <tr v-for="c in filtered" :key="c.抽检单号" class="clickable" @click="openEdit(c)">
                <td class="ops" @click.stop>
                  <button v-if="canHandle" type="button" class="smp-link" @click="openEdit(c)">
                    {{ c.异常处理 ? "修改" : "处理" }}
                  </button>
                  <button
                    v-if="c.异常处理 && canDelete"
                    type="button"
                    class="smp-link danger"
                    @click="clear(c)"
                  >
                    清除
                  </button>
                </td>
                <td class="mono">{{ c.抽检单号 }}</td>
                <td>{{ c.日期 }}</td>
                <td class="mono">{{ c.部番 || c.机种 || "-" }}</td>
                <td>{{ c.机种 || "-" }}</td>
                <td>{{ c.事业部 || "-" }}</td>
                <td>{{ c.检验员 }}</td>
                <td>
                  <span class="smp-badge" :class="isNg(c.判定) ? 'smp-badge-bad' : 'smp-badge-ok'">
                    {{ c.判定 || "-" }}
                  </span>
                </td>
                <td class="num">{{ c.不良数量 ?? "-" }}</td>
                <td>{{ c.异常处理?.OA单号 || "-" }}</td>
                <td>{{ c.异常处理?.责任单位 || "-" }}</td>
                <td>{{ c.异常处理?.结案日期 || "-" }}</td>
                <td>
                  <span class="smp-badge" :class="statusOf(c).cls">{{ statusOf(c).label }}</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="modal.open" class="smp-overlay">
      <div class="smp-modal">
        <div class="smp-modal-head">
          <h3>异常处理 · {{ modal.id }}</h3>
          <button type="button" class="smp-modal-close" @click="closeModal">✕</button>
        </div>
        <div class="smp-modal-body">
          <div class="smp-fixed-info">
            {{ form.sid }} · {{ form.machine }} · 检验员 {{ form.inspector }} · 判定 {{ form.judge }} ·
            不良 {{ form.qty || "-" }}
          </div>

          <div class="smp-section">
            <p class="smp-section-title">问题描述（来自抽检不良）</p>
            <div v-if="form.defects.length" class="defect-list">
              <div v-for="(d, i) in form.defects" :key="i" class="defect-item">
                <span class="idx">{{ i + 1 }}</span>
                <span class="attr">{{ d.不良属性 || '-' }}</span>
                <span>{{ d.现象 || '-' }}</span>
                <span>{{ d.不良位置 || '-' }}</span>
                <span class="qty">×{{ d.数量 ?? '-' }}</span>
              </div>
            </div>
            <p v-else class="smp-hint">这次抽检没有不良记录</p>
            <div class="smp-chips" style="margin-top: 10px">
              <span>判定<strong :class="isNg(form.judge) ? 'bad' : 'ok'">{{ form.judge || '-' }}</strong></span>
              <span>不良数量<strong>{{ form.qty || 0 }}</strong></span>
            </div>
          </div>

          <div class="smp-section">
            <p class="smp-section-title">责任与结案</p>
            <div class="smp-grid">
              <label class="smp-field">
                <span>OA单号</span>
                <input ref="firstInput" v-model="form.OA单号" />
              </label>
              <label class="smp-field">
                <span>指定质控公司</span>
                <input v-model="form.指定质控公司" />
              </label>
              <label class="smp-field">
                <span>责任单位</span>
                <ComboField v-model="form.责任单位" :options="options.送检单位 || []" placeholder="选择或输入" />
              </label>
              <label class="smp-field">
                <span>责任人</span>
                <input v-model="form.责任人" />
              </label>
              <label class="smp-field">
                <span>确认者</span>
                <ComboField v-model="form.确认者" :options="options.确认者 || []" placeholder="选择或输入" />
              </label>
              <label class="smp-field">
                <span>课室负责人</span>
                <ComboField
                  v-model="form.课室负责人"
                  :options="options.课室负责人 || []"
                  placeholder="选择或输入"
                />
              </label>
              <label class="smp-field">
                <span>责任课级负责人</span>
                <input v-model="form.责任课级负责人" />
              </label>
              <label class="smp-field">
                <span>品质工程师</span>
                <input v-model="form.品质工程师" />
              </label>
              <label class="smp-field">
                <span>结案日期</span>
                <input v-model="form.结案日期" type="date" />
              </label>
              <label class="smp-field">
                <span>结案天数（自动）</span>
                <input :value="form.结案天数 ?? '保存后按送检日期计算'" readonly class="readonly" />
              </label>
            </div>
          </div>

          <div class="smp-section">
            <p class="smp-section-title">对策与验证（可插入图片）</p>
            <label class="smp-field full rich-field">
              <span>临时对策</span>
              <RichTextField v-model="form.临时对策" :rows="3" placeholder="文字或粘贴/插入图片" />
            </label>
            <label class="smp-field full rich-field">
              <span>根因分析</span>
              <RichTextField v-model="form.根因分析" :rows="3" placeholder="文字或粘贴/插入图片" />
            </label>
            <label class="smp-field full rich-field">
              <span>永久对策</span>
              <RichTextField v-model="form.永久对策" :rows="3" placeholder="文字或粘贴/插入图片" />
            </label>
            <label class="smp-field full rich-field">
              <span>改善后确认</span>
              <RichTextField v-model="form.改善后确认" :rows="3" placeholder="文字或粘贴/插入图片" />
            </label>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import ComboField from "./ComboField.vue";
import RichTextField from "./RichTextField.vue";
import {
  deleteException,
  downloadCsv,
  flattenInspections,
  inRange,
  loadSampling,
  matchKeyword,
  meName,
  plainText,
  saveException,
  splitDateTime,
} from "./samplingApi.js";

const props = defineProps({
  workbookId: String,
  canUpdate: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
  canHandle: { type: Boolean, default: false },
});

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const entries = ref([]);
const options = ref({});
const filters = ref({ keyword: "", from: "", to: "", mine: false, ngOnly: true });
const statusFilter = ref("all");
const preset = ref("");
const modal = ref({ open: false, id: "", error: "" });
const form = ref(blankForm());
const firstInput = ref(null);

const statusOptions = [
  { key: "all", label: "全部" },
  { key: "open", label: "未处理" },
  { key: "doing", label: "处理中" },
  { key: "closed", label: "已结案" },
];
const presetOptions = [
  { key: "", label: "不限日期" },
  { key: "today", label: "今天" },
  { key: "7d", label: "近7天" },
  { key: "month", label: "本月" },
];
const exporting = ref(false);

const rows = computed(() => flattenInspections(entries.value));
const isNg = (judge) => String(judge || "").toUpperCase().startsWith("NG");
const statusOf = (c) => {
  if (!c.异常处理) return { key: "open", label: "未处理", cls: "smp-badge-muted" };
  if (c.异常处理.结案日期) return { key: "closed", label: "已结案", cls: "smp-badge-ok" };
  return { key: "doing", label: "处理中", cls: "smp-badge-warn" };
};
const openCount = computed(() => rows.value.filter((c) => isNg(c.判定) && !c.异常处理).length);
const doingCount = computed(() => rows.value.filter((c) => statusOf(c).key === "doing").length);
const closedCount = computed(() => rows.value.filter((c) => statusOf(c).key === "closed").length);

function isoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function applyPreset(key) {
  preset.value = key;
  const now = new Date();
  if (key === "today") {
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
  const list = filtered.value;
  if (!list.length) {
    alert("当前筛选没有可导出的异常记录");
    return;
  }
  if (!filters.value.from && !filters.value.to) {
    const ok = confirm(`未选日期，将导出当前筛选的全部 ${list.length} 条，是否继续？`);
    if (!ok) return;
  }
  exporting.value = true;
  try {
    const headers = [
      "抽检单号", "日期", "时间", "部番", "机种", "事业部", "检验员", "判定", "不良数量",
      "OA单号", "指定质控公司", "责任单位", "责任人", "确认者", "课室负责人",
      "责任课级负责人", "品质工程师", "结案日期", "结案时间", "结案天数", "状态",
      "临时对策", "根因分析", "永久对策", "改善后确认",
    ];
    const data = list.map((c) => {
      const dt = splitDateTime(c.日期);
      const ex = c.异常处理 || {};
      const close = splitDateTime(ex.结案日期);
      return [
        c.抽检单号,
        dt.date,
        dt.time,
        c.部番 || c.机种,
        c.机种,
        c.事业部,
        c.检验员,
        c.判定,
        c.不良数量,
        ex.OA单号,
        ex.指定质控公司,
        ex.责任单位,
        ex.责任人,
        ex.确认者,
        ex.课室负责人,
        ex.责任课级负责人,
        ex.品质工程师,
        close.date,
        close.time,
        ex.结案天数,
        statusOf(c).label,
        plainText(ex.临时对策),
        plainText(ex.根因分析),
        plainText(ex.永久对策),
        plainText(ex.改善后确认),
      ];
    });
    const from = filters.value.from || "all";
    const to = filters.value.to || from;
    downloadCsv(`异常记录_${from}_${to}.csv`, headers, data);
  } finally {
    exporting.value = false;
  }
}

const filtered = computed(() =>
  rows.value.filter((c) => {
    if (filters.value.ngOnly && !isNg(c.判定)) return false;
    if (!inRange(c.日期, filters.value.from, filters.value.to)) return false;
    if (statusFilter.value !== "all" && statusOf(c).key !== statusFilter.value) return false;
    if (filters.value.mine && (c.异常处理?.登记人 || "") !== meName()) return false;
    return matchKeyword(
      filters.value.keyword,
      c.抽检单号,
      c.机种,
      c.检验员,
      c.异常处理?.OA单号,
      c.异常处理?.责任单位,
    );
  }),
);

function blankForm() {
  return {
    sid: "",
    iid: "",
    machine: "",
    inspector: "",
    judge: "",
    qty: "",
    OA单号: "",
    指定质控公司: "",
    责任单位: "",
    责任人: "",
    确认者: "",
    课室负责人: "",
    责任课级负责人: "",
    品质工程师: "",
    临时对策: "",
    根因分析: "",
    永久对策: "",
    改善后确认: "",
    结案日期: "",
    结案天数: null,
    defects: [],
  };
}

function flash(message) {
  notice.value = message;
  setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 4000);
}

async function load() {
  if (!props.workbookId) return;
  loading.value = true;
  error.value = "";
  try {
    const data = await loadSampling(props.workbookId);
    entries.value = data.entries || [];
    options.value = data.options || {};
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function openEdit(c) {
  if (!props.canHandle) return;
  const ex = c.异常处理 || {};
  form.value = {
    sid: c.送检单号,
    iid: c.抽检单号,
    machine: c.机种,
    inspector: c.检验员,
    judge: c.判定,
    qty: c.不良数量,
    OA单号: ex.OA单号 || "",
    指定质控公司: ex.指定质控公司 || "",
    责任单位: ex.责任单位 || "",
    责任人: ex.责任人 || "",
    确认者: ex.确认者 || "",
    课室负责人: ex.课室负责人 || "",
    责任课级负责人: ex.责任课级负责人 || "",
    品质工程师: ex.品质工程师 || "",
    临时对策: ex.临时对策 || "",
    根因分析: ex.根因分析 || "",
    永久对策: ex.永久对策 || "",
    改善后确认: ex.改善后确认 || "",
    结案日期: ex.结案日期 || "",
    结案天数: ex.结案天数 ?? null,
    defects: c.不良组 || [],
  };
  modal.value = { open: true, id: c.抽检单号, error: "" };
}

function closeModal() {
  modal.value = { open: false, id: "", error: "" };
}

function resetFilters() {
  filters.value = { keyword: "", from: "", to: "", mine: false, ngOnly: true };
  statusFilter.value = "all";
  preset.value = "";
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    const payload = {
      OA单号: form.value.OA单号,
      指定质控公司: form.value.指定质控公司,
      责任单位: form.value.责任单位,
      责任人: form.value.责任人,
      确认者: form.value.确认者,
      课室负责人: form.value.课室负责人,
      责任课级负责人: form.value.责任课级负责人,
      品质工程师: form.value.品质工程师,
      临时对策: form.value.临时对策,
      根因分析: form.value.根因分析,
      永久对策: form.value.永久对策,
      改善后确认: form.value.改善后确认,
      结案日期: form.value.结案日期,
    };
    const data = await saveException(props.workbookId, form.value.iid, payload);
    entries.value = data.entries || [];
    flash(`异常处理已保存：${form.value.iid}`);
    closeModal();
  } catch (err) {
    modal.value.error = err.message;
  } finally {
    saving.value = false;
  }
}

async function clear(c) {
  if (!confirm(`清除 ${c.抽检单号} 的异常处理内容？`)) return;
  try {
    const data = await deleteException(props.workbookId, c.抽检单号);
    entries.value = data.entries || [];
    flash(`已清除 ${c.抽检单号}`);
  } catch (err) {
    error.value = err.message;
  }
}

watch(
  () => modal.value.open,
  async (open) => {
    if (open) {
      await nextTick();
      firstInput.value?.focus?.();
    }
  },
);

function onKeydown(ev) {
  if (ev.key === "Escape" && modal.value.open) closeModal();
}

onMounted(() => {
  load();
  window.addEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>
