<template>
  <div class="module-home">
    <div class="header">
      <h1>{{ systemInfo.system_name || '管理系统' }}</h1>
      <p class="subtitle">{{ systemInfo.system_subtitle }}</p>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else>
      <div v-if="missingModules.length" class="module-alert module-alert-error">
        <strong>模块配置异常</strong>
        <p>以下模块在配置文件中存在，但数据库中找不到对应项目，因此不会显示：</p>
        <ul>
          <li v-for="mod in missingModules" :key="mod.key || mod.project_id">
            <strong>{{ mod.label }}</strong>
            — 配置的 project_id <code>{{ mod.project_id }}</code> 不存在
          </li>
        </ul>
        <p class="hint">
          请联系管理员：重新导入数据后，请同步更新 <code>product.modules.json</code> 中的 project_id；
          或在项目列表中确认项目是否已创建。
        </p>
      </div>

      <div v-if="fallbackModules.length" class="module-alert module-alert-warn">
        <strong>模块已按名称自动匹配</strong>
        <p>以下模块的 project_id 已失效，系统根据项目名称自动关联（建议管理员更新配置）：</p>
        <ul>
          <li v-for="item in fallbackModules" :key="item.mod.key">
            {{ item.mod.label }} → 项目「{{ item.project.name }}」（{{ item.project.id }}）
          </li>
        </ul>
      </div>

      <div v-if="visibleModules.length === 0" class="empty">
        <p v-if="configuredModules.length === 0">未配置业务模块，请联系管理员。</p>
        <p v-else>暂无可访问的业务模块，请联系管理员分配权限或修复模块配置。</p>
      </div>

      <div v-else class="modules-grid">
        <article class="module-card module-card-monitor" @click="openMonitor">
          <div class="module-icon">📡</div>
          <h2>异常监控大屏</h2>
          <p class="module-desc">KK · 客诉 · 抽检 — 异常结案率、月度趋势、未结案清单</p>
          <div class="module-meta">
            <span class="tag accent">大屏</span>
          </div>
        </article>

        <article
          v-for="mod in visibleModules"
          :key="mod.key || mod.project_id"
          class="module-card"
          @click="openModule(mod)"
        >
          <div class="module-icon">{{ modIcon(mod.key) }}</div>
          <h2>{{ mod.label }}</h2>
          <p class="module-desc">{{ mod.description || mod.project_name }}</p>
          <div class="module-meta">
            <span v-if="mod.user_role" class="tag">{{ roleLabel(mod.user_role) }}</span>
            <span v-if="mod.is_owner" class="tag owner">所有者</span>
            <span v-if="mod.matchType === 'name'" class="tag warn">名称匹配</span>
          </div>
        </article>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authFetch, logout } from './api.js'
import { resolveModuleProject } from './moduleResolve.js'

const router = useRouter()

const emit = defineEmits(['open-project', 'open-monitor'])

const props = defineProps({
  systemInfo: {
    type: Object,
    default: () => ({}),
  },
  isSuperAdmin: {
    type: Boolean,
    default: false,
  },
})

const loading = ref(false)
const error = ref('')
const projects = ref([])

const ICONS = {
  inspection: '🔍',
  complaint: '📋',
  sampling: '📊',
}

const configuredModules = computed(() => props.systemInfo?.modules || [])

const resolvedModules = computed(() => {
  const list = configuredModules.value
  const projectList = projects.value
  return list.map((mod) => {
    const resolved = resolveModuleProject(mod, projectList)
    return { mod, resolved }
  })
})

const visibleModules = computed(() =>
  resolvedModules.value
    .filter((item) => item.resolved?.project)
    .map(({ mod, resolved }) => ({
      ...mod,
      project_id: resolved.project.id,
      project_name: resolved.project.name,
      is_owner: resolved.project.is_owner,
      user_role: resolved.project.user_role,
      matchType: resolved.matchType,
    }))
)

const missingModules = computed(() =>
  props.isSuperAdmin ? resolvedModules.value
    .filter((item) => !item.resolved)
    .map((item) => item.mod) : []
)

const fallbackModules = computed(() =>
  resolvedModules.value.filter((item) => item.resolved?.matchType === 'name')
)

onMounted(async () => {
  await loadProjects()
})

async function loadProjects() {
  loading.value = true
  error.value = ''
  try {
    const res = await authFetch('/api/projects')
    const data = await res.json()
    if (!res.ok) {
      throw new Error(data.detail || '加载失败')
    }
    projects.value = data.projects || []
  } catch (err) {
    error.value = err.message
    if (err.message.includes('登录') || err.message.includes('认证')) {
      setTimeout(() => logout(), 1500)
    }
  } finally {
    loading.value = false
  }
}

function modIcon(key) {
  return ICONS[key] || '📁'
}

function roleLabel(role) {
  const map = { admin: '管理员', entry: '录入', read: '只读' }
  return map[role] || role
}

async function openMonitor() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen?.()
    }
  } catch {
    /* 浏览器可能拒绝自动全屏，仍进入大屏页 */
  }
  emit('open-monitor')
}

function openModule(mod) {
  if (mod.key) {
    router.push(`/m/${mod.key}`)
    return
  }
  emit('open-project', mod.project_id)
}

defineExpose({ loadProjects })
</script>

<style scoped>
.module-home {
  max-width: 1100px;
  margin: 0 auto;
  padding: 48px 20px 64px;
}

.header {
  text-align: center;
  margin-bottom: 40px;
}

.header h1 {
  margin: 0 0 8px;
  font-size: 34px;
  color: var(--primary);
}

.subtitle {
  margin: 0;
  color: var(--muted);
  font-size: 16px;
}

.loading,
.error,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--muted);
}

.error {
  color: var(--danger);
}

.module-alert {
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 24px;
  font-size: 14px;
  line-height: 1.6;
}

.module-alert p {
  margin: 8px 0 0;
}

.module-alert ul {
  margin: 8px 0 0;
  padding-left: 20px;
}

.module-alert code {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.module-alert-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.module-alert-warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.module-alert .hint {
  font-size: 13px;
  opacity: 0.9;
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}

.module-card {
  background: white;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 28px 24px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.module-card:hover {
  transform: translateY(-4px);
  border-color: var(--primary);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.module-icon {
  font-size: 36px;
  margin-bottom: 12px;
}

.module-card h2 {
  margin: 0 0 10px;
  font-size: 22px;
  color: var(--ink);
}

.module-desc {
  margin: 0 0 16px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
  min-height: 44px;
}

.module-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  background: #eef4ff;
  color: var(--primary);
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.tag.owner {
  background: var(--primary);
  color: white;
}

.tag.warn {
  background: #fff7ed;
  color: #c2410c;
}

.module-card-monitor {
  border-color: rgba(124, 58, 237, .35);
  background: linear-gradient(145deg, #faf5ff 0%, #fff 55%);
}

.module-card-monitor:hover {
  border-color: #7c3aed;
  box-shadow: 0 8px 28px rgba(124, 58, 237, .12);
}

.tag.accent {
  background: #ede9fe;
  color: #6d28d9;
}
</style>
