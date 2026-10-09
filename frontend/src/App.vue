<template>
  <!-- Login view if not authenticated -->
  <LoginView v-if="!isLoggedIn" :system-info="systemInfo" @login-success="onLoginSuccess" />
  
  <!-- 异常监控大屏：独立全屏，不显示顶栏 -->
  <AbnormalMonitorView
    v-else-if="view === 'monitor'"
    @back="goHome"
  />

  <!-- Main app content -->
  <div v-else class="page" :class="{ 'page-wide': view === 'project' && hasAiDashboard && (projectView === 'dashboard' || projectView === 'analytics' || projectView === 'sampling' || projectView === 'codes') }">
    <!-- 全局上传/分析加载 -->
    <div v-if="uploading" class="global-loading">
      <div class="loading-box">
        <div class="spinner"></div>
        <p class="loading-title">{{ uploadStatus || '处理中...' }}</p>
        <p class="loading-hint">AI 分析约需 30–60 秒，请稍候</p>
      </div>
    </div>

    <header class="top">
      <div>
        <div class="brand" @click="goHome" style="cursor: pointer">{{ systemInfo.system_name || 'ExcelToWeb' }}</div>
        <div class="sub">{{ systemInfo.system_subtitle || '拖入业务表，自动拆公式、认列关系、生成统计页' }}</div>
      </div>
      <div class="header-actions">
        <span class="user-info">{{ currentUser?.full_name || currentUser?.username }}</span>
        <button class="ghost-btn" @click="profileOpen = true">个人资料</button>
        <button class="ghost-btn" @click="changePasswordOpen = true">修改密码</button>
        <button v-if="currentUser?.role === 'super_admin'" class="ghost-btn" @click="goAdmin">管理</button>
        <button class="ghost-btn" @click="handleLogout">登出</button>
      </div>
    </header>

    <p v-if="error && view === 'list'" class="route-error">
      {{ error }}
      <button type="button" class="route-error-dismiss" @click="error = ''">关闭</button>
    </p>

    <!-- Product mode: fixed business modules -->
    <ModuleHome
      v-if="view === 'list' && isProductMode"
      ref="moduleHomeRef"
      :system-info="systemInfo"
      :is-super-admin="currentUser?.role === 'super_admin'"
      @open-project="openProject"
      @open-monitor="goMonitor"
    />

    <!-- Platform mode: project list -->
    <ProjectList
      v-else-if="view === 'list'"
      ref="projectListRef"
      :allow-upload="systemInfo.allow_upload !== false"
      @open-project="openProject"
      @file-selected="handleFileForPreview"
    />

    <!-- Preview Excel View -->
    <PreviewExcel
      v-else-if="view === 'preview'"
      :spec="previewSpec"
      :filename="previewFilename"
      :file="previewFile"
      @cancel="goHome"
      @saved="onProjectCreated"
    />

    <!-- Project Detail View (existing stats/entry) -->
    <main v-else-if="view === 'project' && spec" class="workspace" :class="{ 'workspace-wide': hasAiDashboard && (projectView === 'dashboard' || projectView === 'analytics' || projectView === 'sampling' || projectView === 'codes') }">
      <div class="title-row">
        <h1>{{ spec.title }}</h1>
        <span class="pill">{{ spec.filename }}</span>
        <span v-if="query.entered" class="pill accent">已录入 {{ query.entered }} 条</span>
        
        <!-- Integration Toggle (仅无 AI 看板时显示) -->
        <button 
          v-if="hasIntegrationConfig && !hasAiDashboard" 
          class="ghost-btn"
          @click="toggleIntegration"
        >
          {{ integrationEnabled ? '📑 显示全部表' : '✨ 整合视图' }}
        </button>
        
        <button class="ghost-btn" @click="goHome">{{ isProductMode ? '返回首页' : '返回项目列表' }}</button>
        <button
          v-if="workbookId && showExportMerged"
          class="ghost-btn"
          :disabled="exporting"
          title="导出：问题清单、抽检数据（宽表187列）、趋势图、代码表"
          @click="exportWorkbook"
        >
          {{ exporting ? '导出中…' : '导出合并表' }}
        </button>
      </div>

      <!-- AI 一页系统导航（顺序由系统管理员在「管理→界面管理」配置） -->
      <div v-if="hasAiDashboard" class="mode ai-nav">
        <button
          v-for="item in visibleNavItems"
          :key="item.key"
          :class="{ on: projectView === item.key }"
          @click="switchProjectView(item.key)"
        >{{ item.label }}</button>
      </div>

      <!-- 旧版：无 AI 看板时的统计/录入 -->
      <div v-if="!hasAiDashboard" class="mode">
        <button :class="{ on: mode === 'stats' }" @click="mode = 'stats'">统计</button>
        <button
          :class="{ on: mode === 'entry' }"
          :disabled="!sheet?.form?.enabled"
          @click="mode = 'entry'"
        >
          录入
        </button>
      </div>

      <!-- 原始分表 tabs（AI项目仅在「原始分表」模式显示） -->
      <nav v-if="!hasAiDashboard || projectView === 'sheets'" class="tabs">
        <button
          v-for="tab in getVisibleTabs()"
          :key="tab.name"
          :class="{ on: tab.name === currentName }"
          @click="selectSheet(tab.name)"
        >
          {{ tab.label || tab.name }}
          <em v-if="tab.type === 'integrated'">整合</em>
          <em v-else>{{ kindLabel(tab) }}</em>
        </button>
      </nav>

      <p v-if="sheet?.note && (!hasAiDashboard || projectView === 'sheets')" class="note">{{ sheet.note }}</p>

      <!-- 问题清单：单页表格 + 可收起录入面板 -->
      <SmartDashboard
        v-if="hasAiDashboard && projectView === 'dashboard'"
        ref="smartDashboardRef"
        :workbook-id="workbookId"
        :design="spec.dashboard_design"
        :spec="spec"
        view-mode="operations"
        :can-create="projectPermissions.create"
        :can-update="projectPermissions.update"
        :can-delete="projectPermissions.delete"
        @refresh="refreshDashboard"
      />

      <!-- 趋势分析：客诉专用实时统计 -->
      <ComplaintAnalyticsView
        v-if="hasAiDashboard && projectView === 'analytics' && isComplaintProject"
        ref="complaintAnalyticsRef"
        :workbook-id="workbookId"
        :sheet="spec.dashboard_design?.main_table?.sheet"
      />

      <!-- 趋势分析：产线巡检专用看板 -->
      <InspectionAnalyticsView
        v-else-if="hasAiDashboard && projectView === 'analytics' && isInspectionProject"
        ref="inspectionAnalyticsRef"
        :workbook-id="workbookId"
        :sheet="spec.dashboard_design?.main_table?.sheet"
      />

      <!-- 趋势分析：OQC 变焦抽检批次合格率推移 -->
      <OqcAnalyticsView
        v-else-if="hasAiDashboard && projectView === 'analytics' && isOqcProject"
        :workbook-id="workbookId"
        :sheet="spec.dashboard_design?.main_table?.sheet"
      />

      <!-- 趋势分析：通用 KPI + 图表 -->
      <SmartDashboard
        v-else-if="hasAiDashboard && projectView === 'analytics'"
        :workbook-id="workbookId"
        :design="spec.dashboard_design"
        :spec="spec"
        view-mode="analytics"
        @refresh="refreshDashboard"
      />

      <!-- 抽检数据：宽表 CRUD -->
      <SamplingDataView
        v-if="hasAiDashboard && projectView === 'sampling' && hasSamplingSheet"
        :workbook-id="workbookId"
        :spec="spec"
        :can-create="projectPermissions.create"
        :can-update="projectPermissions.update"
        :can-delete="projectPermissions.delete"
      />

      <!-- 类别管理：分类/类别、模块/负责人可维护，联动问题清单 -->
      <CodeTableView
        v-if="hasAiDashboard && projectView === 'codes' && hasCodeSheet"
        :workbook-id="workbookId"
        :spec="spec"
        :can-edit="canEditCodeTable"
        @updated="onCodeTableUpdated"
      />

      <!-- 无 AI 看板 / 原始分表模式 -->
      <template v-if="!hasAiDashboard || projectView === 'sheets'">
      <!-- Smart Dashboard (legacy fallback) -->
      <SmartDashboard 
        v-if="!hasAiDashboard && spec?.dashboard_design && mode === 'stats'"
        :workbook-id="workbookId"
        :design="spec.dashboard_design"
        :spec="spec"
        @refresh="refresh"
      />

      <!-- Integrated View -->
      <IntegratedView 
        v-else-if="currentTab?.type === 'integrated'"
        :workbook-id="workbookId"
        :main-sheet="sheet"
        :lookup-sheets="getLookupSheetsForIntegration()"
        :field-mappings="currentTab?.recommendation?.field_mappings || []"
        :query-result="query"
        @refresh="refresh"
      />

      <!-- Original sheet views (stats/entry) -->
      <template v-else>
        <EntryForm
          v-if="mode === 'entry' && sheet?.form?.enabled"
          :workbook-id="workbookId"
          :sheet="sheet"
          @saved="onSaved"
        />

      <section v-if="relations.length" class="card">
        <h2>列关系 / 公式</h2>
        <ul class="rels">
          <li v-for="(r, i) in relations" :key="i">
            <strong>{{ r.left }}</strong>
            <span class="arrow">←</span>
            <span>{{ r.right }}</span>
            <code v-if="r.tag">{{ r.tag }}</code>
          </li>
        </ul>
        <div v-if="joins.length" class="joins">
          <div v-for="(j, i) in joins" :key="i" class="join">
            {{ j.from_sheet }} · {{ j.from_field }}
            → {{ j.to_sheet }}（{{ j.via }}）得到
            {{ j.result_field }}
          </div>
        </div>
      </section>

      <section v-if="!sheet?.empty" class="filters card">
        <h2>筛选</h2>
        <div class="filter-grid">
          <label v-for="f in sheet.filters" :key="f.field">
            <span>{{ f.label }}</span>
            <template v-if="f.type === 'date_range'">
              <div class="dates">
                <DateField v-model="dateFrom[f.field]" @change="refresh" />
                <DateField v-model="dateTo[f.field]" @change="refresh" />
              </div>
            </template>
            <select v-else v-model="enums[f.field]" @change="refresh">
              <option value="">全部</option>
              <option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
            </select>
          </label>
        </div>
      </section>

      <section v-if="query.kpis?.length" class="kpis">
        <article v-for="k in query.kpis" :key="k.id" class="kpi">
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-val">{{ formatKpi(k) }}</div>
        </article>
      </section>

      <section class="charts" :class="{ 'chart-theme-screen': chartTheme === 'screen' }">
        <div v-if="(query.charts || []).length" class="generic-chart-toolbar">
          <span>图表展示</span>
          <ChartThemePicker v-model="chartTheme" />
        </div>
        <div v-for="c in query.charts || []" :key="c.id" class="card chart-card">
          <h2>{{ c.title }}</h2>
          <ChartView :option="chartOption(c)" :theme="chartTheme" />
        </div>
      </section>

      <section class="card table-card" v-if="!sheet?.empty">
        <div class="table-head">
          <h2>明细 · {{ query.total ?? 0 }} 行</h2>
          <div class="pager">
            <button :disabled="offset <= 0" @click="page(-1)">上一页</button>
            <span>{{ pageNo }} / {{ pages }}</span>
            <button :disabled="offset + pageSize >= (query.total || 0)" @click="page(1)">下一页</button>
            <label class="page-size">
              每页
              <select v-model.number="pageSize" @change="onPageSizeChange">
                <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
              </select>
              条
            </label>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th v-for="col in visibleCols" :key="col.key">
                  {{ col.label }}
                  <small v-if="col.formula">ƒ</small>
                </th>
                <th>来源</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in query.rows || []" :key="i" :class="{ fresh: row.__source === 'entered' }">
                <td v-for="col in visibleCols" :key="col.key">{{ formatCell(row[col.key], col) }}</td>
                <td>{{ row.__source === 'entered' ? '新录入' : '原表' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      </template> <!-- End of original sheet views -->
      </template> <!-- End of sheets / legacy mode -->
    </main>

    <!-- Project Settings View -->
    <ProjectSettings
      v-else-if="view === 'settings' && settingsReady"
      :project-id="workbookId"
      :project="currentProjectInfo"
      :is-owner="currentProjectInfo?.is_owner"
      :user-role="currentProjectInfo?.user_role"
      @close="router.push(projectPath(workbookId, projectView))"
      @updated="loadProjectInfo"
    />
    <div v-else-if="view === 'settings'" class="loading-placeholder">加载项目设置...</div>

    <!-- Admin: users + interface settings (super admin only) -->
    <AdminView
      v-else-if="view === 'admin'"
      @close="goHome"
      @settings-updated="onAdminSettingsUpdated"
    />

    <ChangePasswordDialog
      :visible="changePasswordOpen"
      @close="changePasswordOpen = false"
    />
    <ProfileDialog :visible="profileOpen" :user="currentUser" @close="profileOpen = false" @updated="onProfileUpdated" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { projectPath } from "./router.js";
import { findModuleByKey, resolveModuleProject } from "./moduleResolve.js";
import ChartView from "./ChartView.vue";
import ChartThemePicker from "./ChartThemePicker.vue";
import EntryForm from "./EntryForm.vue";
import IntegratedView from "./IntegratedView.vue";
import SmartDashboard from "./SmartDashboard.vue";
import ComplaintAnalyticsView from "./ComplaintAnalyticsView.vue";
import InspectionAnalyticsView from "./InspectionAnalyticsView.vue";
import OqcAnalyticsView from "./OqcAnalyticsView.vue";
import AbnormalMonitorView from "./AbnormalMonitorView.vue";
import SamplingDataView from "./SamplingDataView.vue";
import CodeTableView from "./CodeTableView.vue";
import DateField from "./DateField.vue";
import LoginView from "./LoginView.vue";
import ModuleHome from "./ModuleHome.vue";
import ProjectList from "./ProjectList.vue";
import PreviewExcel from "./PreviewExcel.vue";
import ProjectSettings from "./ProjectSettings.vue";
import AdminView from "./AdminView.vue";
import ChangePasswordDialog from "./ChangePasswordDialog.vue";
import ProfileDialog from "./ProfileDialog.vue";
import { authFetch, authDownload, uploadFile, getCurrentUser, isAuthenticated, logout, refreshCurrentUser, saveCurrentUser } from "./api.js";
import {
  buildVisibleNavItems,
  detectProjectModuleKey,
  migrateNavOrders,
} from "./projectNav.js";

const router = useRouter();
const route = useRoute();

// Authentication state
const isLoggedIn = ref(isAuthenticated());
const currentUser = ref(getCurrentUser());
const chartTheme = ref(localStorage.getItem("qc-hub:chart-theme") || "default");
watch(chartTheme, (value) => localStorage.setItem("qc-hub:chart-theme", value));

// System configuration (platform vs product)
const systemInfo = ref({
  mode: 'platform',
  system_name: 'ExcelToWeb',
  system_subtitle: '拖入业务表，自动拆公式、认列关系、生成统计页',
  allow_upload: true,
  allow_register: true,
  show_raw_sheets: true,
  show_export_merged: true,
  project_nav_orders: null,
  modules: [],
});

const isProductMode = computed(() => systemInfo.value.mode === 'product');
const showRawSheets = computed(() => systemInfo.value.show_raw_sheets !== false);
const showExportMerged = computed(() => systemInfo.value.show_export_merged !== false);

// View state: 'list' | 'preview' | 'project' | 'settings' | 'admin' | 'monitor'
const view = ref('list');

// Preview state
const previewSpec = ref(null);
const previewFilename = ref('');
const previewFile = ref(null);

// Project info for settings
const currentProjectInfo = ref(null);
const settingsReady = ref(false);
const uploading = ref(false);
const uploadStatus = ref('');
const exporting = ref(false);

// Integration view toggle
const integrationEnabled = ref(false);

// AI 系统视图: dashboard（问题清单）| sampling（抽检数据）| analytics | sheets
const projectView = ref('dashboard');
const complaintAnalyticsRef = ref(null);
const inspectionAnalyticsRef = ref(null);
const smartDashboardRef = ref(null);
const oqcDashboardNeedsReload = ref(false);
const changePasswordOpen = ref(false);
const profileOpen = ref(false);
const routeSyncing = ref(false);

function onProfileUpdated(user) {
  currentUser.value = saveCurrentUser(user);
}

async function syncSessionUser() {
  if (!isAuthenticated()) return null;
  try {
    const user = await refreshCurrentUser();
    currentUser.value = user;
    return user;
  } catch {
    const cached = getCurrentUser();
    currentUser.value = cached;
    return cached;
  }
}

function onAppVisible() {
  if (document.visibilityState === "visible" && isLoggedIn.value) {
    syncSessionUser();
  }
}

// Project list ref
const projectListRef = ref(null);
const moduleHomeRef = ref(null);

const hasAiDashboard = computed(() => {
  const d = spec.value?.dashboard_design;
  if (!d) return false;
  if (d.business_understanding?.type === '解析失败') return false;
  return Boolean(d.main_table || d.kpis?.length || d.charts?.length);
});

const hasAnalyticsView = computed(() => {
  const d = spec.value?.dashboard_design;
  return (
    Boolean(d?.kpis?.length || d?.charts?.length) ||
    isComplaintProject.value ||
    isInspectionProject.value ||
    isOqcProject.value
  );
});

const isComplaintProject = computed(() => {
  const title = spec.value?.title || spec.value?.filename || '';
  const sheet = spec.value?.dashboard_design?.main_table?.sheet || '';
  return title.includes('客诉') || sheet.includes('客诉');
});

const isInspectionProject = computed(() => {
  const title = spec.value?.title || spec.value?.filename || '';
  const entity = spec.value?.dashboard_design?.business_understanding?.main_entity || '';
  const type = spec.value?.dashboard_design?.business_understanding?.type || '';
  if (title.includes('客诉')) return false;
  return (
    title.includes('巡检') ||
    entity.includes('巡检') ||
    type.includes('巡检')
  );
});

const isOqcProject = computed(() => {
  const title = spec.value?.title || spec.value?.filename || '';
  const sheet = spec.value?.dashboard_design?.main_table?.sheet || '';
  const entity = spec.value?.dashboard_design?.business_understanding?.main_entity || '';
  return (
    title.includes('抽检') ||
    title.includes('OQC') ||
    sheet.includes('OQC') ||
    sheet.includes('抽检批次') ||
    entity.includes('OQC') ||
    entity.includes('抽检批次')
  );
});

const dashboardNavLabel = computed(() => {
  if (isOqcProject.value) return '抽检明细';
  if (isComplaintProject.value) return '客诉明细';
  return '问题清单';
});

const hasSamplingSheet = computed(() => {
  const sheets = spec.value?.sheets || [];
  return sheets.some((s) => {
    const n = (s.name || "").trim();
    return n === "抽检数据" || (n.startsWith("抽检数据") && !n.includes("展开"));
  });
});

const hasCodeSheet = computed(() => {
  const sheets = spec.value?.sheets || [];
  return sheets.some((s) => {
    const n = (s.name || "").trim();
    if (n !== "代码" && !n.includes("代码表")) return false;
    const keys = new Set((s.columns || []).map((c) => c.key));
    if (keys.has("代码") && keys.has("不良描述")) return true;
    return s.kind === "lookup" || !(s.empty ?? true);
  });
});

const projectModuleKey = computed(() =>
  detectProjectModuleKey({
    isInspection: isInspectionProject.value,
    isComplaint: isComplaintProject.value,
    isOqc: isOqcProject.value,
  }),
);

const currentNavOrder = computed(() => {
  const orders = migrateNavOrders(systemInfo.value);
  return orders[projectModuleKey.value];
});

const visibleNavItems = computed(() =>
  buildVisibleNavItems(projectModuleKey.value, currentNavOrder.value, {
    dashboard: { key: "dashboard", label: dashboardNavLabel.value, show: hasAiDashboard.value },
    sampling: { key: "sampling", label: "抽检数据", show: hasSamplingSheet.value },
    analytics: { key: "analytics", label: "趋势分析", show: hasAnalyticsView.value },
    codes: { key: "codes", label: "类别管理", show: hasCodeSheet.value },
    sheets: { key: "sheets", label: "原始分表", show: showRawSheets.value },
  }),
);

const mainTableSheet = computed(() => {
  if (!spec.value?.sheets) return null;
  const target = spec.value.dashboard_design?.main_table?.sheet?.trim();
  const findSheet = (n) => {
    if (!n) return null;
    return spec.value.sheets.find((s) => s.name === n || s.name.trim() === n) || null;
  };
  const byName = findSheet(target);
  if (byName) return byName;
  return spec.value.sheets.find((s) => s.form?.enabled && (s.kind === 'fact' || s.kind === 'table')) || null;
});

const projectPermissions = computed(() => {
  const info = currentProjectInfo.value;
  if (!info) {
    return { create: false, read: false, update: false, delete: false };
  }
  if (info.is_owner || info.permissions == null) {
    return { create: true, read: true, update: true, delete: true };
  }
  const p = info.permissions || {};
  return {
    create: !!p.create,
    read: !!p.read,
    update: !!p.update,
    delete: !!p.delete,
  };
});

const canEditCodeTable = computed(() => {
  const p = projectPermissions.value;
  return p.create || p.update || p.delete;
});

const hasIntegrationConfig = computed(() => {
  return spec.value?.smart_view?.has_recommendations || false;
});

function toggleIntegration() {
  integrationEnabled.value = !integrationEnabled.value;
  
  // When toggling, select first visible tab
  const visible = getVisibleTabs();
  if (visible.length > 0) {
    selectSheet(visible[0].name);
  }
}

function onLoginSuccess(user) {
  currentUser.value = saveCurrentUser(user);
  isLoggedIn.value = true;
  const redirect =
    route.query.redirect ||
    (route.path !== "/" ? route.fullPath : "/");
  router.replace(typeof redirect === "string" ? redirect : "/").then(() => syncFromRoute());
}

function handleLogout() {
  logout();
}

async function exportWorkbook() {
  if (!workbookId.value || exporting.value) return;
  exporting.value = true;
  try {
    const title = spec.value?.title || 'export';
    await authDownload(
      `/api/workbooks/${workbookId.value}/export?mode=merged`,
      `${title}-合并.xlsx`,
      { timeout: 120000 },
    );
  } catch (err) {
    alert(err.message || '导出失败');
  } finally {
    exporting.value = false;
  }
}

function exitBrowserFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen?.().catch(() => {});
  }
}

