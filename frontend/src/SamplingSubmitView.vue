<template>
  <div class="page-block">
    <div class="toolbar card">
      <div>
        <h2>① 送检登记</h2>
        <p class="hint">外部/产线人员填写。一批送检一张单，登记到「送检数量」。</p>
      </div>
      <div class="toolbar-right">
        <span class="stat">今日我登记 <strong>{{ todayMine }}</strong> 条</span>
        <span class="stat">待抽检 <strong>{{ pending }}</strong> 张</span>
        <button v-if="canCreate" type="button" class="primary-btn" @click="openNew">+ 新增送检</button>
        <button type="button" class="ghost-btn" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <div v-if="notice" class="notice card">{{ notice }}</div>
    <div v-if="error" class="error-hint card">{{ error }}</div>

    <div class="card filters">
      <input v-model="filters.keyword" class="search" placeholder="搜索 单号 / 机种 / 送检单位" />
      <label>日期 <input v-model="filters.from" type="date" /> ~ <input v-model="filters.to" type="date" /></label>
      <label class="check"><input v-model="filters.mine" type="checkbox" /> 只看我的</label>
      <button type="button" class="link-btn" @click="resetFilters">清空</button>
      <span class="count">共 {{ filtered.length }} 条</span>
    </div>

    <div class="card table-card">
      <table>
        <thead>
          <tr>
            <th>送检单号</th>
            <th>日期</th>
            <th>机种</th>
            <th>送检单位</th>
            <th class="num">送检数量</th>
            <th class="num">抽检人数</th>
            <th class="num">异常</th>
            <th>状态</th>
            <th>登记人</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="10" class="empty">加载中…</td></tr>
          <tr v-else-if="!filtered.length"><td colspan="10" class="empty">没有符合条件的送检单</td></tr>
          <template v-else>
            <tr v-for="e in filtered" :key="e.送检单号">
            <td class="mono">{{ e.送检单号 }}</td>
            <td>{{ e.日期 }}</td>
            <td>{{ e.机种 || "-" }}</td>
            <td>{{ e.送检单位 || "-" }}</td>
            <td class="num">{{ e.送检数量 ?? "-" }}</td>
            <td class="num">{{ (e.抽检 || []).length }}</td>
            <td class="num">{{ defectCount(e) }}</td>
            <td>
              <span class="badge" :class="status(e).cls">{{ status(e).label }}</span>
            </td>
            <td>{{ e.登记人 || "-" }}</td>
            <td class="ops">
              <button type="button" class="link-btn" @click="openEdit(e)">编辑</button>
              <button v-if="canDelete" type="button" class="link-btn danger" @click="remove(e)">
                删除
              </button>
            </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="modal.open" class="overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ modal.id ? `编辑 ${modal.id}` : "新增送检单" }}</h3>
          <button type="button" class="link-btn" @click="closeModal">✕</button>
        </div>
        <div class="grid">
          <label class="field"><span>日期</span><input v-model="form.日期" type="date" /></label>
          <label class="field">
            <span>时间段</span>
            <input v-model="form.时间段" list="opt-时间段" />
          </label>
          <label class="field">
            <span>送检类型</span>
            <input v-model="form.送检类型" list="opt-送检类型" />
          </label>
          <label class="field"><span>机种 *</span><input v-model="form.机种" list="opt-机种" /></label>
          <label class="field">
            <span>送检单位</span>
            <input v-model="form.送检单位" list="opt-送检单位" />
          </label>
          <label class="field">
            <span>送检数量 *</span>
            <input v-model="form.送检数量" type="number" min="0" step="any" />
          </label>
          <label class="field">
            <span>同批送检次数</span>
            <input v-model="form.同批送检次数" type="number" min="0" />
          </label>
          <label class="field">
            <span>是否紧急出货</span>
            <select v-model="form.是否紧急出货">
              <option value="">-</option>
              <option value="是">是</option>
              <option value="否">否</option>
            </select>
          </label>
          <label class="field"><span>确认者</span><input v-model="form.确认者" list="opt-确认者" /></label>
          <label class="field">
            <span>课室负责人</span>
            <input v-model="form.课室负责人" list="opt-课室负责人" />
          </label>
          <label class="field wide"><span>层别备注</span><input v-model="form.层别备注" /></label>
        </div>
        <div v-if="modal.error" class="modal-error">{{ modal.error }}</div>
        <div class="modal-actions">
          <button type="button" class="ghost-btn" @click="closeModal">取消</button>
          <button type="button" class="primary-btn" :disabled="saving" @click="save">
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
    </div>

    <datalist id="opt-机种"><option v-for="o in options.机种 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-送检单位"><option v-for="o in options.送检单位 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-时间段"><option v-for="o in options.时间段 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-送检类型"><option v-for="o in options.送检类型 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-确认者"><option v-for="o in options.确认者 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-课室负责人"><option v-for="o in options.课室负责人 || []" :key="o" :value="o" /></datalist>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import {
  createSubmission,
  defectCount,
  deleteSubmission,
  inRange,
  loadSampling,
  matchKeyword,
  meName,
  submissionStatus,
  todayStr,
  updateSubmission,
} from "./samplingApi.js";

