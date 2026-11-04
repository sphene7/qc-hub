<template>
  <div class="page-block">
    <div class="toolbar card">
      <div>
        <h2>② 抽检登记</h2>
        <p class="hint">
          检验员填写。一条 = 一名检验员对一张送检单的抽检；不良明细在这一条里登记，不良数量/不良率/判定自动计算。
        </p>
      </div>
      <div class="toolbar-right">
        <span class="stat">今日我登记 <strong>{{ todayMine }}</strong> 条</span>
        <span v-if="pendingCount" class="stat warn">还有 {{ pendingCount }} 张送检单未抽检</span>
        <button v-if="canUpdate" type="button" class="primary-btn" @click="openNew">+ 登记抽检</button>
        <button type="button" class="ghost-btn" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <div v-if="notice" class="notice card">{{ notice }}</div>
    <div v-if="error" class="error-hint card">{{ error }}</div>

    <div class="card filters">
      <input v-model="filters.keyword" class="search" placeholder="搜索 单号 / 机种 / 检验员 / 现象" />
      <label>日期 <input v-model="filters.from" type="date" /> ~ <input v-model="filters.to" type="date" /></label>
      <label class="check"><input v-model="filters.mine" type="checkbox" /> 只看我的</label>
      <label class="check">
        <select v-model="filters.result">
          <option value="">全部结果</option>
          <option value="ok">OK</option>
          <option value="ng">NG</option>
        </select>
      </label>
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
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="18" class="empty">加载中…</td></tr>
          <tr v-else-if="!filtered.length"><td colspan="18" class="empty">没有符合条件的抽检记录</td></tr>
          <template v-else>
            <tr v-for="c in filtered" :key="c.抽检单号">
              <td class="mono">{{ c.抽检单号 }}</td>
              <td>{{ c.日期 }}</td>
              <td>{{ c.机种 || "-" }}</td>
              <td class="num">{{ c.外观抽检数量 ?? "-" }}</td>
              <td class="num">{{ c.机能抽检数量 ?? "-" }}</td>
              <td class="num">{{ c.不良数量 ?? "-" }}</td>
              <td class="num">{{ rateText(c.不良率) }}</td>
              <td class="num">{{ c.抽检批 ? 1 : 0 }}</td>
              <td class="num">{{ c.合格批 ? 1 : 0 }}</td>
              <td class="num">{{ rateText(c.合格批率) }}</td>
              <td>
                <span class="badge" :class="isNg(c.判定) ? 'badge-bad' : 'badge-ok'">{{ c.判定 || "-" }}</span>
              </td>
              <td>{{ c.不良属性 || "-" }}</td>
              <td>{{ c.不良位置 || "-" }}</td>
              <td>{{ c.现象 || "-" }}</td>
              <td class="num">{{ c.数量 || "-" }}</td>
              <td>{{ c.检验员 }}</td>
              <td>{{ c.登记人 || "-" }}</td>
              <td class="ops">
                <button type="button" class="link-btn" @click="openEdit(c)">修改</button>
                <button v-if="canDelete" type="button" class="link-btn danger" @click="remove(c)">
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
          <h3>{{ modal.id ? `修改 ${modal.id}` : "登记抽检" }}</h3>
          <button type="button" class="link-btn" @click="closeModal">✕</button>
        </div>

        <label v-if="!modal.id" class="field full">
          <span>送检单 *</span>
          <select v-model="form.sid">
            <option value="">— 选择送检单 —</option>
            <option v-for="s in optionsList" :key="s.送检单号" :value="s.送检单号">
              {{ s.送检单号 }} · {{ s.日期 }} · {{ s.机种 }} · 送检 {{ s.送检数量 ?? "-" }}
              {{ (s.抽检 || []).length ? "（已抽检）" : "" }}
            </option>
          </select>
        </label>
        <div v-else class="fixed-info">
          {{ form.sid }} · {{ selectedSubmission?.机种 }} · 送检 {{ selectedSubmission?.送检数量 }}
        </div>

        <div class="grid">
          <label class="field">
            <span>外观抽检数量</span>
            <input v-model="form.外观抽检数量" type="number" min="0" step="any" />
          </label>
          <label class="field">
            <span>机能抽检数量</span>
            <input v-model="form.机能抽检数量" type="number" min="0" step="any" />
          </label>
          <label class="field">
            <span>检验员 *</span>
            <input v-model="form.检验员" list="opt-检验员" placeholder="姓名" />
          </label>
        </div>

        <div class="defects">
          <div class="defects-head">
            <span>不良明细（可多组，留空即 OK）</span>
            <button type="button" class="link-btn" @click="addDefect">+ 添加不良</button>
          </div>
          <p v-if="!form.defects.length" class="hint">无不良可不填</p>
          <div v-for="(d, i) in form.defects" :key="i" class="defect-row">
            <label class="field">
              <span>不良属性</span>
              <select v-model="d.不良属性">
                <option value="">-</option>
                <option v-for="o in options.不良属性 || []" :key="o" :value="o">{{ o }}</option>
              </select>
            </label>
            <label class="field">
              <span>不良位置</span>
              <input v-model="d.不良位置" list="opt-不良位置" />
            </label>
            <label class="field">
              <span>现象</span>
              <input v-model="d.现象" list="opt-现象" />
            </label>
            <label class="field qty">
              <span>数量</span>
              <input v-model="d.数量" type="number" min="0" step="any" />
            </label>
            <button type="button" class="link-btn danger" @click="removeDefect(i)">删除</button>
          </div>
        </div>

        <div class="computed">
          <span>不良数量 <strong>{{ preview.total }}</strong></span>
          <span>不良率 <strong>{{ rateText(preview.rate) }}</strong></span>
          <span>抽检批 <strong>{{ modal.id ? '按保存后计算' : 1 }}</strong></span>
          <span>合格批 <strong>{{ preview.total ? 0 : 1 }}</strong></span>
          <span>判定 <strong :class="preview.total ? 'bad' : 'ok'">{{ preview.judge }}</strong></span>
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

    <datalist id="opt-检验员"><option v-for="o in options.检验员 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-不良位置"><option v-for="o in options.不良位置 || []" :key="o" :value="o" /></datalist>
    <datalist id="opt-现象"><option v-for="o in options.现象 || []" :key="o" :value="o" /></datalist>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
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
});

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const entries = ref([]);
const options = ref({});
const filters = ref({ keyword: "", from: "", to: "", mine: false, result: "" });
const modal = ref({ open: false, id: "", error: "" });
const form = ref(blankForm());

