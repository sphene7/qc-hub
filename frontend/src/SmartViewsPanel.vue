<template>
  <div class="smart-views-panel">
    <div class="panel-header">
      <h3>💡 智能整合建议</h3>
      <button class="btn-close" @click="$emit('close')">×</button>
    </div>

    <div v-if="loading" class="loading">分析中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    
    <div v-else-if="smartViews && smartViews.has_recommendations" class="content">
      <div class="analysis-summary">
        <h4>表结构分析</h4>
        <div class="stats">
          <div class="stat-item">
            <span class="stat-value">{{ smartViews.analysis.main_sheets }}</span>
            <span class="stat-label">主数据表</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ smartViews.analysis.lookup_sheets }}</span>
            <span class="stat-label">配置表</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ smartViews.analysis.dashboard_sheets }}</span>
            <span class="stat-label">看板</span>
          </div>
        </div>
      </div>

      <div class="recommendations">
        <h4>整合方案</h4>
        <div
          v-for="(rec, i) in smartViews.recommendations"
          :key="i"
          class="recommendation-card"
          :class="rec.priority"
        >
          <div class="rec-header">
            <span class="rec-title">{{ rec.title }}</span>
            <span class="rec-priority">{{ priorityLabel(rec.priority) }}</span>
          </div>
          <p class="rec-desc">{{ rec.description }}</p>
          
          <div v-if="rec.embed_lookups && rec.embed_lookups.length > 0" class="rec-detail">
            <strong>自动关联:</strong>
            <div class="tags">
              <span v-for="lookup in rec.embed_lookups" :key="lookup" class="tag">
                {{ lookup }}
              </span>
            </div>
          </div>

          <button class="btn-apply" @click="applyRecommendation(rec)">
            应用此方案
          </button>
        </div>
      </div>

      <details class="details-section">
        <summary>查看详细分析</summary>
        
        <div class="detail-tables">
          <div v-if="smartViews.details.main.length > 0" class="detail-group">
            <h5>主数据表</h5>
            <ul>
              <li v-for="sheet in smartViews.details.main" :key="sheet.name">
                <strong>{{ sheet.name }}</strong> - {{ sheet.reason }}
              </li>
            </ul>
          </div>

          <div v-if="smartViews.details.lookup.length > 0" class="detail-group">
            <h5>配置/对照表</h5>
            <ul>
              <li v-for="sheet in smartViews.details.lookup" :key="sheet.name">
                <strong>{{ sheet.name }}</strong> - {{ sheet.reason }}
                <span v-if="sheet.referenced_by && sheet.referenced_by.length > 0" class="muted">
                  (被引用: {{ sheet.referenced_by.join(', ') }})
                </span>
              </li>
            </ul>
          </div>

          <div v-if="smartViews.details.utility.length > 0" class="detail-group">
            <h5>可隐藏的表</h5>
            <ul>
              <li v-for="sheet in smartViews.details.utility" :key="sheet.name">
                <strong>{{ sheet.name }}</strong> - {{ sheet.reason }}
              </li>
            </ul>
          </div>
        </div>
      </details>
    </div>

    <div v-else class="no-recommendations">
      <p>暂无整合建议</p>
      <p class="muted">当前工作簿的表结构较为简单，不需要特别整合</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { authFetch } from './api.js'

const props = defineProps({
  workbookId: String,
})

const emit = defineEmits(['close', 'apply'])

const smartViews = ref(null)
const loading = ref(false)
const error = ref('')

onMounted(() => {
  loadSmartViews()
})

async function loadSmartViews() {
  loading.value = true
  error.value = ''
  
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/smart-views`)
    const data = await res.json()
    
    if (res.ok) {
      smartViews.value = data.smart_views
    } else {
      throw new Error(data.detail || '加载失败')
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function applyRecommendation(rec) {
  emit('apply', rec)
  emit('close')
}

function priorityLabel(priority) {
  const map = {
    high: '推荐',
    medium: '可选',
    low: '备选',
  }
  return map[priority] || priority
}
</script>

<style scoped>
.smart-views-panel {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 480px;
  background: white;
  box-shadow: -4px 0 12px rgba(0,0,0,0.1);
  z-index: 100;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  background: white;
  z-index: 10;
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 28px;
  color: var(--muted);
  cursor: pointer;
  line-height: 1;
  padding: 0;
  width: 32px;
  height: 32px;
}

.btn-close:hover {
  color: var(--ink);
}

.content {
  padding: 20px;
}

.loading, .error, .no-recommendations {
  text-align: center;
  padding: 60px 20px;
  color: var(--muted);
}

.error {
  color: var(--danger);
}

.analysis-summary {
  margin-bottom: 24px;
  padding: 16px;
  background: var(--bg-accent);
  border-radius: 8px;
}

.analysis-summary h4 {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: var(--muted);
}

.stats {
  display: flex;
  gap: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--primary);
}

.stat-label {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
}

.recommendations h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
}

.recommendation-card {
  border: 2px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  transition: all 0.2s;
}

.recommendation-card.high {
  border-color: #4caf50;
  background: #f1f8f4;
}

.recommendation-card.medium {
  border-color: #2196f3;
}

.recommendation-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.rec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.rec-title {
  font-weight: 600;
  color: var(--ink);
}

.rec-priority {
  background: #4caf50;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.recommendation-card.medium .rec-priority {
  background: #2196f3;
}

.rec-desc {
  margin: 0 0 12px 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.5;
}

.rec-detail {
  margin-bottom: 12px;
  font-size: 13px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.tag {
  background: white;
  border: 1px solid var(--line);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  color: var(--ink);
}

.btn-apply {
  width: 100%;
  padding: 10px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.btn-apply:hover {
  opacity: 0.9;
}

.details-section {
  margin-top: 24px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}

.details-section summary {
  cursor: pointer;
  font-weight: 500;
  color: var(--primary);
  padding: 8px 0;
}

.detail-tables {
  margin-top: 16px;
}

.detail-group {
  margin-bottom: 20px;
}

.detail-group h5 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--muted);
}

.detail-group ul {
  margin: 0;
  padding-left: 20px;
}

.detail-group li {
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.6;
}

.muted {
  color: var(--muted);
  font-size: 12px;
}
</style>