const props = defineProps({
  workbookId: String,
  canCreate: { type: Boolean, default: false },
  canUpdate: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
});

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const entries = ref([]);
const options = ref({});
const filters = ref({ keyword: "", from: "", to: "", mine: false });
const modal = ref({ open: false, id: "", error: "" });
const form = ref(blankForm());

const status = submissionStatus;

const filtered = computed(() =>
  entries.value.filter((e) => {
    if (!inRange(e.日期, filters.value.from, filters.value.to)) return false;
    if (filters.value.mine && (e.登记人 || "") !== meName()) return false;
    return matchKeyword(filters.value.keyword, e.送检单号, e.机种, e.送检单位);
  }),
);
const todayMine = computed(() => {
  const today = todayStr();
  return entries.value.filter((e) => e.日期 === today && (e.登记人 || "") === meName()).length;
});
const pending = computed(() => entries.value.filter((e) => !(e.抽检 || []).length).length);

function blankForm() {
  return {
    日期: todayStr(),
    时间段: "8:00-12:00",
    送检类型: "正常送检",
    机种: "",
    送检单位: "",
    送检数量: "",
    同批送检次数: "",
    是否紧急出货: "",
    层别备注: "",
    确认者: "",
    课室负责人: "",
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

function openNew() {
  form.value = blankForm();
  modal.value = { open: true, id: "", error: "" };
}

function openEdit(entry) {
  const next = blankForm();
  for (const key of Object.keys(next)) {
    if (entry[key] !== undefined && entry[key] !== null) next[key] = entry[key];
  }
  form.value = next;
  modal.value = { open: true, id: entry.送检单号, error: "" };
}

function closeModal() {
  modal.value = { open: false, id: "", error: "" };
}

function resetFilters() {
  filters.value = { keyword: "", from: "", to: "", mine: false };
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    const payload = { ...form.value };
    const data = modal.value.id
      ? await updateSubmission(props.workbookId, modal.value.id, payload)
      : await createSubmission(props.workbookId, payload);
    entries.value = data.entries || [];
    flash(`已保存 ${data.submission?.送检单号 || ""}`);
    closeModal();
  } catch (err) {
    modal.value.error = err.message;
  } finally {
    saving.value = false;
  }
}

async function remove(entry) {
  if (!confirm(`确定删除 ${entry.送检单号}？其抽检与异常记录会一并删除。`)) return;
  try {
    const data = await deleteSubmission(props.workbookId, entry.送检单号);
    entries.value = data.entries || [];
    flash(`已删除 ${entry.送检单号}`);
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(load);
</script>

<style scoped>
.page-block { display: flex; flex-direction: column; gap: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.toolbar h2 { margin: 0 0 4px; font-size: 18px; }
.toolbar p { margin: 0; max-width: 680px; }
.toolbar-right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.stat { font-size: 12px; color: #666; background: #f4f6f2; padding: 4px 10px; border-radius: 12px; }
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 10px 14px; font-size: 13px; }
.filters .search { flex: 1 1 240px; min-width: 200px; padding: 6px 10px; border: 1px solid #cfcfcf; border-radius: 6px; }
.filters input[type="date"] { padding: 4px 6px; border: 1px solid #cfcfcf; border-radius: 6px; }
.filters .check { display: flex; align-items: center; gap: 4px; }
.filters .count { margin-left: auto; color: #888; }
.table-card { padding: 0; overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; text-align: left; white-space: nowrap; }
th { background: #fafbf9; color: #555; font-weight: 600; }
.num { text-align: right; }
.ops { text-align: right; }
td.mono { color: #888; font-size: 12px; }
.empty { text-align: center; color: #999; padding: 28px; }
.badge { font-size: 12px; padding: 1px 8px; border-radius: 10px; }
.badge-ok { background: #e5f3df; color: #3a6b28; }
.badge-bad { background: #fbe3e1; color: #b03a2e; }
.badge-muted { background: #eee; color: #777; }
.notice { padding: 8px 12px; background: #eef6ea; color: #3a6b28; font-size: 13px; }
.error-hint { color: #b03a2e; padding: 10px 12px; }
.hint { color: #8a8a8a; font-size: 12px; }
.overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 20px; }
.modal { background: #fff; border-radius: 10px; width: min(760px, 100%); max-height: 90vh; overflow: auto; padding: 18px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.modal-head h3 { margin: 0; font-size: 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.field.wide { grid-column: 1 / -1; }
.field span { color: #666; }
.field input, .field select { padding: 6px 8px; border: 1px solid #cfcfcf; border-radius: 6px; font-size: 13px; }
.modal-error { margin-top: 10px; color: #b03a2e; font-size: 13px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.primary-btn, .ghost-btn { padding: 6px 14px; border-radius: 6px; border: 1px solid transparent; cursor: pointer; font-size: 13px; }
.primary-btn { background: #548235; color: #fff; }
.primary-btn:disabled { opacity: 0.6; }
.ghost-btn { background: #fff; border-color: #cfcfcf; color: #444; }
.link-btn { background: none; border: none; color: #548235; cursor: pointer; font-size: 13px; padding: 0 4px; }
.link-btn.danger { color: #c0392b; }
</style>
