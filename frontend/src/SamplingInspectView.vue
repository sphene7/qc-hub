<template>
  <div class="smp-page">
    <div class="smp-toolbar card">
      <div class="smp-stats">
        <span class="smp-stat">今日我登记 <strong>{{ todayMine }}</strong> 条</span>
        <span class="smp-stat">本月 <strong>{{ monthCount }}</strong> 条</span>
        <span v-if="pendingCount" class="smp-stat warn">待抽检 <strong>{{ pendingCount }}</strong> 张</span>
      </div>
      <span class="smp-spacer"></span>
      <button v-if="canInspect" type="button" class="smp-btn smp-btn-primary" @click="openNew()">
        + 登记抽检
      </button>
      <button type="button" class="smp-btn smp-btn-ghost" :disabled="loading" @click="load">刷新</button>
    </div>

    <div v-if="notice" class="smp-notice">{{ notice }}</div>
    <div v-if="error" class="smp-error">{{ error }}</div>

    <div class="smp-filters card">
      <div class="smp-search">
        <input v-model="filters.keyword" placeholder="搜索 单号 / 机种 / 检验员 / 现象" />
      </div>
      <div class="smp-seg">
        <button
          v-for="opt in resultOptions"
          :key="opt.key"
          type="button"
          :class="{ active: filters.result === opt.key }"
          @click="filters.result = opt.key"
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
              <th class="num">外观抽检数量</th>
              <th class="num">机能抽检数量</th>
              <th class="num">不良数量</th>
              <th class="num">不良率</th>
              <th class="num">抽检批</th>
              <th class="num">合格批</th>
              <th class="num">合格批率</th>
              <th>判定</th>
              <th>不良属性</th>
              <th>不良位置</th>
              <th>现象</th>
              <th class="num">数量</th>
              <th>检验员</th>
              <th>登记人</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="20"><div class="smp-empty">加载中…</div></td></tr>
            <tr v-else-if="!filtered.length">
              <td colspan="20">
                <div class="smp-empty">
                  <span class="smp-empty-icon">🔎</span>
                  没有符合条件的抽检记录
                </div>
              </td>
            </tr>
            <template v-else>
              <tr v-for="c in filtered" :key="c.抽检单号" class="clickable" @click="openEdit(c)">
                <td class="ops" @click.stop>
                  <button v-if="canInspect" type="button" class="smp-link" @click="openEdit(c)">修改</button>
                  <button v-if="canDelete" type="button" class="smp-link danger" @click="remove(c)">
                    删除
                  </button>
                </td>
                <td class="mono">{{ c.抽检单号 }}</td>
                <td>{{ c.日期 }}</td>
                <td class="mono">{{ c.部番 || c.机种 || "-" }}</td>
                <td>{{ c.机种 || "-" }}</td>
                <td>{{ c.事业部 || "-" }}</td>
                <td class="num">{{ c.外观抽检数量 ?? "-" }}</td>
                <td class="num">{{ c.机能抽检数量 ?? "-" }}</td>
                <td class="num">{{ c.不良数量 ?? "-" }}</td>
                <td class="num">{{ rateText(c.不良率) }}</td>
                <td class="num">{{ c.抽检批 ? 1 : 0 }}</td>
                <td class="num">{{ c.合格批 ? 1 : 0 }}</td>
                <td class="num">{{ rateText(c.合格批率) }}</td>
                <td>
                  <span class="smp-badge" :class="isNg(c.判定) ? 'smp-badge-bad' : 'smp-badge-ok'">
                    {{ c.判定 || "-" }}
                  </span>
                </td>
                <td>{{ c.不良属性 || "-" }}</td>
                <td>{{ c.不良位置 || "-" }}</td>
                <td>{{ c.现象 || "-" }}</td>
                <td class="num">{{ c.数量 || "-" }}</td>
                <td>{{ c.检验员 }}</td>
                <td>{{ c.登记人 || "-" }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="modal.open" class="smp-overlay" @click.self="closeModal">
      <div class="smp-modal">
        <div class="smp-modal-head">
          <h3>{{ modal.id ? `修改 ${modal.id}` : "登记抽检" }}</h3>
          <button type="button" class="smp-modal-close" @click="closeModal">✕</button>
        </div>
        <div class="smp-modal-body">
          <label v-if="!modal.id" class="smp-field full" style="margin-bottom: 14px">
            <span>送检单<span class="smp-required">*</span></span>
            <select v-model="form.sid">
              <option value="">— 选择送检单 —</option>
              <option v-for="s in optionsList" :key="s.送检单号" :value="s.送检单号">
                {{ s.送检单号 }} · {{ s.日期 }} · {{ s.机种 }} · 送检 {{ s.送检数量 ?? "-" }}
                {{ (s.抽检 || []).length ? "（已抽检）" : "" }}
              </option>
            </select>
          </label>
          <div v-else class="smp-fixed-info">
            {{ form.sid }} · {{ selectedSubmission?.机种 }} · 送检 {{ selectedSubmission?.送检数量 }}
          </div>

          <div class="smp-section">
            <p class="smp-section-title">抽检信息</p>
            <div class="smp-grid">
              <label class="smp-field">
                <span>检验员<span class="smp-required">*</span></span>
                <input ref="firstInput" v-model="form.检验员" list="opt-检验员" placeholder="姓名" />
              </label>
              <label class="smp-field">
                <span>外观抽检数量</span>
                <input v-model="form.外观抽检数量" type="number" min="0" step="any" />
              </label>
              <label class="smp-field">
                <span>机能抽检数量</span>
                <input v-model="form.机能抽检数量" type="number" min="0" step="any" />
              </label>
            </div>
          </div>

          <div class="smp-section">
            <p class="smp-section-title">
              不良明细
              <button type="button" class="smp-link" @click="addDefect">+ 添加不良</button>
            </p>
            <p v-if="!form.defects.length" class="smp-hint">无不良可不填，判定为 OK</p>
            <div v-for="(d, i) in form.defects" :key="i" class="smp-defect-row">
              <label class="smp-field">
                <span>不良属性</span>
                <select v-model="d.不良属性">
                  <option value="">-</option>
                  <option v-for="o in options.不良属性 || []" :key="o" :value="o">{{ o }}</option>
                </select>
              </label>
              <label class="smp-field">
                <span>不良位置</span>
                <input v-model="d.不良位置" list="opt-不良位置" />
              </label>
              <label class="smp-field">
                <span>现象</span>
                <input v-model="d.现象" list="opt-现象" />
              </label>
              <label class="smp-field">
                <span>数量</span>
                <input v-model="d.数量" type="number" min="0" step="any" />
              </label>
              <button type="button" class="smp-link danger" @click="removeDefect(i)">删除</button>
            </div>
          </div>

          <div class="smp-chips">
            <span>不良数量<strong>{{ preview.total }}</strong></span>
            <span>不良率<strong>{{ rateText(preview.rate) }}</strong></span>
            <span>抽检批<strong>{{ modal.id ? "按保存计算" : 1 }}</strong></span>
            <span>合格批<strong>{{ preview.total ? 0 : 1 }}</strong></span>
            <span>
              判定
              <strong :class="preview.total ? 'bad' : 'ok'">{{ preview.judge }}</strong>
            </span>
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

    <datalist id="opt-检验员"><option v-for="o in options.检验员 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-不良位置"><option v-for="o in options.不良位置 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-现象"><option v-for="o in options.现象 || []" :key="o" :value="o" /></datalist>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  addInspection,
  deleteInspection,
  flattenInspections,
  inRange,
  loadSampling,
  matchKeyword,
  meName,
  todayStr,
  updateInspection,
} from "./samplingApi.js";

