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
      <button class="btn-primary" @click="showCreateUser = true">创建用户</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="users-table">
      <table>
        <thead>
          <tr>
            <th>用户名</th>
            <th>全名</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.username }}</td>
            <td>{{ user.full_name || '-' }}</td>
            <td>{{ user.email || '-' }}</td>
            <td>
              <span class="role-badge" :class="user.role">
                {{ roleLabel(user.role) }}
              </span>
            </td>
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
        <div v-if="editError" class="error">{{ editError }}</div>
        <div class="modal-actions"><button type="button" class="btn-secondary" @click="closeEditUser">取消</button><button type="submit" class="btn-primary" :disabled="editing">{{ editing ? '保存中...' : '保存' }}</button></div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
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
})
const creating = ref(false)
const createError = ref('')
const showEditUser = ref(false)
const editing = ref(false)
const editError = ref('')
const editForm = ref({ id: null, username: '', full_name: '', email: '' })

onMounted(() => {
  loadUsers()
})

async function loadUsers() {
  loading.value = true
  error.value = ''
  
  try {
    // Note: This endpoint doesn't exist yet, we need to add it to backend
    const res = await authFetch('/api/admin/users')
    const data = await readResponse(res)
    
    if (res.ok) {
      users.value = data.users || []
    } else {
      throw new Error(data.detail || '加载失败')
    }
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
  editForm.value = { id: user.id, username: user.username, full_name: user.full_name || '', email: user.email || '' }
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
</style>
