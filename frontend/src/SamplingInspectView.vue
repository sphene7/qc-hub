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
        <input v-model="filters.keyword" placeholder="搜索 单号 / 部番 / 机种 / 检验员 / 现象" />
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
              <th>送检类型</th>
              <th>事业部</th>
              <th class="num">送检数量</th>
              <th class="num">外观抽检数量</th>
              <th class="num">机能抽检数量</th>
              <th class="num">不良数量</th>
              <th class="num">不良率</th>
              <th class="num">抽检批</th>
              <th class="num">合格批</th>
              <th class="num">合格批率</th>
              <th>判定</th>
              <th>不良属性</th>
              <th>不良现象</th>
              <th>不良位置</th>
              <th>是否紧急出货</th>
              <th class="num">数量</th>
              <th>检验员</th>
              <th>登记人</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="23"><div class="smp-empty">加载中…</div></td></tr>
            <tr v-else-if="!filtered.length">
              <td colspan="23">
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
                <td>{{ c.送检类型 || "-" }}</td>
                <td>{{ c.事业部 || "-" }}</td>
                <td class="num">{{ c.送检数量 ?? "-" }}</td>
                <td class="num">{{ c.外观抽检数量 ?? "-" }}</td>
                <td class="num">{{ c.机能抽检数量 ?? "-" }}</td>
                <td class="num">{{ c.不良数量 ?? "-" }}</td>
                <td class="num">{{ rateText(c.不良率) }}</td>
                <td class="num">{{ c.抽检批 ? 1 : 0 }}</td>
                <td class="num">{{ c.合格批 ? 1 : 0 }}</td>
                <td class="num">{{ rateText(c.合格批率) }}</td>
                <td>
                  <span
                    class="smp-badge"
                    :class="judgeBadgeClass(c.判定)"
                    :title="judgeTitle(c.判定)"
                  >
                    {{ c.判定 || "-" }}
                  </span>
                </td>
                <td>{{ c.不良属性 || "-" }}</td>
                <td>{{ c.现象 || "-" }}</td>
                <td>{{ c.不良位置 || "-" }}</td>
                <td>
                  <span
                    v-if="c.是否紧急出货"
                    class="smp-badge"
                    :class="c.是否紧急出货 === '是' ? 'smp-badge-warn' : 'smp-badge-muted'"
                  >{{ c.是否紧急出货 }}</span>
                  <span v-else>-</span>
                </td>
                <td class="num">{{ c.数量 || "-" }}</td>
                <td>{{ c.检验员 }}</td>
                <td>{{ c.登记人 || "-" }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="modal.open" class="smp-overlay">
      <div class="smp-modal smp-modal-wide">
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
                {{ submissionOptionLabel(s) }}
              </option>
            </select>
          </label>
          <div v-else class="smp-fixed-info">
            {{ submissionOptionLabel(selectedSubmission) }}
          </div>

          <div
            v-for="(block, bi) in form.blocks"
            :key="bi"
            class="smp-section smp-inspector-block"
          >
            <p class="smp-section-title">
              <span>抽检与不良 · 第 {{ bi + 1 }} 组</span>
              <span class="smp-block-actions">
                <button
                  v-if="!modal.id && form.blocks.length > 1"
                  type="button"
                  class="smp-link danger"
                  @click="removeBlock(bi)"
                >
                  删除本组
                </button>
              </span>
            </p>
            <div class="smp-grid">
              <div class="smp-field smp-inspector-field full">
                <span>检验员<span class="smp-required">*</span></span>
                <div class="smp-inspector-list">
                  <div
                    v-for="(_name, ii) in block.inspectors"
                    :key="ii"
                    class="smp-inspector-pick"
                  >
                    <ComboField
                      v-model="block.inspectors[ii]"
                      :options="inspectorOptionsFor(block.inspectors[ii], block, ii)"
                      placeholder="选择或输入检验员"
                    />
                    <button
                      v-if="ii === block.inspectors.length - 1"
                      type="button"
                      class="smp-plus-btn"
                      title="本行再加一位检验员"
                      @click="addInspector(bi)"
                    >
                      +
                    </button>
                    <button
                      v-if="block.inspectors.length > 1"
                      type="button"
                      class="smp-link danger"
                      title="移除这位检验员"
                      @click="removeInspector(bi, ii)"
                    >
                      删
                    </button>
                  </div>
                </div>
              </div>
              <label class="smp-field">
                <span>外观抽检数量</span>
                <input v-model="block.外观抽检数量" type="number" min="0" step="any" />
              </label>
              <label class="smp-field">
                <span>机能抽检数量</span>
                <input v-model="block.机能抽检数量" type="number" min="0" step="any" />
              </label>
            </div>

            <div class="smp-defect-head">
              <span>不良明细（归属检验员：{{ formatInspectors(block) || "未填" }}）</span>
              <button type="button" class="smp-link" @click="addDefect(bi)">+ 添加不良</button>
            </div>
            <p v-if="!block.defects.length" class="smp-hint">无不良可不填；判定可选手选（默认正常 OK）</p>
            <div v-for="(d, i) in block.defects" :key="i" class="smp-defect-row">
              <label class="smp-field">
                <span>不良属性</span>
                <select v-model="d.不良属性">
                  <option value="">-</option>
                  <option v-for="o in options.不良属性 || []" :key="o" :value="o">{{ o }}</option>
                </select>
              </label>
              <label class="smp-field">
                <span>不良现象</span>
                <select v-model="d.现象" @change="onPhenomenonChange(d)">
                  <option value="">— 选择大类 —</option>
                  <option
                    v-for="o in phenomenonOptionsFor(d.现象)"
                    :key="o"
                    :value="o"
                  >
                    {{ o }}
                  </option>
                </select>
              </label>
              <label class="smp-field">
                <span>不良位置</span>
                <select v-model="d.不良位置" :disabled="!d.现象">
                  <option value="">— 选择小类 —</option>
                  <option
                    v-for="o in locationOptionsFor(d.现象, d.不良位置)"
                    :key="o"
                    :value="o"
                  >
                    {{ o }}
                  </option>
                </select>
              </label>
              <label class="smp-field">
                <span>数量</span>
                <input v-model="d.数量" type="number" min="0" step="any" />
              </label>
              <button type="button" class="smp-link danger" @click="removeDefect(bi, i)">删除</button>
            </div>
            <div class="smp-chips" style="margin-top: 10px">
              <span>不良数量<strong>{{ blockPreview(block).total }}</strong></span>
              <span>不良率<strong>{{ rateText(blockPreview(block).rate) }}</strong></span>
              <label class="smp-judge-pick">
                判定
                <select v-model="block.判定" :class="judgeSelectClass(block.判定)">
                  <option v-for="o in judgeOptions" :key="o.value" :value="o.value">
                    {{ o.label }}
                  </option>
                </select>
              </label>
            </div>
          </div>

          <button
            v-if="!modal.id"
            type="button"
            class="smp-btn smp-btn-ghost"
            style="margin-bottom: 12px"
            @click="addBlock"
          >
            + 添加一行抽检（另一组数量 / 不良）
          </button>

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
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import ComboField from "./ComboField.vue";
import {
  addInspection,
  deleteInspection,
  downloadCsv,
  flattenInspections,
  inRange,
  loadSampling,
  matchKeyword,
  meName,
  splitDateTime,
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

const defectLookups = computed(() => options.value?.lookups || {});
/** 仅用类别管理代码表大类，避免混入历史「现象」脏值 */
const defectCategories = computed(() => {
  const fromLookup = defectLookups.value.defect_categories || [];
  if (fromLookup.length) return uniqOptions(fromLookup);
  return uniqOptions(options.value.不良现象大类 || []);
});
const minorsByCategory = computed(
  () => defectLookups.value.defect_minors_by_category || {},
);
/**
 * 检验员下拉：类别管理名单 + 权限管理里「检验员」角色用户。
 * 手输姓名只写入本条记录，不回写名单（ComboField 不改 options）。
 */
const inspectorRoster = computed(() => {
  const fromLookup = defectLookups.value.inspectors || [];
  if (fromLookup.length) return uniqOptions(fromLookup);
  return uniqOptions(options.value.检验员 || []);
});

function uniqOptions(list) {
  const out = [];
  const seen = new Set();
  for (const raw of list || []) {
    const s = String(raw ?? "").trim();
    if (!s || seen.has(s)) continue;
    seen.add(s);
    out.push(s);
  }
  return out;
}

function withCurrentOption(list, current) {
  const cur = String(current || "").trim();
  if (!cur) return list;
  if (list.includes(cur)) return list;
  return [cur, ...list];
}

function inspectorOptionsFor(_current, block = null, index = -1) {
  const taken = new Set();
  if (block?.inspectors) {
    block.inspectors.forEach((name, i) => {
      const n = String(name || "").trim();
      if (n && i !== index) taken.add(n);
    });
  }
  // 不把当前手输值塞进 options，避免「临时输入」出现在下拉列表
  return inspectorRoster.value.filter((o) => !taken.has(o));
}

function splitInspectorNames(value) {
  return String(value || "")
    .split(/[;；,，|｜/／\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatInspectors(block) {
  return (block?.inspectors || []).map((s) => String(s || "").trim()).filter(Boolean).join("；");
}

function joinInspectors(block) {
  return formatInspectors(block);
}

function phenomenonOptionsFor(current) {
  return withCurrentOption(defectCategories.value, current);
}

function locationOptionsFor(category, current) {
  const cat = String(category || "").trim();
  const map = minorsByCategory.value;
  let opts = [];
  if (cat && Array.isArray(map[cat])) opts = map[cat];
  else if (!cat && Array.isArray(map[""])) opts = map[""];
  return withCurrentOption(uniqOptions(opts), current);
}

function onPhenomenonChange(d) {
  const allowed = locationOptionsFor(d.现象, "");
  if (d.不良位置 && !allowed.includes(d.不良位置)) d.不良位置 = "";
}

const resultOptions = [
  { key: "", label: "全部" },
  { key: "ok", label: "OK" },
  { key: "ng", label: "NG" },
];
/** 判定四档：中文业务名 → 落库代码 */
const judgeOptions = [
  { value: "OK", label: "正常 · OK" },
  { value: "NG", label: "不良 · NG" },
  { value: "OK2", label: "特采 · OK2" },
  { value: "OK1", label: "免检 · OK1" },
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

function normalizeJudge(judge) {
  const v = String(judge || "").trim().toUpperCase();
  if (v === "OK1" || v === "OK2" || v === "OK") return v;
  if (v.startsWith("NG")) return "NG";
  return "OK";
}

function judgeTitle(judge) {
  const v = normalizeJudge(judge);
  const hit = judgeOptions.find((o) => o.value === v);
  return hit ? hit.label : "";
}

function judgeBadgeClass(judge) {
  const v = normalizeJudge(judge);
  if (v === "NG") return "smp-badge-bad";
  if (v === "OK1") return "smp-badge-ok1";
  if (v === "OK2") return "smp-badge-ok2";
  return "smp-badge-ok";
}

function judgeSelectClass(judge) {
  const v = normalizeJudge(judge);
  if (v === "NG") return "bad";
  if (v === "OK1") return "ok1";
  if (v === "OK2") return "ok2";
  return "ok";
}

function filledDefectCount(block) {
  return (block?.defects || []).filter(
    (d) => d.不良位置 || d.现象 || d.数量 !== "" || d.不良属性,
  ).length;
}

/** 有/无不良时，仅在「正常/不良」之间轻量联动；特采/免检不自动改。 */
function syncJudgeWithDefects(block) {
  const n = filledDefectCount(block);
  const cur = normalizeJudge(block.判定);
  if (n > 0 && cur === "OK") block.判定 = "NG";
  else if (n === 0 && cur === "NG") block.判定 = "OK";
}

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

function exportFiltered() {
  const list = filtered.value;
  if (!list.length) {
    alert("当前筛选没有可导出的抽检记录");
    return;
  }
  if (!filters.value.from && !filters.value.to) {
    const ok = confirm(`未选日期，将导出当前筛选的全部 ${list.length} 条，是否继续？`);
    if (!ok) return;
  }
  exporting.value = true;
  try {
    const headers = [
      "抽检单号", "日期", "时间", "部番", "机种", "送检类型", "事业部", "送检数量",
      "外观抽检数量", "机能抽检数量", "不良数量", "不良率",
      "抽检批", "合格批", "合格批率", "判定",
      "不良属性", "不良现象", "不良位置", "是否紧急出货", "数量", "检验员", "登记人",
    ];
    const data = list.map((c) => {
      const dt = splitDateTime(c.日期);
      return [
        c.抽检单号,
        dt.date,
        dt.time,
        c.部番 || c.机种,
        c.机种,
        c.送检类型,
        c.事业部,
        c.送检数量,
        c.外观抽检数量,
        c.机能抽检数量,
        c.不良数量,
        rateText(c.不良率),
        c.抽检批 ? 1 : 0,
        c.合格批 ? 1 : 0,
        rateText(c.合格批率),
        c.判定,
        c.不良属性,
        c.现象,
        c.不良位置,
        c.是否紧急出货,
        c.数量,
        c.检验员,
        c.登记人,
      ];
    });
    const from = filters.value.from || "all";
    const to = filters.value.to || from;
    downloadCsv(`抽检记录_${from}_${to}.csv`, headers, data);
  } finally {
    exporting.value = false;
  }
}

const filtered = computed(() =>
  rows.value.filter((c) => {
    if (!inRange(c.日期, filters.value.from, filters.value.to)) return false;
    if (filters.value.mine && (c.登记人 || "") !== meName()) return false;
    const ng = isNg(c.判定);
    if (filters.value.result === "ok" && ng) return false;
    if (filters.value.result === "ng" && !ng) return false;
    return matchKeyword(
      filters.value.keyword,
      c.抽检单号,
      c.部番,
      c.机种,
      c.送检类型,
      c.检验员,
      c.现象,
    );
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

/** 送检单下拉/回显：用完整部番，不用缩成机种 */
function submissionOptionLabel(s) {
  if (!s) return "";
  const day = String(s.送检日期 || s.日期 || "").replace("T", " ").slice(0, 16);
  const part = s.部番 || s.机种 || "-";
  const type = s.送检类型 || "-";
  const dept = s.送检单位 || "-";
  const batch = s.同批送检次数 != null && s.同批送检次数 !== "" ? `同批${s.同批送检次数}` : "";
  const qty = s.送检数量 != null && s.送检数量 !== "" ? `数量${s.送检数量}` : "数量-";
  const inspected = (s.抽检 || []).length;
  const tail = inspected ? `已抽检${inspected}人` : "待抽检";
  return [s.送检单号, day, part, type, dept, batch, qty, tail].filter(Boolean).join(" · ");
}

function emptyBlock() {
  return { 外观抽检数量: "", 机能抽检数量: "", inspectors: [""], defects: [], 判定: "OK" };
}

function blankForm() {
  return { sid: "", blocks: [emptyBlock()] };
}

function blockPreview(block) {
  const filled = (block.defects || []).filter(
    (d) => d.不良位置 || d.现象 || d.数量 !== "" || d.不良属性,
  );
  const total = filled.reduce((n, d) => n + (Number(d.数量) || 0), 0);
  const appearance = Number(block.外观抽检数量) || 0;
  return {
    total,
    rate: appearance > 0 ? total / appearance : null,
    judge: normalizeJudge(block.判定),
  };
}

function flash(message) {
  notice.value = message;
  setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 4000);
}

async function load(silent = false) {
  if (!props.workbookId) {
    console.warn("[抽检登记] load 跳过：workbookId 为空", { silent });
    return;
  }
  if (!silent) loading.value = true;
  error.value = "";
  const prevCount = flattenInspections(entries.value).length;
  try {
    const data = await loadSampling(props.workbookId);
    const next = data.entries || [];
    const nextCount = flattenInspections(next).length;
    console.log("[抽检登记] load 完成", {
      silent,
      workbookId: props.workbookId,
      prevInspections: prevCount,
      nextSubmissions: next.length,
      nextInspections: nextCount,
      dept: data.dept ?? "(未返回)",
      keys: data && typeof data === "object" ? Object.keys(data) : [],
    });
    // 防护：若刷新结果异常变空，保留旧数据并告警（避免「保存后瞬间清空」）
    if (prevCount > 0 && nextCount === 0) {
      console.warn("[抽检登记] 刷新结果为空，保留旧列表，请检查 /sampling/entries", data);
      error.value = "刷新结果为空，已保留当前列表；请点「刷新」或查看控制台";
      return;
    }
    entries.value = next;
    options.value = data.options || {};
  } catch (err) {
    console.error("[抽检登记] load 失败", err);
    error.value = err.message;
  } finally {
    if (!silent) loading.value = false;
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
  const names = splitInspectorNames(c.检验员);
  form.value = {
    sid: c.送检单号,
    blocks: [
      {
        外观抽检数量: c.外观抽检数量 ?? "",
        机能抽检数量: c.机能抽检数量 ?? "",
        inspectors: names.length ? names : [""],
        defects: (c.不良组 || []).map((d) => ({ ...d })),
        判定: normalizeJudge(c.判定),
      },
    ],
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

function addBlock() {
  form.value.blocks.push(emptyBlock());
}

function removeBlock(bi) {
  form.value.blocks.splice(bi, 1);
}

function addInspector(bi) {
  form.value.blocks[bi].inspectors.push("");
}

function removeInspector(bi, ii) {
  const list = form.value.blocks[bi].inspectors;
  if (list.length <= 1) return;
  list.splice(ii, 1);
}

function addDefect(bi) {
  const block = form.value.blocks[bi];
  block.defects.push({ 不良属性: "", 不良位置: "", 现象: "", 数量: "" });
  syncJudgeWithDefects(block);
}

function removeDefect(bi, i) {
  const block = form.value.blocks[bi];
  block.defects.splice(i, 1);
  syncJudgeWithDefects(block);
}

function validateBlockInspectors(block, label = "本组") {
  const names = (block.inspectors || []).map((s) => String(s || "").trim());
  if (names.some((n) => !n)) throw new Error(`${label}：请填写检验员`);
  if (new Set(names).size !== names.length) throw new Error(`${label}：检验员不能重复`);
  return names;
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    if (modal.value.id) {
      const block = form.value.blocks[0];
      const names = validateBlockInspectors(block);
      const joined = names.join("；");
      const payload = {
        外观抽检数量: block.外观抽检数量,
        机能抽检数量: block.机能抽检数量,
        检验员: joined,
        判定: normalizeJudge(block.判定),
        defects: block.defects,
      };
      if (modal.value.version != null) payload.expected_version = modal.value.version;
      console.log("[抽检登记] 保存(修改)", { iid: modal.value.id, 判定: payload.判定 });
      const updated = await updateInspection(props.workbookId, modal.value.id, payload);
      // 旧包 bug：曾把 update 响应的 .entries（实际没有）写成 []，导致列表瞬间清空
      if (updated && !Array.isArray(updated.entries)) {
        console.log("[抽检登记] 修改接口未返回 entries（正常），改为重新 load", {
          keys: Object.keys(updated || {}),
        });
      }
      await load(true);
      flash(`已保存：${joined} / ${form.value.sid}`);
    } else {
      if (!form.value.sid) throw new Error("请选择送检单");
      const allNames = [];
      form.value.blocks.forEach((block, i) => {
        const names = validateBlockInspectors(block, `第 ${i + 1} 组`);
        allNames.push(...names);
      });
      if (new Set(allNames).size !== allNames.length) {
        throw new Error("同一送检单下检验员不能重复");
      }
      for (const block of form.value.blocks) {
        console.log("[抽检登记] 保存(新建)", {
          sid: form.value.sid,
          检验员: joinInspectors(block),
          判定: normalizeJudge(block.判定),
        });
        const created = await addInspection(props.workbookId, form.value.sid, {
          外观抽检数量: block.外观抽检数量,
          机能抽检数量: block.机能抽检数量,
          检验员: joinInspectors(block),
          判定: normalizeJudge(block.判定),
          defects: block.defects,
        });
        if (created && !Array.isArray(created.entries)) {
          console.log("[抽检登记] 新建接口未返回 entries（正常），改为重新 load", {
            keys: Object.keys(created || {}),
            inspectionKeys: created.inspection ? Object.keys(created.inspection) : [],
          });
        }
      }
      await load(true);
      flash(`已保存 ${form.value.blocks.length} 组抽检 / ${form.value.sid}`);
    }
    closeModal();
  } catch (err) {
    console.error("[抽检登记] 保存失败", err);
    modal.value.error = err.message;
    if (String(err.message).includes("刷新")) await load();
  } finally {
    saving.value = false;
  }
}

async function remove(c) {
  if (!confirm(`删除 ${c.检验员}（${c.抽检单号}）的抽检记录及其异常处理吗？`)) return;
  try {
    await deleteInspection(props.workbookId, c.抽检单号);
    await load(true);
    flash(`已删除 ${c.抽检单号}`);
  } catch (err) {
    error.value = err.message;
  }
}

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

<style scoped>
.smp-modal-wide {
  width: min(920px, 100%);
}
.smp-inspector-block {
  border-color: #c9d6bc;
  background: #fbfcf8;
}
.smp-block-actions {
  display: flex;
  gap: 8px;
}
.smp-inspector-field.full {
  grid-column: 1 / -1;
}
.smp-inspector-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.smp-inspector-pick {
  display: flex;
  gap: 6px;
  align-items: center;
}
.smp-inspector-pick :deep(.combo-field) {
  flex: 1;
  min-width: 0;
  max-width: 280px;
}
.smp-plus-btn {
  flex: 0 0 34px;
  height: 34px;
  border: 1px solid #c5cfc0;
  border-radius: 8px;
  background: #fff;
  color: #3a6b28;
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
}
.smp-plus-btn:hover {
  background: #eef5e8;
  border-color: #9bb88a;
}
.smp-defect-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12px 0 8px;
  font-size: 12.5px;
  color: #5d645a;
  font-weight: 600;
}
.smp-judge-pick {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.smp-judge-pick select {
  min-width: 132px;
  height: 28px;
  padding: 0 8px;
  border: 1px solid #c5cfc0;
  border-radius: 6px;
  background: #fff;
  font-size: 12.5px;
  font-weight: 600;
  color: #2b3028;
}
.smp-judge-pick select.ok { color: #3a6b28; border-color: #9bb88a; background: #f3f9ef; }
.smp-judge-pick select.ok1 { color: #7a6b00; border-color: #d6c84a; background: #fffce8; }
.smp-judge-pick select.ok2 { color: #8a5a00; border-color: #e0a84a; background: #fff6e8; }
.smp-judge-pick select.bad { color: #b03a2e; border-color: #e0a39c; background: #fdf1ef; }
</style>