const props = defineProps({
  workbookId: String,
  canUpdate: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
  canInspect: { type: Boolean, default: false },
});

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const entries = ref([]);
const options = ref({});
const filters = ref({ keyword: "", from: "", to: "", mine: false, result: "" });
const preset = ref("");
const modal = ref({ open: false, id: "", error: "", version: null });
const form = ref(blankForm());
const firstInput = ref(null);

const resultOptions = [
  { key: "", label: "全部" },
  { key: "ok", label: "OK" },
  { key: "ng", label: "NG" },
];
const presetOptions = [
  { key: "", label: "不限日期" },
  { key: "today", label: "今天" },
  { key: "7d", label: "近7天" },
  { key: "month", label: "本月" },
];

const rows = computed(() => flattenInspections(entries.value));
const isNg = (judge) => String(judge || "").toUpperCase().startsWith("NG");
const rateText = (v) =>
  v == null || v === "" || Number.isNaN(Number(v)) ? "-" : `${(Number(v) * 100).toFixed(1)}%`;

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

const filtered = computed(() =>
  rows.value.filter((c) => {
    if (!inRange(c.日期, filters.value.from, filters.value.to)) return false;
    if (filters.value.mine && (c.登记人 || "") !== meName()) return false;
    const ng = isNg(c.判定);
    if (filters.value.result === "ok" && ng) return false;
    if (filters.value.result === "ng" && !ng) return false;
    return matchKeyword(filters.value.keyword, c.抽检单号, c.机种, c.检验员, c.现象);
  }),
);
const todayMine = computed(() => {
  const today = todayStr();
  return rows.value.filter((c) => String(c.日期 || "").slice(0, 10) === today && (c.登记人 || "") === meName()).length;
});
const monthCount = computed(() => {
  const month = todayStr().slice(0, 7);
  return rows.value.filter((c) => String(c.日期 || "").slice(0, 7) === month).length;
});
const pendingCount = computed(() => entries.value.filter((e) => !(e.抽检 || []).length).length);
const optionsList = computed(() => {
  const list = [...entries.value];
  list.sort((a, b) => {
    const ac = (a.抽检 || []).length ? 1 : 0;
    const bc = (b.抽检 || []).length ? 1 : 0;
    if (ac !== bc) return ac - bc;
    return String(b.日期).localeCompare(String(a.日期));
  });
  return list;
});
const selectedSubmission = computed(
  () => entries.value.find((e) => e.送检单号 === form.value.sid) || null,
);
const preview = computed(() => {
  const filled = (form.value.defects || []).filter(
    (d) => d.不良位置 || d.现象 || d.数量 !== "" || d.不良属性,
  );
  const total = filled.reduce((n, d) => n + (Number(d.数量) || 0), 0);
  const appearance = Number(form.value.外观抽检数量) || 0;
  return {
    total,
    rate: appearance > 0 ? total / appearance : null,
    judge: filled.length ? (filled.length === 1 ? "NG" : `NG×${filled.length}`) : "OK",
  };
});