const rows = computed(() => flattenInspections(entries.value));
const isNg = (judge) => String(judge || "").toUpperCase().startsWith("NG");
const rateText = (v) => (v == null || v === "" || Number.isNaN(Number(v)) ? "-" : `${(Number(v) * 100).toFixed(1)}%`);

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
  return rows.value.filter((c) => c.日期 === today && (c.登记人 || "") === meName()).length;
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
const selectedSubmission = computed(() => entries.value.find((e) => e.送检单号 === form.value.sid) || null);
const preview = computed(() => {
  const total = (form.value.defects || []).reduce((n, d) => n + (Number(d.数量) || 0), 0);
  const filled = (form.value.defects || []).filter(
    (d) => d.不良位置 || d.现象 || d.数量 !== "" || d.不良属性,
  ).length;
  const appearance = Number(form.value.外观抽检数量) || 0;
  return {
    total,
    rate: appearance > 0 ? total / appearance : null,
    judge: filled ? (filled === 1 ? "NG" : `NG×${filled}`) : "OK",
  };
});

function blankForm() {
  return {
    sid: "",
    外观抽检数量: "",
    机能抽检数量: "",
    检验员: "",
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

function openNew() {
  const pending = entries.value.find((e) => !(e.抽检 || []).length);
  form.value = { ...blankForm(), sid: pending?.送检单号 || "" };
  modal.value = { open: true, id: "", error: "" };
}

function openEdit(c) {
  form.value = {
    sid: c.送检单号,
    外观抽检数量: c.外观抽检数量 ?? "",
    机能抽检数量: c.机能抽检数量 ?? "",
    检验员: c.检验员 || "",
    defects: (c.不良组 || []).map((d) => ({ ...d })),
  };
  if (!form.value.defects.length) form.value.defects = [];
  modal.value = { open: true, id: c.抽检单号, error: "" };
}

function closeModal() {
  modal.value = { open: false, id: "", error: "" };
}

function resetFilters() {
  filters.value = { keyword: "", from: "", to: "", mine: false, result: "" };
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

onMounted(load);
</script>

<style scoped>
.page-block { display: flex; flex-direction: column; gap: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.toolbar h2 { margin: 0 0 4px; font-size: 18px; }
.toolbar p { margin: 0; max-width: 700px; }
.toolbar-right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.stat { font-size: 12px; color: #666; background: #f4f6f2; padding: 4px 10px; border-radius: 12px; }
.stat.warn { background: #fdf3e2; color: #a4691a; }
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 10px 14px; font-size: 13px; }
.filters .search { flex: 1 1 240px; min-width: 200px; padding: 6px 10px; border: 1px solid #cfcfcf; border-radius: 6px; }
.filters input[type="date"], .filters select { padding: 4px 6px; border: 1px solid #cfcfcf; border-radius: 6px; }
.filters .check { display: flex; align-items: center; gap: 4px; }
.filters .count { margin-left: auto; color: #888; }
.table-card { padding: 0; overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { padding: 7px 9px; border-bottom: 1px solid #f0f0f0; text-align: left; white-space: nowrap; }
th { background: #fafbf9; color: #555; font-weight: 600; }
.num { text-align: right; }
.ops { text-align: right; }
td.mono { color: #888; }
.empty { text-align: center; color: #999; padding: 28px; }
.badge { font-size: 12px; padding: 1px 8px; border-radius: 10px; }
.badge-ok { background: #e5f3df; color: #3a6b28; }
.badge-bad { background: #fbe3e1; color: #b03a2e; }
.notice { padding: 8px 12px; background: #eef6ea; color: #3a6b28; font-size: 13px; }
.error-hint { color: #b03a2e; padding: 10px 12px; }
.hint { color: #8a8a8a; font-size: 12px; }
.overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 20px; }
.modal { background: #fff; border-radius: 10px; width: min(760px, 100%); max-height: 90vh; overflow: auto; padding: 18px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.modal-head h3 { margin: 0; font-size: 16px; }
.fixed-info { margin-bottom: 12px; padding: 8px 12px; background: #f7f9f6; border-radius: 6px; font-size: 13px; color: #555; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.field.full { width: 100%; margin-bottom: 12px; }
.field span { color: #666; }
.field input, .field select { padding: 6px 8px; border: 1px solid #cfcfcf; border-radius: 6px; font-size: 13px; }
.defects { margin-top: 14px; padding-top: 12px; border-top: 1px dashed #e2e2e2; }
.defects-head { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #555; margin-bottom: 8px; }
.defect-row { display: grid; grid-template-columns: 1fr 1fr 1fr 90px auto; gap: 8px; align-items: end; padding: 8px; border-radius: 6px; background: #fafafa; margin-bottom: 6px; }
.computed { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 12px; padding: 10px 12px; background: #f6f8f4; border-radius: 6px; font-size: 13px; color: #556; }
.computed strong { color: #222; }
.computed .bad { color: #b03a2e; }
.computed .ok { color: #3a6b28; }
.modal-error { margin-top: 10px; color: #b03a2e; font-size: 13px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.primary-btn, .ghost-btn { padding: 6px 14px; border-radius: 6px; border: 1px solid transparent; cursor: pointer; font-size: 13px; }
.primary-btn { background: #548235; color: #fff; }
.primary-btn:disabled { opacity: 0.6; }
.ghost-btn { background: #fff; border-color: #cfcfcf; color: #444; }
.link-btn { background: none; border: none; color: #548235; cursor: pointer; font-size: 13px; padding: 0 4px; }
.link-btn.danger { color: #c0392b; }
@media (max-width: 900px) {
  .defect-row { grid-template-columns: 1fr 1fr; }
}
</style>
