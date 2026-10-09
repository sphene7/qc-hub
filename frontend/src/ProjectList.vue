<template>
  <div class="project-list">
    <div class="header">
      <h1>我的项目</h1>
      <label v-if="allowUpload" class="btn-primary">
        <input type="file" accept=".xlsx,.xlsm,.xls" hidden @change="onFileSelect" />
        上传新表
      </label>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    
    <div v-else-if="projects.length === 0" class="empty">
      <p>{{ allowUpload ? '还没有项目，上传一份Excel表开始吧' : '暂无可访问的项目' }}</p>
    </div>

    <div v-else class="projects-grid">
      <div
        v-for="project in projects"
        :key="project.id"
        class="project-card"
      >
        <div class="project-content" @click="$emit('open-project', project.id)">
          <div class="project-name">{{ project.name }}</div>
          <div class="project-meta">
            <span class="tag" v-if="project.is_owner">所有者</span>
            <span class="date">{{ formatDate(project.created_at) }}</span>
          </div>
          <div class="project-desc">{{ project.description }}</div>
        </div>
        <div v-if="project.is_owner" class="project-actions">
          <button class="btn-delete" @click.stop="deleteProject(project.id)" title="删除项目">
            🗑️
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { authFetch, logout } from './api.js'

const emit = defineEmits(['open-project', 'file-selected'])

defineProps({
  allowUpload: {
    type: Boolean,
    default: true,
  },
})

const projects = ref([])
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  await loadProjects()
})

async function loadProjects() {
  loading.value = true
  error.value = ''
  console.log('[ProjectList] loadProjects start')
  try {
    const res = await authFetch('/api/projects')
    const data = await res.json()
    if (res.ok) {
      projects.value = data.projects || []
      console.log('[ProjectList] loaded', projects.value.length, 'projects')
    } else {
      throw new Error(data.detail || '加载失败')
    }
  } catch (err) {
    error.value = err.message
    console.error('[ProjectList] loadProjects failed', err)
    if (err.message.includes('登录') || err.message.includes('认证')) {
      // 令牌失效：退回登录页
      setTimeout(() => logout(), 1500)
    }
  } finally {
    loading.value = false
  }
}

async function deleteProject(projectId) {
  if (!confirm('确定要删除这个项目吗？此操作不可恢复。')) {
    return
  }
  
  try {
    const res = await authFetch(`/api/projects/${projectId}`, {
      method: 'DELETE'
    })
    
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || '删除失败')
    }
    
    // Reload projects list
    await loadProjects()
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

function onFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) {
    emit('file-selected', file)
  }
  e.target.value = ''
}

function formatDate(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

defineExpose({ loadProjects })
</script>

<style scoped>
.project-list {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.header h1 {
  font-size: 32px;
  margin: 0;
  color: var(--primary);
}

.btn-primary {
  background: var(--primary);
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s;
}

.btn-primary:hover {
  transform: translateY(-2px);
}

.loading, .error, .empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--muted);
  font-size: 16px;
}

.error {
  color: var(--danger);
}

.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.project-card {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.project-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.project-content {
  flex: 1;
}

.project-actions {
  display: flex;
  gap: 8px;
}

.btn-delete {
  background: transparent;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  opacity: 0.6;
  transition: all 0.2s;
}

.btn-delete:hover {
  opacity: 1;
  background: #fee;
}

.project-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
}

.project-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
}

.tag {
  background: var(--primary);
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.date {
  color: var(--muted);
}

.project-desc {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