function blankForm() {
  return { sid: "", 外观抽检数量: "", 机能抽检数量: "", 检验员: "", defects: [] };
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

function openNew(presetSid = "") {
  const target = presetSid
    ? entries.value.find((e) => e.送检单号 === presetSid)
    : entries.value.find((e) => !(e.抽检 || []).length);
  form.value = { ...blankForm(), sid: target?.送检单号 || "" };
  modal.value = { open: true, id: "", error: "", version: null };
}

function openFromQuery() {
  const sid = String(route.query.sid || "").trim();
  if (!sid || !props.canInspect) return;
  if (!entries.value.some((e) => e.送检单号 === sid)) return;
  openNew(sid);
  router.replace({ query: {} });
}

function openEdit(c) {
  if (!props.canInspect) return;
  form.value = {
    sid: c.送检单号,
    外观抽检数量: c.外观抽检数量 ?? "",
    机能抽检数量: c.机能抽检数量 ?? "",
    检验员: c.检验员 || "",
    defects: (c.不良组 || []).map((d) => ({ ...d })),
  };
  modal.value = { open: true, id: c.抽检单号, error: "", version: c.版本 ?? null };
}

function closeModal() {
  modal.value = { open: false, id: "", error: "", version: null };
}

function resetFilters() {
  filters.value = { keyword: "", from: "", to: "", mine: false, result: "" };
  preset.value = "";
}

function addDefect() {
  form.value.defects.push({ 不良属性: "", 不良位置: "", 现象: "", 数量: "" });
}

function removeDefect(i) {
  form.value.defects.splice(i, 1);
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    const payload = {
      外观抽检数量: form.value.外观抽检数量,
      机能抽检数量: form.value.机能抽检数量,
      检验员: form.value.检验员,
      defects: form.value.defects,
    };
    if (modal.value.id && modal.value.version != null) {
      payload.expected_version = modal.value.version;
    }
    let data;
    if (modal.value.id) {
      data = await updateInspection(props.workbookId, modal.value.id, payload);
    } else {
      if (!form.value.sid) throw new Error("请选择送检单");
      data = await addInspection(props.workbookId, form.value.sid, payload);
    }
    entries.value = data.entries || [];
    flash(`已保存：${form.value.检验员} / ${form.value.sid}`);
    closeModal();
  } catch (err) {
    modal.value.error = err.message;
    if (String(err.message).includes("刷新")) await load();
  } finally {
    saving.value = false;
  }
}

async function remove(c) {
  if (!confirm(`删除 ${c.检验员}（${c.抽检单号}）的抽检记录及其异常处理吗？`)) return;
  try {
    const data = await deleteInspection(props.workbookId, c.抽检单号);
    entries.value = data.entries || [];
    flash(`已删除 ${c.抽检单号}`);
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

onMounted(async () => {
  await load();
  openFromQuery();
  window.addEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>