function leaveMonitorView() {
  document.body.classList.remove("monitor-fullscreen");
  document.documentElement.style.removeProperty("background");
}

function goHome() {
  exitBrowserFullscreen();
  leaveMonitorView();
  spec.value = null;
  workbookId.value = '';
  previewSpec.value = null;
  previewFile.value = null;
  router.push("/");
}

function goMonitor() {
  router.push("/monitor");
}

function goAdmin() {
  router.push("/admin");
}

function applyLegacyEntryPanelHint(wid, layout) {
  if (!wid || !layout) return;
  try {
    if (layout === "table") localStorage.setItem(`qc-entry-panel:${wid}`, "0");
    else if (layout === "workbench") localStorage.setItem(`qc-entry-panel:${wid}`, "1");
  } catch (_) {
    /* ignore */
  }
}

async function loadSystemInfo() {
  try {
    console.log('[App] loadSystemInfo → /api/system/info')
    const res = await fetch('/api/system/info');
    if (res.ok) {
      systemInfo.value = await res.json();
      console.log('[App] systemInfo', systemInfo.value.mode, systemInfo.value.system_name)
    } else {
      console.warn('[App] system/info HTTP', res.status)
    }
  } catch (err) {
    console.warn('[App] Failed to load system info:', err);
  }
}

