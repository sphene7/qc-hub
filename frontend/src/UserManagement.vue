<template>
  <div class="user-management" :class="{ embedded }">
    <div v-if="!embedded" class="header">
      <h1>用户管理</h1>
      <div class="actions">
        <button class="btn-secondary" @click="$emit('close')">返回</button>
        <button class="btn-primary" @click="showCreateUser = true">创建用户</button>
      </div>
    </div>
    <div v-else class="embedded-toolbar">
      <div class="filter-row">
        <input v-model="q" class="search-input" placeholder="搜索用户名 / 姓名 / 邮箱" @keyup.enter="reload" />
        <select v-model="filterDept" class="dept-filter" @change="reload">
          <option value="">全部部门</option>
          <option v-for="d in deptOptions" :key="d.id" :value="d.id">{{ d.label }}</option>
        </select>
        <button class="btn-secondary" @click="reload">查询</button>
      </div>
      <div class="action-row">
        <template v-if="selectedIds.length">
          <span class="sel-hint">已选 {{ selectedIds.length }} 人</span>
          <select v-model="batchDept" class="dept-filter">
            <option value="">移出部门</option>
            <option v-for="d in deptOptions" :key="d.id" :value="d.id">{{ d.label }}</option>
          </select>
          <button class="btn-secondary" @click="batchAssign">批量分配部门</button>
        </template>
        <button class="btn-primary" @click="showCreateUser = true">创建用户</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="users-table">
      <table>
        <thead>
          <tr>
            <th class="check-col"><input type="checkbox" :checked="allSelected" @change="toggleAll($event.target.checked)" /></th>
            <th>用户名</th>
            <th>全名</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>部门</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td class="check-col"><input type="checkbox" :checked="selectedIds.includes(user.id)" @change="toggleOne(user.id, $event.target.checked)" /></td>
            <td>{{ user.username }}</td>
            <td>{{ user.full_name || '-' }}</td>
            <td>{{ user.email || '-' }}</td>
            <td>
              <span class="role-badge" :class="user.role">
                {{ roleLabel(user.role) }}
              </span>
            </td>
            <td>{{ user.department_name || '-' }}</td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>
              <div class="row-actions">
                <button type="button" class="btn-sm btn-edit" @click="editUser(user)">编辑</button>
                <button type="button" class="btn-sm btn-reset" @click="resetPassword(user)">重置密码</button>
                <button type="button" class="btn-sm btn-danger" @click="deleteUser(user.id)" :disabled="user.role === 'super_admin'">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <span>共 {{ total }} 人</span>
        <button class="page-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span>{{ page }} / {{ pageCount }}</span>
        <button class="page-btn" :disabled="page >= pageCount" @click="goPage(page + 1)">下一页</button>
      </div>
    </div>

    <!-- Create User Dialog -->
    <div v-if="showCreateUser" class="modal-overlay">
      <div class="modal-content">
        <div class="modal-title-row"><h3>创建新用户</h3><button type="button" class="modal-close" aria-label="关闭" @click="showCreateUser = false">×</button></div>
        
        <div class="form-group">
          <label>用户名 *</label>
          <input v-model="newUser.username" placeholder="用户名（唯一）" />
        </div>

        <p class="initial-password-hint">初始密码统一为 <strong>123456</strong>，用户登录后可自行修改。</p>

        <div class="form-group">
          <label>全名</label>
          <input v-model="newUser.full_name" placeholder="全名（可选）" />
        </div>

        <div class="form-group">
          <label>邮箱</label>
          <input type="email" v-model="newUser.email" placeholder="邮箱（可选）" />
        </div>

        <div class="form-group">
          <label>部门 / 课室</label>
          <select v-model="newUser.department_id">
            <option :value="null">未分配</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>

        <div v-if="createError" class="error">{{ createError }}</div>

        <div class="modal-actions">
          <button type="button" class="btn-secondary" @click="showCreateUser = false">取消</button>
          <button type="button" class="btn-primary" @click="createUser" :disabled="creating">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Edit User Dialog -->
    <div v-if="showEditUser" class="modal-overlay">
      <form class="modal-content" @submit.prevent="saveEditUser">
        <div class="modal-title-row"><h3>编辑用户</h3><button type="button" class="modal-close" aria-label="关闭" @click="closeEditUser">×</button></div>
        <div class="form-group"><label>用户名 *</label><input v-model.trim="editForm.username" required maxlength="50" /></div>
        <div class="form-group"><label>显示名称</label><input v-model.trim="editForm.full_name" maxlength="100" /></div>
        <div class="form-group"><label>邮箱</label><input v-model.trim="editForm.email" type="email" maxlength="100" /></div>
        <div class="form-group"><label>部门 / 课室</label>
          <select v-model="editForm.department_id">
            <option :value="null">未分配</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div v-if="editError" class="error">{{ editError }}</div>
        <div class="modal-actions"><button type="button" class="btn-secondary" @click="closeEditUser">取消</button><button type="submit" class="btn-primary" :disabled="editing">{{ editing ? '保存中...' : '保存' }}</button></div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { authFetch } from './api.js'

