<template>
  <div class="page-block">
    <div class="toolbar card">
      <div>
        <h2>③ 异常登记</h2>
        <p class="hint">
          对 NG 的抽检记录做异常处理：OA 单号、责任归属、对策、根因、结案。不良明细已经在「② 抽检登记」里登记。
        </p>
      </div>
      <div class="toolbar-right">
        <span class="stat">未处理 <strong>{{ openCount }}</strong> 条</span>
        <button type="button" class="ghost-btn" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <div v-if="notice" class="notice card">{{ notice }}</div>
    <div v-if="error" class="error-hint card">{{ error }}</div>

    <div class="card filters">
      <input v-model="filters.keyword" class="search" placeholder="搜索 单号 / 机种 / 检验员 / OA单号 / 责任单位" />
      <label>日期 <input v-model="filters.from" type="date" /> ~ <input v-model="filters.to" type="date" /></label>
      <label class="check"><input v-model="filters.ngOnly" type="checkbox" /> 只看 NG</label>
      <label class="check"><input v-model="filters.mine" type="checkbox" /> 只看我的</label>
      <button type="button" class="link-btn" @click="resetFilters">清空</button>
      <span class="count">共 {{ filtered.length }} 条</span>
    </div>

    <div class="card table-card">
      <table>
        <thead>
          <tr>
            <th>抽检单号</th>
            <th>日期</th>
            <th>机种</th>
            <th>检验员</th>
            <th>判定</th>
            <th class="num">不良数量</th>
            <th>OA单号</th>
            <th>责任单位</th>
            <th>结案日期</th>
            <th>状态</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="11" class="empty">加载中…</td></tr>
          <tr v-else-if="!filtered.length"><td colspan="11" class="empty">没有符合条件的记录</td></tr>
          <template v-else>
            <tr v-for="c in filtered" :key="c.抽检单号">
              <td class="mono">{{ c.抽检单号 }}</td>
              <td>{{ c.日期 }}</td>
              <td>{{ c.机种 || "-" }}</td>
              <td>{{ c.检验员 }}</td>
              <td>
                <span class="badge" :class="isNg(c.判定) ? 'badge-bad' : 'badge-ok'">{{ c.判定 || "-" }}</span>
              </td>
              <td class="num">{{ c.不良数量 ?? "-" }}</td>
              <td>{{ c.异常处理?.OA单号 || "-" }}</td>
              <td>{{ c.异常处理?.责任单位 || "-" }}</td>
              <td>{{ c.异常处理?.结案日期 || "-" }}</td>
              <td>
                <span class="badge" :class="statusOf(c).cls">{{ statusOf(c).label }}</span>
              </td>
              <td class="ops">
                <button type="button" class="link-btn" @click="openEdit(c)">
                  {{ c.异常处理 ? "修改" : "处理" }}
                </button>
                <button
                  v-if="c.异常处理 && canDelete"
                  type="button"
                  class="link-btn danger"
                  @click="clear(c)"
                >
                  清除
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
          <h3>异常处理 · {{ modal.id }}</h3>
          <button type="button" class="link-btn" @click="closeModal">✕</button>
        </div>

        <div class="fixed-info">
          {{ form.sid }} · {{ form.machine }} · 检验员 {{ form.inspector }} · 判定 {{ form.judge }} ·
          不良 {{ form.qty || "-" }}
        </div>

        <div class="grid">
          <label class="field"><span>OA单号</span><input v-model="form.OA单号" /></label>
          <label class="field"><span>指定质控公司</span><input v-model="form.指定质控公司" /></label>
          <label class="field"><span>责任单位</span><input v-model="form.责任单位" list="opt-送检单位" /></label>
          <label class="field"><span>责任人</span><input v-model="form.责任人" /></label>
          <label class="field"><span>结案日期</span><input v-model="form.结案日期" type="date" /></label>
        </div>

        <label class="field block"><span>临时对策</span><textarea v-model="form.临时对策" rows="2" /></label>
        <label class="field block"><span>根因分析</span><textarea v-model="form.根因分析" rows="2" /></label>
        <label class="field block"><span>永久对策</span><textarea v-model="form.永久对策" rows="2" /></label>
        <label class="field block"><span>改善后确认</span><textarea v-model="form.改善后确认" rows="2" /></label>

        <div v-if="modal.error" class="modal-error">{{ modal.error }}</div>
        <div class="modal-actions">
          <button type="button" class="ghost-btn" @click="closeModal">取消</button>
          <button type="button" class="primary-btn" :disabled="saving" @click="save">
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
    </div>

    <datalist id="opt-送检单位"><option v-for="o in options.送检单位 || []" :key="o" :value="o" /></datalist>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import {
  deleteException,
  flattenInspections,
  inRange,
  loadSampling,
  matchKeyword,
  meName,
  saveException,
} from "./samplingApi.js";