async function onAdminSettingsUpdated() {
  await loadSystemInfo();
  if (!showRawSheets.value && projectView.value === 'sheets' && workbookId.value) {
    switchProjectView('dashboard');
  }
}

async function loadProject(wid) {
  const res = await authFetch(`/api/workbooks/${wid}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "加载项目失败");
  }
  workbookId.value = wid;
  spec.value = data.spec;
  if (data.spec.sheets?.[0]?.name && !currentName.value) {
    currentName.value = data.spec.sheets[0].name;
  }
  if (data.spec.smart_view?.has_recommendations && !hasAiDashboard.value) {
    integrationEnabled.value = true;
  }
  await loadProjectInfo();
  return data;
}

async function syncFromRoute() {
  if (!isLoggedIn.value) return;

  routeSyncing.value = true;
  try {
    const name = route.name;

    if (name === "module") {
      const mod = findModuleByKey(systemInfo.value.modules, route.params.key);
      if (!mod) {
        error.value = `未找到模块「${route.params.key}」的配置`;
        view.value = "list";
        return;
      }
      const res = await authFetch("/api/projects");
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "加载项目列表失败");
      }
      const resolved = resolveModuleProject(mod, data.projects || []);
      if (!resolved) {
        error.value = `模块「${mod.label}」未绑定有效项目（配置的 project_id: ${mod.project_id}）`;
        view.value = "list";
        return;
      }
      await router.replace(projectPath(resolved.project.id, "dashboard"));
      return;
    }

    if (name === "monitor") {
      view.value = "monitor";
      return;
    }

    if (name === "home" || route.path === "/") {
      view.value = "list";
      await nextTick();
      moduleHomeRef.value?.loadProjects();
      projectListRef.value?.loadProjects();
      return;
    }

    if (name === "admin") {
      view.value = "admin";
      return;
    }

    if (name === "preview") {
      view.value = "preview";
      return;
    }

    if (name === "project-settings") {
      const wid = route.params.wid;
      view.value = "settings";
      settingsReady.value = false;
      if (wid !== workbookId.value || !spec.value) {
        await loadProject(wid);
      } else {
        workbookId.value = wid;
        await loadProjectInfo();
      }
      if (!currentProjectInfo.value && spec.value) {
        currentProjectInfo.value = {
          name: spec.value.title || spec.value.filename || "项目",
          created_at: null,
          is_owner: true,
        };
      }
      settingsReady.value = true;
      return;
    }

    if (
      route.params.wid &&
      (name === "project-view" || name === "project-layout" || name === "project-settings")
    ) {
      const wid = route.params.wid;
      const tab = route.params.tab || "dashboard";
      const layout = route.params.layout || "workbench";

      view.value = "project";
      if (tab === "dashboard" && route.name === "project-layout" && layout) {
        applyLegacyEntryPanelHint(wid, layout);
      }
      if (tab === "sheets" && !showRawSheets.value) {
        await router.replace(projectPath(wid, "dashboard"));
        projectView.value = "dashboard";
      } else {
        projectView.value = tab;
        if (tab === "dashboard" && layout && route.name === "project-layout") {
          await router.replace(projectPath(wid, "dashboard"));
        }
      }

      if (wid !== workbookId.value || !spec.value) {
        await loadProject(wid);
      }

      if (!hasAiDashboard.value && tab === "dashboard") {
        const visibleTabs = getVisibleTabs();
        if (visibleTabs.length > 0 && !currentName.value) {
          selectSheet(visibleTabs[0].name);
        }
      }
    }
  } catch (err) {
    error.value = err.message;
    view.value = "list";
  } finally {
    if (route.name === "monitor") {
      document.body.classList.add("monitor-fullscreen");
    } else {
      leaveMonitorView();
    }
    routeSyncing.value = false;
  }
}

watch(
  () => route.fullPath,
  () => {
    syncFromRoute();
  }
);

watch(
  () => projectView.value,
  (tab) => {
    if (tab === "dashboard") {
      if (oqcDashboardNeedsReload.value) {
        smartDashboardRef.value?.reloadMainTable?.();
        oqcDashboardNeedsReload.value = false;
      } else {
        smartDashboardRef.value?.refreshLookups?.();
      }
    }
  },
);

onMounted(async () => {
  await loadSystemInfo();
  if (isAuthenticated()) {
    isLoggedIn.value = true;
    await syncSessionUser();
    await syncFromRoute();
  }
  document.addEventListener("visibilitychange", onAppVisible);
});

onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", onAppVisible);
});

async function handleFileForPreview(file) {
  loading.value = true;
  uploading.value = true;
  uploadStatus.value = '正在上传并解析 Excel...';
  error.value = '';
  
  try {
    uploadStatus.value = '正在调用 AI 分析业务逻辑（约 30–60 秒）...';
    const res = await uploadFile('/api/upload/preview', file);
    const data = await res.json();
    
    if (!res.ok) {
      throw new Error(data.detail || '解析失败');
    }
    
    previewSpec.value = data.spec;
    previewFilename.value = data.filename || file.name;
    previewFile.value = file;
    router.push("/preview");
  } catch (err) {
    error.value = err.message;
    alert(err.message);
  } finally {
    loading.value = false;
    uploading.value = false;
    uploadStatus.value = '';
  }
}

function onProjectCreated(data) {
  workbookId.value = data.id;
  spec.value = data.spec;
  projectView.value = 'dashboard';
  integrationEnabled.value = false;

  if (data.spec.sheets?.[0]?.name) {
    currentName.value = data.spec.sheets[0].name;
  }

  if (data.spec.smart_view?.has_recommendations && !hasAiDashboard.value) {
    integrationEnabled.value = true;
  }

  router.push(projectPath(data.id, "dashboard"));

  if (!hasAiDashboard.value) {
    const visibleTabs = getVisibleTabs();
    if (visibleTabs.length > 0) {
      selectSheet(visibleTabs[0].name);
    }
  }
}

// Get tabs to display (including integrated tabs when enabled)
function getVisibleTabs() {
  if (!spec.value?.sheets) return [];
  
  const tabs = [];
  const smartView = spec.value.smart_view;
  
  // Add integrated tabs first (AI 项目不使用整合 tab，避免原始分表混乱)
  if (integrationEnabled.value && smartView?.has_recommendations && !hasAiDashboard.value) {
    for (const rec of smartView.recommendations || []) {
      if (rec.type === 'integrate' && rec.main_sheet) {
        tabs.push({
          name: `${rec.main_sheet}·整合`,
          type: 'integrated',
          mainSheet: rec.main_sheet,
          label: `${rec.main_sheet}·整合`,
          kind: 'integrated',
          recommendation: rec,
        });
      }
    }
  }
  
  // Add all original sheets
  tabs.push(...spec.value.sheets.map(s => ({
    ...s,
    type: 'original',
  })));
  
  return tabs;
}

// Get the current tab object (might be integrated or original sheet)
const currentTab = computed(() => {
  const tabs = getVisibleTabs();
  return tabs.find(t => t.name === currentName.value);
});

// Get the actual sheet object for current selection
const sheet = computed(() => {
  if (!spec.value?.sheets) return null;

  const tab = currentTab.value;
  if (tab?.type === 'integrated') {
    return spec.value.sheets.find((s) => s.name === tab.mainSheet) || null;
  }
  if (currentName.value) {
    return spec.value.sheets.find((s) => s.name === currentName.value) || null;
  }
  return spec.value.sheets[0] || null;
});

async function openProject(projectId) {
  try {
    router.push(projectPath(projectId, "dashboard"));
  } catch (err) {
    error.value = err.message;
  }
}

async function loadProjectInfo() {
  if (!workbookId.value) return;
  try {
    const res = await authFetch(`/api/projects`);
    const data = await res.json();
    if (res.ok) {
      const project = data.projects.find(p => p.id === workbookId.value);
      currentProjectInfo.value = project || null;
    }
  } catch (err) {
    console.error('Failed to load project info:', err);
  }
}

const spec = shallowRef(null);
const currentName = ref("");
const query = shallowRef({});
const lookupData = ref({}); // Store lookup table data: { sheetName: { data: [...] } }
const loading = ref(false);
const error = ref("");
const enums = ref({});
const dateFrom = ref({});
const dateTo = ref({});
const offset = ref(0);
const pageSize = ref(50);
const pageSizeOptions = [20, 50, 100, 200, 500];
const workbookId = ref("");
const mode = ref("stats");

const visibleCols = computed(() =>
  (sheet.value?.columns || []).filter((c) => c.role !== "empty" && c.fill > 0)
);
const joins = computed(() => spec.value?.joins || []);
const relations = computed(() => {
  const cols = sheet.value?.formula?.columns || [];
  return cols
    .filter((c) => c.depends_on?.length || c.kind)
    .slice(0, 12)
    .map((c) => ({
      left: c.name,
      right: c.expr || c.depends_on.join("、") || c.sample,
      tag: (c.functions || [])[0] || c.kind,
    }));
});
const pageNo = computed(() => Math.floor(offset.value / pageSize.value) + 1);
const pages = computed(() => Math.max(1, Math.ceil((query.value.total || 0) / pageSize.value)));

// Remove old upload/sample functions as they're replaced by preview workflow

function kindLabel(s) {
  const map = {
    fact: "明细",
    table: "表",
    dashboard: "看板",
    lookup: "对照",
    instruction: "说明",
    empty: "空",
    hidden: "隐藏",
  };
  return map[s.kind] || s.kind;
}

function applyWorkbook(data) {
  workbookId.value = data.id;
  spec.value = data.spec;
  currentName.value = data.spec.primary_sheet || data.spec.sheets[0]?.name;
  enums.value = {};
  dateFrom.value = {};
  dateTo.value = {};
  offset.value = 0;
  mode.value = "stats";
  refresh();
}

function selectSheet(name) {
  currentName.value = name;
  enums.value = {};
  dateFrom.value = {};
  dateTo.value = {};
  offset.value = 0;
  
  // For integrated tabs, always show stats mode
  const tabs = getVisibleTabs();
  const selectedTab = tabs.find(t => t.name === name);
  if (selectedTab?.type === 'integrated') {
    mode.value = "stats";
  } else {
    const s = spec.value?.sheets.find((x) => x.name === name);
    if (!s?.form?.enabled) mode.value = "stats";
  }
  
  refresh();
}

function onSaved(data) {
  if (data.form && sheet.value) {
    sheet.value.form = data.form;
    if (data.filters) sheet.value.filters = data.filters;
    sheet.value.row_count = data.row_count;
  }
  const total = data.row_count || 0;
  offset.value = Math.max(0, Math.floor((total - 1) / pageSize.value) * pageSize.value);
  refresh();
}

function onPageSizeChange() {
  offset.value = 0;
  refresh();
}

function switchProjectView(v) {
  if (!workbookId.value) return;
  if (v === 'sheets' && !showRawSheets.value) {
    v = 'dashboard';
  }
  if (v === 'analytics' && !hasAnalyticsView.value) {
    router.push(projectPath(workbookId.value, "dashboard"));
    return;
  }
  if (v === 'dashboard') {
    router.push(projectPath(workbookId.value, "dashboard"));
  } else {
    router.push(projectPath(workbookId.value, v));
  }
  if (v === 'sheets') {
    integrationEnabled.value = false;
    mode.value = 'stats';
    const sheets = spec.value?.sheets || [];
    if (sheets.length > 0) {
      selectSheet(sheets[0].name);
    }
  }
}

async function openSettings() {
  if (!workbookId.value) return;
  router.push(projectPath(workbookId.value, "settings"));
}

function refreshDashboard(data) {
  if (data?.form && mainTableSheet.value) {
    mainTableSheet.value.form = data.form;
    if (data.filters) mainTableSheet.value.filters = data.filters;
    mainTableSheet.value.row_count = data.row_count;
  }
  complaintAnalyticsRef.value?.refresh?.();
  inspectionAnalyticsRef.value?.refresh?.();
  smartDashboardRef.value?.refreshLookups?.();
}

function onCodeTableUpdated(data) {
  const sync = data?.sync || {};
  if (mainTableSheet.value?.form) {
    const form = mainTableSheet.value.form;
    if (!form.lookups) form.lookups = {};
    if (data?.category_options?.length) {
      form.lookups.category_options = data.category_options;
    }
    if (data?.classification_categories) {
      form.lookups.classification_categories = data.classification_categories;
    }
    if (data?.module_owners) form.lookups.module_owners = data.module_owners;
    if (data?.owner_modules) form.lookups.owner_modules = data.owner_modules;
    if (data?.layout === "oqc") {
      const lk = data.lookups || {};
      form.lookups = {
        ...form.lookups,
        ...lk,
        series_sections: data.series_sections || lk.series_sections,
        series_confirmers: data.series_confirmers || lk.series_confirmers,
        section_heads: lk.section_heads || {},
        defect_phenomena: data.defect_phenomena || lk.defect_phenomena,
        defect_category_by_code:
          data.defect_category_by_code || lk.defect_category_by_code || lk.defect_categories || {},
      };
    }
  }
  if (sync.form || sync.filters) {
    refreshDashboard({
      form: sync.form,
      filters: sync.filters,
    });
  } else if (data?.category_options?.length) {
    smartDashboardRef.value?.refreshLookups?.();
  } else if (data?.layout === "oqc" && mainTableSheet.value) {
    refreshDashboard({
      form: sync.form || mainTableSheet.value.form,
      filters: sync.filters || mainTableSheet.value.filters,
    });
  }
  if (data?.layout === "oqc" && sync.synced) {
    oqcDashboardNeedsReload.value = true;
    if (projectView.value === "dashboard") {
      smartDashboardRef.value?.reloadMainTable?.();
      oqcDashboardNeedsReload.value = false;
    }
  }
  smartDashboardRef.value?.refreshLookups?.();
}

function filterPayload() {
  const out = {};
  for (const [k, v] of Object.entries(enums.value)) {
    if (v) out[k] = [v];
  }
  for (const f of sheet.value?.filters || []) {
    if (f.type === "date_range") {
      const start = dateFrom.value[f.field];
      const end = dateTo.value[f.field];
      if (start || end) out[f.field] = { type: "date_range", start, end };
    }
  }
  return out;
}

async function refresh() {
  if (!workbookId.value || !currentName.value) return;
  
  const tab = currentTab.value;
  if (!tab) return;
  
  // For integrated tabs, query the main sheet
  const sheetToQuery = tab.type === 'integrated' ? tab.mainSheet : currentName.value;
  
  const res = await authFetch(`/api/workbooks/${workbookId.value}/query`, {
    method: "POST",
    body: JSON.stringify({
      sheet: sheetToQuery,
      filters: filterPayload(),
      offset: offset.value,
      limit: pageSize.value,
    }),
  });
  query.value = await res.json();
  
  // If it's an integrated tab, also load lookup table data
  if (tab.type === 'integrated' && tab.recommendation?.lookup_sheets) {
    await loadLookupTables(tab.recommendation.lookup_sheets);
  }
}

async function loadLookupTables(lookupSheetNames) {
  if (!workbookId.value || !lookupSheetNames?.length) return;
  
  for (const sheetName of lookupSheetNames) {
    try {
      const res = await authFetch(`/api/workbooks/${workbookId.value}/query`, {
        method: "POST",
        body: JSON.stringify({
          sheet: sheetName,
          filters: {},
          offset: 0,
          limit: 1000, // Load all lookup data
        }),
      });
      const data = await res.json();
      lookupData.value[sheetName] = {
        name: sheetName,
        data: data.rows || [],
      };
    } catch (err) {
      console.error(`Failed to load lookup table ${sheetName}:`, err);
    }
  }
}

function getLookupSheetsForIntegration() {
  const tab = currentTab.value;
  if (!tab || tab.type !== 'integrated') return [];
  
  const lookupSheetNames = tab.recommendation?.lookup_sheets || [];
  return lookupSheetNames.map(name => lookupData.value[name]).filter(Boolean);
}

function page(dir) {
  offset.value = Math.max(0, offset.value + dir * pageSize.value);
  refresh();
}

function formatKpi(k) {
  const v = k.computed;
  if (v == null || Number.isNaN(v)) return "—";
  if (k.format === "percent") {
    const p = Math.abs(v) <= 1 ? v * 100 : v;
    return p.toFixed(1) + "%";
  }
  if (k.format === "int" || Number.isInteger(v)) return Number(v).toLocaleString();
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatCell(v, col) {
  if (v == null || v === "") return "";
  if (col?.type === "percent" && typeof v === "number") {
    const p = Math.abs(v) <= 1 ? v * 100 : v;
    return p.toFixed(1) + "%";
  }
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return String(v);
}

function chartOption(c) {
  const palette = ["#7c5cbf", "#9b6fd4", "#2d8a62", "#b45309", "#6b4aa8"];
  const labels = c.labels || [];
  const values = c.values || [];
  if (c.type === "pie") {
    return {
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          radius: ["38%", "68%"],
          data: labels.map((n, i) => ({ name: n, value: values[i] })),
          label: { fontSize: 11 },
        },
      ],
      color: palette,
    };
  }
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 16, top: 24, bottom: 48 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { rotate: labels.some((x) => String(x).length > 6) ? 30 : 0, fontSize: 11 },
    },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#e6edf3" } } },
    series: [
      {
        type: c.type === "line" ? "line" : "bar",
        data: values,
        smooth: true,
        barMaxWidth: 28,
        itemStyle: { color: palette[0], borderRadius: [4, 4, 0, 0] },
        areaStyle: c.type === "line" ? { color: "rgba(22,85,122,0.12)" } : undefined,
      },
    ],
  };
}
</script>

<style scoped>
.page { max-width: 1280px; margin: 0 auto; padding: 24px 20px 64px; }
.page-wide {
  max-width: none;
  padding: 8px 10px 24px;
}
.workspace-wide {
  margin-top: 8px;
}
.workspace-wide .title-row {
  margin-bottom: 0;
}
.workspace-wide .title-row h1 {
  font-size: 20px;
}
.workspace-wide .mode.ai-nav {
  margin: 8px 0 4px;
}
.top { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.user-info { font-size: 14px; color: var(--primary); font-weight: 500; }
.brand { font-size: 22px; font-weight: 700; letter-spacing: 0.04em; color: var(--primary); }
.sub { color: var(--muted); margin-top: 4px; font-size: 13px; }
.pill.accent { background: var(--primary-light); color: var(--primary-2); }
.ghost-btn {
  border: 1px solid var(--line); background: #fff; border-radius: 8px; padding: 8px 12px; color: var(--primary);
  text-decoration: none; display: inline-flex; align-items: center;
}
.mode { display: flex; gap: 8px; margin: 14px 0 0; }
.mode button {
  border: 0; background: #fff; border-radius: 10px; padding: 8px 16px; box-shadow: var(--shadow);
}
.mode button.on { background: var(--primary); color: #fff; }
.mode button:disabled { opacity: 0.4; }
.ai-nav button.on { background: var(--primary); color: #fff; }
.sub-nav {
  margin-top: 8px;
  padding-left: 4px;
  gap: 6px;
}
.sub-nav button {
  font-size: 13px;
  padding: 7px 16px;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}
.sub-nav button.on {
  font-size: 16px;
  font-weight: 700;
  padding: 11px 28px;
  background: var(--primary);
  color: #fff;
  box-shadow: var(--shadow);
  border-color: var(--primary);
}
.design-doc-panel { margin-top: 16px; }
.design-doc-panel h2 { margin: 0 0 8px; }
.design-meta { color: var(--muted); margin: 0 0 12px; font-size: 14px; }
.design-doc {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 70vh;
  overflow: auto;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}
.fresh { background: #f0faf4; }
.hero { margin-top: 48px; }
.drop {
  display: block; border: 1.5px dashed #9bb4c6; background: rgba(255,255,255,0.8);
  border-radius: 16px; padding: 72px 24px; text-align: center; cursor: pointer;
}
.drop.over, .drop:hover { border-color: var(--primary); background: #fff; }
.drop-title { font-size: 22px; font-weight: 650; }
.drop-hint { color: var(--muted); margin-top: 8px; }
.samples { margin-top: 28px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.samples-label { width: 100%; color: var(--muted); font-size: 13px; }
.sample {
  background: #fff; border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; color: var(--ink);
}
.sample:hover { border-color: var(--primary); color: var(--primary); }
.error { color: var(--danger); margin-top: 16px; }
.route-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
}
.route-error-dismiss {
  border: 0;
  background: transparent;
  color: #991b1b;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}
.muted { color: var(--muted); }
.workspace { margin-top: 28px; }
.title-row { display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; }
h1 { font-size: 26px; margin: 0; }
h2 { font-size: 14px; margin: 0 0 12px; color: var(--muted); font-weight: 650; }
.pill { font-size: 12px; color: var(--muted); background: var(--bg-accent); padding: 3px 8px; border-radius: 999px; }
.tabs { display: flex; gap: 8px; overflow: auto; margin: 18px 0 12px; padding-bottom: 4px; }
.tabs button {
  border: 0; background: #fff; border-radius: 10px; padding: 8px 12px; white-space: nowrap;
  box-shadow: var(--shadow);
}
.tabs button.on { background: var(--primary); color: #fff; }
.tabs em { font-style: normal; opacity: 0.7; margin-left: 6px; font-size: 12px; }
.generic-chart-toolbar { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin: 0 0 12px; color: var(--muted); font-size: 14px; }
.note {
  background: #fff7ed; color: #9a3412; padding: 10px 12px; border-radius: 8px; font-size: 13px;
}
.card {
  background: var(--card); border-radius: 14px; padding: 16px 18px; margin-top: 14px;
  box-shadow: var(--shadow);
}
.rels { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.rels li { font-size: 13px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.arrow { color: var(--accent); }
code { background: var(--bg-accent); padding: 1px 6px; border-radius: 6px; font-size: 11px; }
.joins { margin-top: 10px; display: grid; gap: 6px; }
.join { font-size: 12px; color: var(--muted); }
.filter-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.filter-grid label { display: grid; gap: 6px; font-size: 12px; color: var(--muted); }
select, input[type="date"] {
  border: 1px solid var(--line); border-radius: 8px; padding: 7px 8px; background: #fff; color: var(--ink);
}
.dates { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin-top: 14px; }
.kpi { background: #fff; border-radius: 14px; padding: 14px; box-shadow: var(--shadow); }
.kpi-label { color: var(--muted); font-size: 12px; }
.kpi-val { font-size: 24px; font-weight: 700; margin-top: 4px; color: var(--primary); }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
.chart-card { min-height: 280px; }
.table-head { display: flex; justify-content: space-between; align-items: center; }
.pager { display: flex; gap: 8px; align-items: center; font-size: 13px; }
.pager button { border: 1px solid var(--line); background: #fff; border-radius: 8px; padding: 4px 8px; }
.pager button:disabled { opacity: 0.45; }
.page-size {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}
.page-size select {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 3px 6px;
  background: #fff;
}
.table-wrap { overflow: auto; max-height: 480px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { border-bottom: 1px solid var(--line); padding: 7px 8px; text-align: left; white-space: nowrap; max-width: 240px; overflow: hidden; text-overflow: ellipsis; }
th { position: sticky; top: 0; background: var(--bg-accent); color: var(--muted); font-weight: 650; }
th small { color: var(--accent); margin-left: 4px; }
</style>
