<template>
  <div class="preview-container">
    <div class="preview-header">
      <h2>预览解析结果</h2>
      <div class="actions">
        <button class="btn-secondary" @click="$emit('cancel')">取消</button>
        <button class="btn-primary" @click="confirmSave" :disabled="saving">
          {{ saving ? '保存中...' : '确认并保存为项目' }}
        </button>
      </div>
    </div>

    <div class="preview-content">
      <div class="file-info">
        <h3>{{ filename }}</h3>
        <p class="muted">共 {{ spec.sheets?.length || 0 }} 个工作表</p>
      </div>

      <!-- Module alignment (homepage three tables) -->
      <div v-if="moduleLabel" class="module-align-section">
        <div class="section-header">
          <h3>对齐主页业务表</h3>
          <span class="badge module">{{ moduleLabel }}</span>
        </div>
        <div class="module-align-box">
          <p>
            将按主页「{{ moduleLabel }}」模块的网页结构生成，而不是按 Excel 原始分表逐页镜像。
          </p>
          <ul>
            <li v-if="preferredMainSheet">
              <strong>主表明细：</strong>{{ preferredMainSheet }}
              <span v-if="displayColCount" class="muted"> · 展示 {{ displayColCount }} 列（精选，非整表全列）</span>
            </li>
            <li v-if="smartView?.module_hint">{{ smartView.module_hint }}</li>
            <li>代码/对照表 → 类别管理或下拉选项；汇总/图表 sheet → 趋势分析页</li>
          </ul>
        </div>
      </div>
      <div v-else class="module-align-section generic">
        <div class="section-header">
          <h3>通用看板</h3>
          <span class="badge">未匹配三模块</span>
        </div>
        <p class="muted">
          未识别为产线巡检 / 客诉跟进 / 产品抽检。将生成通用单页看板；多 sheet 时可在「原始分表」中切换。
        </p>
      </div>

      <!-- Smart Integration Recommendations -->
      <div v-if="smartView?.has_recommendations" class="smart-view-section">
        <div class="section-header">
          <h3>💡 智能整合建议</h3>
          <span class="badge">{{ smartView.summary }}</span>
        </div>

        <div class="recommendation-box">
          <p class="intro">系统检测到以下表可整合进主页式一页系统（主表 + 配置下拉）：</p>

          <div class="recommendations">
            <div v-for="(rec, idx) in smartView.recommendations" :key="idx" class="rec-item">
              <div class="rec-header">
                <input
                  type="checkbox"
                  :id="'rec-' + idx"
                  v-model="selectedIntegrations"
                  :value="idx"
                />
                <label :for="'rec-' + idx">
                  <strong>{{ rec.main_sheet }}</strong>
                  <span class="arrow">+</span>
                  <span class="lookup-list">{{ rec.lookup_sheets.join('、') }}</span>
                </label>
              </div>
              <p class="rec-desc">{{ rec.description }}</p>
              <div class="rec-benefit">✓ {{ rec.benefit }}</div>
            </div>
          </div>

          <div class="integration-note">
            <strong>整合后的功能：</strong>
            <ul>
              <li>✓ 一页展示所有相关数据</li>
              <li>✓ 配置表自动转为下拉选项</li>
              <li>✓ 完整的增删改查功能</li>
              <li>✓ 自动关联和联动筛选</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- AI Design Document -->
      <div v-if="dashboardDesign?.design_document" class="ai-design-section">
        <h3>🤖 AI 系统设计方案</h3>
        <p class="muted" v-if="dashboardDesign?.business_understanding?.type">
          业务类型：{{ dashboardDesign.business_understanding.type }}
          · KPI {{ dashboardDesign.kpis?.length || 0 }} 个
          · 图表 {{ dashboardDesign.charts?.length || 0 }} 个
        </p>
        <pre class="design-doc">{{ dashboardDesign.design_document }}</pre>
      </div>

      <div v-if="dashboardDesign?.parse_error" class="error-box">
        AI JSON 配置生成失败（已使用降级方案）：{{ dashboardDesign.parse_error }}
      </div>

      <!-- Sheet Structure -->
      <div class="sheets-structure">
        <h3>表结构分析</h3>

        <div v-if="smartView?.main_sheets?.length" class="sheet-group">
          <h4>📊 主数据表 ({{ smartView.main_sheets.length }})</h4>
          <div class="sheet-grid">
            <div v-for="sheet in smartView.main_sheets" :key="sheet.name" class="sheet-card main">
              <div class="sheet-name">{{ sheet.name }}</div>
              <div class="sheet-stats">{{ sheet.row_count }} 行 · {{ sheet.col_count }} 列</div>
              <div class="sheet-reason">{{ sheet.reason }}</div>
            </div>
          </div>
        </div>

        <div v-if="smartView?.lookup_sheets?.length" class="sheet-group">
          <h4>📋 配置/对照表 ({{ smartView.lookup_sheets.length }})</h4>
          <div class="sheet-grid">
            <div v-for="sheet in smartView.lookup_sheets" :key="sheet.name" class="sheet-card lookup">
              <div class="sheet-name">{{ sheet.name }}</div>
              <div class="sheet-stats">{{ sheet.row_count }} 行</div>
              <div class="sheet-reason">{{ sheet.reason }}</div>
              <div v-if="sheet.referenced_by?.length" class="ref-by">
                被引用: {{ sheet.referenced_by.join('、') }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="smartView?.dashboard_sheets?.length" class="sheet-group">
          <h4>📈 仪表板/说明 ({{ smartView.dashboard_sheets.length }})</h4>
          <div class="sheet-grid">
            <div v-for="sheet in smartView.dashboard_sheets" :key="sheet.name" class="sheet-card dashboard">
              <div class="sheet-name">{{ sheet.name }}</div>
              <div class="sheet-reason">{{ sheet.reason }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- All Sheets List — collapsed when aligned to a homepage module -->
      <details class="all-sheets" :open="!moduleLabel">
        <summary>Excel 原始分表详情 ({{ spec.sheets?.length || 0 }}) — 仅作参考，网页不以分表镜像</summary>
        <div class="sheets-preview">
          <div v-for="sheet in spec.sheets" :key="sheet.name" class="sheet-detail">
            <div class="detail-header">
              <span class="detail-name">{{ sheet.name }}</span>
              <span class="detail-type">{{ kindLabel(sheet.kind) }}</span>
            </div>
            <div class="detail-stats">
              <span>{{ sheet.row_count }} 行</span>
              <span>{{ sheet.col_count }} 列</span>
            </div>
            <div v-if="sheet.note" class="detail-note">{{ sheet.note }}</div>
          </div>
        </div>
      </details>

      <div v-if="error" class="error-box">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { uploadFile } from './api.js'

const props = defineProps({
  spec: Object,
  filename: String,
  file: File,
})

const emit = defineEmits(['cancel', 'saved'])

const saving = ref(false)
const error = ref('')
const selectedIntegrations = ref([])

const smartView = computed(() => props.spec?.smart_view || null)
const dashboardDesign = computed(() => props.spec?.dashboard_design || null)
const moduleKey = computed(
  () => props.spec?.module_key || smartView.value?.module_key || dashboardDesign.value?.module_key || '',
)
const moduleLabel = computed(() => {
  const labels = { inspection: '产线巡检', complaint: '客诉跟进', sampling: '产品抽检' }
  return props.spec?.module_label || smartView.value?.module_label || labels[moduleKey.value] || ''
})
const preferredMainSheet = computed(
  () =>
    smartView.value?.preferred_main_sheet ||
    dashboardDesign.value?.main_table?.sheet ||
    props.spec?.primary_sheet ||
    '',
)
const displayColCount = computed(
  () => (dashboardDesign.value?.main_table?.display_columns || []).length,
)

// Pre-select all recommendations by default
if (smartView.value?.recommendations) {
  selectedIntegrations.value = smartView.value.recommendations.map((_, idx) => idx)
}

async function confirmSave() {
  saving.value = true
  error.value = ''
  
  try {
    // Prepare integration config
    const integrationConfig = {
      enabled: selectedIntegrations.value.length > 0,
      selected: selectedIntegrations.value.map(idx => 
        smartView.value?.recommendations[idx]
      ),
    }
    
    // Create FormData with file and config
    const formData = new FormData()
    formData.append('file', props.file)
    formData.append('integration_config', JSON.stringify(integrationConfig))
    
    // Upload with config
    const token = localStorage.getItem('token')
    const res = await fetch('/api/projects/create', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    })
    
    const data = await res.json()
    
    if (!res.ok) {
      throw new Error(data.detail || '保存失败')
    }
    
    // Include integration config in the result
    data.integration_config = integrationConfig
    
    emit('saved', data)
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

function kindLabel(kind) {
  const map = {
    fact: '明细表',
    dashboard: '看板',
    lookup: '对照表',
    instruction: '说明',
    empty: '空表',
    hidden: '隐藏',
  }
  return map[kind] || kind
}
</script>

<style scoped>
.preview-container {
  max-width: 1200px;
  margin: 40px auto;
  padding: 0 20px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.preview-header h2 {
  margin: 0;
  font-size: 28px;
  color: var(--primary);
}

.actions {
  display: flex;
  gap: 12px;
}

.btn-secondary, .btn-primary {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  border: none;
}

.btn-secondary {
  background: white;
  border: 1px solid var(--line);
  color: var(--ink);
}

.btn-secondary:hover {
  border-color: var(--primary);
}

.btn-primary {
  background: var(--primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.preview-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.module-align-section {
  background: #f0f7f4;
  border: 1px solid #b7d4c8;
  border-radius: 12px;
  padding: 20px 24px;
}

.module-align-section.generic {
  background: #f7f7f5;
  border-color: var(--line);
}

.module-align-box {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink);
}

.module-align-box ul {
  margin: 8px 0 0;
  padding-left: 1.2em;
}

.module-align-box .muted {
  color: var(--muted);
  font-weight: normal;
}

.badge.module {
  background: #1a7a54;
  color: #fff;
}

.file-info {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 24px;
}

.file-info h3 {
  margin: 0 0 8px 0;
  font-size: 20px;
  color: var(--ink);
}

/* Smart View Section */
.smart-view-section {
  background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
  border: 2px solid var(--primary);
  border-radius: 12px;
  padding: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--primary);
}

.badge {
  padding: 4px 12px;
  background: white;
  border-radius: 12px;
  font-size: 13px;
  color: var(--primary);
}

.recommendation-box {
  background: white;
  border-radius: 8px;
  padding: 20px;
}

.intro {
  margin: 0 0 16px 0;
  color: var(--ink);
  font-weight: 500;
}

.recommendations {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.rec-item {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-accent);
}

.rec-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.rec-header input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.rec-header label {
  flex: 1;
  cursor: pointer;
  font-size: 15px;
  color: var(--ink);
}

.arrow {
  color: var(--primary);
  margin: 0 8px;
}

.lookup-list {
  color: var(--primary);
  font-weight: 500;
}

.rec-desc {
  margin: 8px 0 8px 30px;
  color: var(--muted);
  font-size: 14px;
}

.rec-benefit {
  margin-left: 30px;
  color: #16a34a;
  font-size: 13px;
}

.integration-note {
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}

.integration-note strong {
  color: #16a34a;
  display: block;
  margin-bottom: 8px;
}

.integration-note ul {
  margin: 0;
  padding-left: 20px;
  color: #15803d;
}

.integration-note li {
  margin-bottom: 4px;
}

/* Sheet Structure */
.sheets-structure {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 24px;
}

.sheets-structure h3 {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: var(--ink);
}

.sheet-group {
  margin-bottom: 24px;
}

.sheet-group:last-child {
  margin-bottom: 0;
}

.sheet-group h4 {
  margin: 0 0 12px 0;
  font-size: 15px;
  color: var(--ink);
  font-weight: 600;
}

.sheet-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}

.sheet-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
}

.sheet-card.main {
  background: #eff6ff;
  border-color: #3b82f6;
}

.sheet-card.lookup {
  background: #fef3c7;
  border-color: #f59e0b;
}

.sheet-card.dashboard {
  background: #f3e8ff;
  border-color: #a855f7;
}

.sheet-name {
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.sheet-stats, .sheet-reason {
  font-size: 13px;
  color: var(--muted);
  margin-top: 4px;
}

.ref-by {
  font-size: 12px;
  color: var(--primary);
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--line);
}

/* All Sheets Details */
.all-sheets {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 20px;
}

.all-sheets summary {
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.all-sheets summary::-webkit-details-marker {
  display: none;
}

.all-sheets summary::before {
  content: '▶ ';
  display: inline-block;
  margin-right: 8px;
  transition: transform 0.2s;
}

.all-sheets[open] summary::before {
  transform: rotate(90deg);
}

.sheets-preview {
  margin-top: 16px;
  display: grid;
  gap: 12px;
}

.sheet-detail {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-accent);
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.detail-name {
  font-weight: 600;
  color: var(--ink);
}

.detail-type {
  font-size: 12px;
  padding: 2px 8px;
  background: white;
  border-radius: 12px;
  color: var(--muted);
}

.detail-stats {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: var(--muted);
}

.detail-note {
  font-size: 13px;
  color: var(--muted);
  margin-top: 8px;
  line-height: 1.4;
}

.error-box {
  padding: 12px;
  background: #fee;
  border: 1px solid #fcc;
  border-radius: 8px;
  color: #c33;
}

.ai-design-section {
  margin: 24px 0;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: white;
}

.ai-design-section h3 {
  margin: 0 0 8px;
}

.design-doc {
  margin-top: 12px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 480px;
  overflow: auto;
  font-size: 13px;
  line-height: 1.6;
  font-family: inherit;
}

.muted {
  color: var(--muted);
  margin: 0;
}
</style>