const props = defineProps({
  workbookId: String,
  canUpdate: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
});

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const entries = ref([]);
const options = ref({});
const filters = ref({ keyword: "", from: "", to: "", mine: false, ngOnly: true });
const modal = ref({ open: false, id: "", error: "" });
const form = ref(blankForm());

const rows = computed(() => flattenInspections(entries.value));
const isNg = (judge) => String(judge || "").toUpperCase().startsWith("NG");
const statusOf = (c) => {
  if (!c.异常处理) return { label: "未处理", cls: "badge-muted" };
  if (c.异常处理.结案日期) return { label: "已结案", cls: "badge-ok" };
  return { label: "处理中", cls: "badge-warn" };
};
const openCount = computed(
  () => rows.value.filter((c) => isNg(c.判定) && !c.异常处理).length,
);

const filtered = computed(() =>
  rows.value.filter((c) => {
    if (filters.value.ngOnly && !isNg(c.判定)) return false;
    if (!inRange(c.日期, filters.value.from, filters.value.to)) return false;
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
    临时对策: "",
    根因分析: "",
    永久对策: "",
    改善后确认: "",
    结案日期: "",
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
    临时对策: ex.临时对策 || "",
    根因分析: ex.根因分析 || "",
    永久对策: ex.永久对策 || "",
    改善后确认: ex.改善后确认 || "",
    结案日期: ex.结案日期 || "",
  };
  modal.value = { open: true, id: c.抽检单号, error: "" };
}

function closeModal() {
  modal.value = { open: false, id: "", error: "" };
}

function resetFilters() {
  filters.value = { keyword: "", from: "", to: "", mine: false, ngOnly: true };
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

onMounted(load);
</script>

<style scoped>
.page-block { display: flex; flex-direction: column; gap: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.toolbar h2 { margin: 0 0 4px; font-size: 18px; }
.toolbar p { margin: 0; max-width: 700px; }
.toolbar-right { display: flex; gap: 8px; align-items: center; }
.stat { font-size: 12px; color: #666; background: #f4f6f2; padding: 4px 10px; border-radius: 12px; }
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 10px 14px; font-size: 13px; }
.filters .search { flex: 1 1 260px; min-width: 220px; padding: 6px 10px; border: 1px solid #cfcfcf; border-radius: 6px; }
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
.badge-warn { background: #fdf3e2; color: #a4691a; }
.badge-muted { background: #eee; color: #777; }
.notice { padding: 8px 12px; background: #eef6ea; color: #3a6b28; font-size: 13px; }
.error-hint { color: #b03a2e; padding: 10px 12px; }
.hint { color: #8a8a8a; font-size: 12px; }
.overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 20px; }
.modal { background: #fff; border-radius: 10px; width: min(720px, 100%); max-height: 90vh; overflow: auto; padding: 18px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.modal-head h3 { margin: 0; font-size: 16px; }
.fixed-info { margin-bottom: 12px; padding: 8px 12px; background: #f7f9f6; border-radius: 6px; font-size: 13px; color: #555; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.field.block { margin-top: 10px; }
.field span { color: #666; }
.field input, .field select, .field textarea { padding: 6px 8px; border: 1px solid #cfcfcf; border-radius: 6px; font-size: 13px; font-family: inherit; }
.field textarea { resize: vertical; }
.modal-error { margin-top: 10px; color: #b03a2e; font-size: 13px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.primary-btn, .ghost-btn { padding: 6px 14px; border-radius: 6px; border: 1px solid transparent; cursor: pointer; font-size: 13px; }
.primary-btn { background: #548235; color: #fff; }
.primary-btn:disabled { opacity: 0.6; }
.ghost-btn { background: #fff; border-color: #cfcfcf; color: #444; }
.link-btn { background: none; border: none; color: #548235; cursor: pointer; font-size: 13px; padding: 0 4px; }
.link-btn.danger { color: #c0392b; }
</style>