defineProps({
  embedded: { type: Boolean, default: false },
});

defineEmits(['close'])

const users = ref([])
const loading = ref(false)
const error = ref('')

const showCreateUser = ref(false)
const newUser = ref({
  username: '',
  email: '',
  full_name: '',
  role: 'user',
  department_id: null,
})
const creating = ref(false)
const createError = ref('')
const showEditUser = ref(false)
const editing = ref(false)
const editError = ref('')
const editForm = ref({ id: null, username: '', full_name: '', email: '', department_id: null })
const departments = ref([])
const q = ref('')
const filterDept = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const selectedIds = ref([])
const batchDept = ref('')

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const allSelected = computed(
  () => users.value.length > 0 && users.value.every((u) => selectedIds.value.includes(u.id)),
)
const deptOptions = computed(() => {
  const map = new Map(departments.value.map((d) => [d.id, { ...d, children: [] }]))
  const roots = []
  for (const d of map.values()) {
    if (d.parent_id && map.has(d.parent_id)) map.get(d.parent_id).children.push(d)
    else roots.push(d)
  }
  const sort = (list) => {
    list.sort((a, b) => (a.sort_order - b.sort_order) || a.name.localeCompare(b.name, 'zh-CN'))
    list.forEach((n) => sort(n.children))
  }
  sort(roots)
  const out = []
  const walk = (list, depth) => {
    for (const d of list) {
      out.push({ id: d.id, label: `${'　'.repeat(depth)}${depth ? '└ ' : ''}${d.name}` })
      walk(d.children, depth + 1)
    }
  }
  walk(roots, 0)
  return out
})

function reload() {
  page.value = 1
  loadUsers()
}

function goPage(next) {
  page.value = Math.min(Math.max(1, next), pageCount.value)
  loadUsers()
}

function toggleOne(id, checked) {
  const set = new Set(selectedIds.value)
  if (checked) set.add(id)
  else set.delete(id)
  selectedIds.value = [...set]
}

function toggleAll(checked) {
  selectedIds.value = checked ? users.value.map((u) => u.id) : []
}

async function batchAssign() {
  if (!selectedIds.value.length) return
  const deptName = deptOptions.value.find((d) => d.id === batchDept.value)?.label || '未分配'
  if (!confirm(`把选中的 ${selectedIds.value.length} 名用户调整为「${deptName}」？`)) return
  try {
    const res = await authFetch('/api/admin/users/batch-department', {
      method: 'POST',
      body: JSON.stringify({
        user_ids: selectedIds.value,
        department_id: batchDept.value ? Number(batchDept.value) : null,
      }),
    })
    const data = await readResponse(res)
    if (!res.ok) throw new Error(data.detail || '批量分配失败')
    alert(data.message || '已更新')
    await loadUsers()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(() => {
  loadUsers()
  loadDepartments()
})

async function loadDepartments() {
  try {
    const res = await authFetch('/api/admin/departments')
    if (!res.ok) return
    const data = await readResponse(res)
    departments.value = data.departments || []
  } catch {
    /* 部门接口失败不影响用户列表 */
  }
}

async function loadUsers() {
  loading.value = true
  error.value = ''

  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    if (q.value.trim()) params.set('q', q.value.trim())
    if (filterDept.value) params.set('department_id', String(filterDept.value))
    const res = await authFetch(`/api/admin/users?${params.toString()}`)
    const data = await readResponse(res)

    if (!res.ok) throw new Error(data.detail || '加载失败')
    users.value = data.users || []
    total.value = data.total || 0
    selectedIds.value = []
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function createUser() {
  if (!newUser.value.username) {
    createError.value = '用户名不能为空'
    return
  }

  creating.value = true
  createError.value = ''

  try {
    const res = await authFetch('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify(newUser.value),
    })

    const data = await readResponse(res)
    if (!res.ok) {
      throw new Error(data.detail || '创建失败')
    }

    // Success
    showCreateUser.value = false
    newUser.value = {
      username: '',
      email: '',
      full_name: '',
      department_id: null,
    }
    await loadUsers()
  } catch (err) {
    createError.value = err.message
  } finally {
    creating.value = false
  }
}

async function deleteUser(userId) {
  if (!confirm('确定要删除该用户吗？此操作不可恢复。')) return

  try {
    const res = await authFetch(`/api/admin/users/${userId}`, {
      method: 'DELETE',
    })

    if (!res.ok) {
      const data = await readResponse(res)
      throw new Error(data.detail || '删除失败')
    }

    await loadUsers()
  } catch (err) {
    error.value = err.message
  }
}

async function editUser(user) {
  editForm.value = { id: user.id, username: user.username, full_name: user.full_name || '', email: user.email || '', department_id: user.department_id ?? null }
  editError.value = ''
  showEditUser.value = true
}

function closeEditUser() {
  if (!editing.value) showEditUser.value = false
}

async function saveEditUser() {
  if (!editForm.value.username || editing.value) return
  editing.value = true
  editError.value = ''
  try {
    const { id, ...payload } = editForm.value
    const res = await authFetch(`/api/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
    const data = await readResponse(res)
    if (!res.ok) throw new Error(data.detail || '更新失败')
    showEditUser.value = false
    await loadUsers()
  } catch (err) { editError.value = err.message || '更新失败' }
  finally { editing.value = false }
}

async function resetPassword(user) {
  if (!confirm(`确定将「${user.username}」的密码重置为 123456 吗？`)) return
  try {
    const res = await authFetch(`/api/admin/users/${user.id}/reset-password`, { method: 'POST' })
    const data = await readResponse(res)
    if (!res.ok) throw new Error(data.detail || '重置失败')
    alert(data.message || '密码已重置')
  } catch (err) { error.value = err.message }
}

function roleLabel(role) {
  const map = {
    super_admin: '超级管理员',
    user: '普通用户',
  }
  return map[role] || role
}

function formatDate(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

async function readResponse(res) {
  const text = await res.text()
  if (!text) return {}
  try { return JSON.parse(text) } catch { return { detail: text.slice(0, 300) } }
}
</script>

<style scoped>
.embedded-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.filter-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search-input {
  width: 240px;
  padding: 8px 12px;
  border: 1px solid #dce1d6;
  border-radius: 8px;
  font-size: 13px;
}
.search-input:focus { outline: none; border-color: #9dbb8a; box-shadow: 0 0 0 3px rgba(84, 130, 53, 0.12); }
.dept-filter {
  padding: 7px 10px;
  border: 1px solid #dce1d6;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  min-width: 140px;
}
.action-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sel-hint { font-size: 12.5px; color: #3f6427; background: #eef6ea; padding: 4px 10px; border-radius: 999px; }
.check-col { width: 40px; text-align: center; }
.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 14px;
  border-top: 1px solid #f0f2ee;
  font-size: 12.5px;
  color: #6f756c;
}
.page-btn {
  padding: 4px 10px;
  border: 1px solid #dce1d6;
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
}
.page-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.users-table { background: #fff; border: 1px solid #e6e8e3; border-radius: 12px; overflow: hidden; }

.user-management {
  max-width: 1200px;
  margin: 40px auto;
  padding: 0 20px;
}

.user-management.embedded {
  max-width: none;
  margin: 0;
  padding: 0;
}

.embedded-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.header h1 {
  margin: 0;
  font-size: 32px;
  color: var(--primary);
}

.actions {
  display: flex;
  gap: 12px;
}

.btn-primary, .btn-secondary {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  border: none;
}

.btn-primary {
  background: var(--primary);
  color: white;
}

.btn-secondary {
  background: white;
  border: 1px solid var(--line);
  color: var(--ink);
}

.btn-sm {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid transparent;
  border-radius: 7px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.row-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.btn-edit { background: #f4eafb; border-color: #d9bde9; color: #7a3980; }
.btn-edit:hover { background: #ead8f5; }
.btn-reset { background: #f8f3ff; border-color: #dfccef; color: #70458b; }
.btn-reset:hover { background: #eee1fa; }

.btn-danger {
  background: #fff3f5;
  border-color: #f2b8c2;
  color: #b5334b;
}
.btn-danger:hover:not(:disabled) { background: #ffe4e9; }

.btn-danger:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.loading, .error {
  text-align: center;
  padding: 60px 20px;
  font-size: 16px;
}

.loading {
  color: var(--muted);
}

.error {
  color: var(--danger);
  background: #fee;
  border-radius: 8px;
}

.users-table {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: var(--bg-accent);
}

th {
  padding: 16px;
  text-align: left;
  font-weight: 600;
  color: var(--ink);
  border-bottom: 1px solid var(--line);
}

td {
  padding: 16px;
  border-bottom: 1px solid var(--line);
  color: var(--ink);
}

tbody tr:hover {
  background: var(--bg-accent);
}

tbody tr:last-child td {
  border-bottom: none;
}

.role-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
}

.role-badge.super_admin {
  background: #ff6b6b;
  color: white;
}

.role-badge.user {
  background: var(--bg-accent);
  color: var(--primary);
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 32px;
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin: 0 0 24px 0;
  font-size: 20px;
}

.modal-title-row { display: flex; justify-content: space-between; align-items: flex-start; }
.modal-title-row h3 { margin-bottom: 24px; }
.modal-close { border: 0; background: transparent; color: var(--muted); cursor: pointer; font-size: 26px; line-height: 22px; padding: 0 0 0 16px; }
.modal-close:hover { color: var(--ink); }

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--ink);
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.initial-password-hint { margin: 0 0 20px; padding: 10px 12px; border-radius: 7px; background: #f6effb; color: #70458b; font-size: 14px; }

.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}

/* Ant Design Pro 风格：紧凑表格 + 中性色 */
.users-table table { width: 100%; border-collapse: collapse; font-size: 13px; }
.users-table thead th {
  background: #fafbf8 !important;
  color: #5a6057 !important;
  font-weight: 600 !important;
  font-size: 12.5px;
  padding: 10px 14px !important;
  border-bottom: 1px solid #eef0ec !important;
  text-align: left;
  white-space: nowrap;
}
.users-table tbody td {
  padding: 10px 14px !important;
  border-bottom: 1px solid #f4f6f2 !important;
  font-size: 13px;
  color: #2b3028;
  background: #fff;
}
.users-table tbody tr:hover td { background: #f9fbf7 !important; }
.users-table .role-badge {
  display: inline-block;
  padding: 1px 9px;
  border-radius: 999px;
  font-size: 11.5px;
  background: #eef0ec !important;
  color: #5a6157 !important;
}
.users-table .role-badge.super_admin { background: #e6f4df !important; color: #3a6b28 !important; }
.embedded-toolbar .btn-primary { background: #548235 !important; border-color: #548235 !important; color: #fff !important; }
.embedded-toolbar .btn-secondary { background: #fff !important; border: 1px solid #d6dbcf !important; color: #444 !important; }
.users-table .btn-sm {
  background: #fff !important;
  border: 1px solid #e2e6dd !important;
  color: #4b5247 !important;
  border-radius: 6px;
  padding: 3px 9px !important;
  font-size: 12px !important;
}
.users-table .btn-sm:hover { border-color: #9dbb8a !important; color: #3f6427 !important; }
.users-table .btn-sm.btn-danger { color: #c0392b !important; border-color: #f0d5d0 !important; }
</style>
