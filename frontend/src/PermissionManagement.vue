<template>
  <div class="permission-management">
    <div class="perm-head">
      <div>
        <h2>权限管理</h2>
        <p class="hint">为普通用户分配各业务模块（工作簿）的权限。「送检 / 抽检 / 异常」对应抽检登记的三个页面，「课室」限定送检数据范围（留空=全部）。超级管理员与模块所有者默认拥有全部权限。</p>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else>
      <div class="filter-bar">
        <label>
          <span>按用户筛选</span>
          <select v-model="filterUserId">
            <option value="">全部用户</option>
            <option v-for="u in users" :key="u.id" :value="String(u.id)">
              {{ u.full_name || u.username }}
            </option>
          </select>
        </label>
        <label>
          <span>按模块筛选</span>
          <select v-model="filterProjectId">
            <option value="">全部模块</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </label>
      </div>

      <div class="perm-table-wrap">
        <table class="perm-table">
          <thead>
            <tr>
              <th>用户</th>
              <th>业务模块</th>
              <th>角色</th>
              <th class="crud-col">查看</th>
              <th class="crud-col" title="巡检/客诉等通用录入">增</th>
              <th class="crud-col" title="巡检/客诉等通用修改">改</th>
              <th class="crud-col">删除</th>
              <th class="crud-col" title="能否登记/修改送检单">送检</th>
              <th class="crud-col" title="能否登记/修改抽检记录">抽检</th>
              <th class="crud-col" title="能否填写 OA/责任/对策/结案">异常</th>
              <th class="dept-col" title="送检数据范围：留空=全部，填课室=只看本课室">课室</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredGrants.length === 0">
              <td colspan="12" class="empty">暂无可配置的用户或业务模块</td>
            </tr>
            <tr v-for="row in filteredGrants" :key="row.user_id + '-' + row.project_id">
              <td>
                <strong>{{ row.full_name || row.username }}</strong>
                <span class="sub">{{ row.username }}</span>
              </td>
              <td>{{ row.project_name }}</td>
              <td>
                <select
                  class="preset-select"
                  :value="row.role_id || ''"
                  :disabled="row.is_owner"
                  @change="applyRole(row, $event.target.value)"
                >
                  <option value="">自定义</option>
                  <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
                </select>
              </td>
              <td class="crud-col"><input type="checkbox" :checked="row.permissions.read" :disabled="row.is_owner || !!row.role_id" @change="togglePerm(row, 'read', $event.target.checked)" /></td>
              <td class="crud-col"><input type="checkbox" :checked="row.permissions.create" :disabled="row.is_owner || !!row.role_id" @change="togglePerm(row, 'create', $event.target.checked)" /></td>
              <td class="crud-col"><input type="checkbox" :checked="row.permissions.update" :disabled="row.is_owner || !!row.role_id" @change="togglePerm(row, 'update', $event.target.checked)" /></td>
              <td class="crud-col"><input type="checkbox" :checked="row.permissions.delete" :disabled="row.is_owner || !!row.role_id" @change="togglePerm(row, 'delete', $event.target.checked)" /></td>
              <td class="crud-col"><input type="checkbox" :checked="row.permissions.submit" :disabled="row.is_owner || !!row.role_id" @change="togglePerm(row, 'submit', $event.target.checked)" /></td>
              <td class="crud-col"><input type="checkbox" :checked="row.permissions.inspect" :disabled="row.is_owner || !!row.role_id" @change="togglePerm(row, 'inspect', $event.target.checked)" /></td>
              <td class="crud-col"><input type="checkbox" :checked="row.permissions.handle" :disabled="row.is_owner || !!row.role_id" @change="togglePerm(row, 'handle', $event.target.checked)" /></td>
              <td class="dept-col">
                <select
                  class="dept-select"
                  :value="row.permissions.dept || ''"
                  :disabled="row.is_owner || !row.permissions.submit"
                  @change="setDept(row, $event.target.value)"
                >
                  <option value="">全部</option>
                  <option v-for="d in activeDepartments" :key="d.id" :value="d.name">{{ d.name }}</option>
                </select>
              </td>
              <td><span v-if="row.is_owner" class="owner-label">所有者</span><span v-else class="grant-hint">{{ row.hasGrant ? '已分配' : '未分配' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { authFetch } from "./api.js";

const users = ref([]);
const projects = ref([]);
const grants = ref([]);
const loading = ref(false);
const error = ref("");

const filterUserId = ref("");
const filterProjectId = ref("");


const allRows = computed(() => {
  const existing = new Map(grants.value.map((g) => [`${g.user_id}-${g.project_id}`, g]));
  const rows = [];
  for (const user of users.value) {
    for (const project of projects.value) {
      const key = `${user.id}-${project.id}`;
      const grant = existing.get(key);
      const isOwner = project.owner_id === user.id;
      rows.push(normalizeGrant({
        user_id: user.id,
        username: user.username,
        full_name: user.full_name,
        project_id: project.id,
        project_name: project.name,
        permissions: isOwner ? { create: true, read: true, update: true, delete: true, submit: true, inspect: true, handle: true, dept: '' } : (grant?.permissions || {}),
        is_owner: isOwner,
        hasGrant: !!grant,
      }));
    }
  }
  return rows;
});

const filteredGrants = computed(() => {
  let rows = allRows.value;
  if (filterUserId.value) {
    rows = rows.filter((r) => String(r.user_id) === filterUserId.value);
  }
  if (filterProjectId.value) {
    rows = rows.filter((r) => r.project_id === filterProjectId.value);
  }
  return rows;
});

onMounted(() => {
  loadAll();
  loadDepartments();
  loadRoles();
});

async function loadAll() {
  loading.value = true;
  error.value = "";
  try {
    const res = await authFetch("/api/admin/permissions");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载失败");
    users.value = data.users || [];
    projects.value = data.projects || [];
    grants.value = (data.grants || []).map(normalizeGrant);
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    loading.value = false;
  }
}

function normalizeGrant(g) {
  const p = g.permissions || {};
  return {
    ...g,
    role_id: g.role_id ?? null,
    permissions: {
      read: !!p.read,
      create: !!p.create,
      update: !!p.update,
      delete: !!p.delete,
      submit: p.submit == null ? !!(p.create || p.update) : !!p.submit,
      inspect: p.inspect == null ? !!p.update : !!p.inspect,
      handle: p.handle == null ? !!p.update : !!p.handle,
      dept: p.dept || "",
    },
    preset: detectPreset(p),
  };
}

async function saveGrant(userId, projectId, permissions, roleId = null) {
  const res = await authFetch("/api/admin/permissions", {
    method: "PUT",
    body: JSON.stringify({
      user_id: Number(userId),
      project_id: projectId,
      permissions,
      role_id: roleId,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "保存失败");
}

const departments = ref([]);
const roles = ref([]);

async function loadRoles() {
  try {
    const res = await authFetch("/api/admin/roles");
    if (!res.ok) return;
    const data = await res.json();
    roles.value = data.roles || [];
  } catch {
    /* 角色接口失败不阻塞 */
  }
}
const activeDepartments = computed(() => departments.value.filter((d) => d.active));

async function loadDepartments() {
  try {
    const res = await authFetch("/api/admin/departments");
    if (!res.ok) return;
    const data = await res.json();
    departments.value = data.departments || [];
  } catch {
    /* 部门接口失败不阻塞权限页 */
  }
}

const presetOptions = [
  { key: "custom", label: "自定义" },
  { key: "submitter", label: "送检员" },
  { key: "inspector", label: "检验员" },
  { key: "quality", label: "品质" },
  { key: "supervisor", label: "项目主管" },
  { key: "reader", label: "只读" },
];

const PRESET_PERMS = {
  submitter: { read: true, submit: true },
  inspector: { read: true, inspect: true },
  quality: { read: true, handle: true },
  supervisor: { read: true, submit: true, inspect: true, handle: true, delete: true },
  reader: { read: true },
};

function detectPreset(p) {
  if (!p) return "custom";
  const f = {
    read: !!p.read,
    submit: !!p.submit,
    inspect: !!p.inspect,
    handle: !!p.handle,
    del: !!p.delete,
  };
  if (f.read && f.submit && !f.inspect && !f.handle && !f.del) return "submitter";
  if (f.read && f.inspect && !f.submit && !f.handle && !f.del) return "inspector";
  if (f.read && f.handle && !f.submit && !f.inspect && !f.del) return "quality";
  if (f.read && f.submit && f.inspect && f.handle && f.del) return "supervisor";
  if (f.read && !f.submit && !f.inspect && !f.handle && !f.del) return "reader";
  return "custom";
}

async function applyPreset(row, key) {
  if (key === "custom") return;
  const base = PRESET_PERMS[key];
  const writable = !!(base.submit || base.inspect || base.handle);
  const next = {
    read: !!base.read,
    create: writable,
    update: writable,
    delete: !!base.delete,
    submit: !!base.submit,
    inspect: !!base.inspect,
    handle: !!base.handle,
    dept: key === "submitter" ? row.permissions.dept || "" : "",
  };
  setLocalGrant(row, next);
  try {
    await saveGrant(row.user_id, row.project_id, next);
  } catch (err) {
    error.value = err.message || String(err);
    await loadAll();
  }
}

async function setDept(row, value) {
  const next = { ...row.permissions, dept: String(value || "").trim() };
  setLocalGrant(row, next);
  try {
    await saveGrant(row.user_id, row.project_id, next);
  } catch (err) {
    error.value = err.message || String(err);
    await loadAll();
  }
}

async function togglePerm(row, key, checked) {
  const next = { ...row.permissions, [key]: checked };
  if (key !== "read" && checked) {
    next.read = true;
  } else if (!next.read) {
    next.create = false;
    next.update = false;
    next.delete = false;
    next.submit = false;
    next.inspect = false;
    next.handle = false;
  }
  try {
    if (!next.read && !next.create && !next.update && !next.delete && !next.submit && !next.inspect && !next.handle) {
      const hadGrant = row.hasGrant;
      removeLocalGrant(row);
      if (hadGrant) await deleteGrant(row);
      return;
    }
    // 先写入响应式授权数据，复选框会在当前点击中立即联动更新。
    setLocalGrant(row, next);
    await saveGrant(row.user_id, row.project_id, next);
  } catch (err) {
    error.value = err.message || String(err);
    await loadAll();
  }
}

async function applyRole(row, value) {
  const roleId = value ? Number(value) : null;
  const role = roles.value.find((r) => r.id === roleId);
  const next = role
    ? { ...role.permissions, dept: row.permissions.dept || "" }
    : { ...row.permissions };
  setLocalGrant(row, next, roleId);
  try {
    await saveGrant(row.user_id, row.project_id, next, roleId);
  } catch (err) {
    error.value = err.message || String(err);
    await loadAll();
  }
}

function setLocalGrant(row, permissions, roleId = null) {
  const nextGrant = normalizeGrant({
    user_id: row.user_id,
    username: row.username,
    full_name: row.full_name,
    project_id: row.project_id,
    project_name: row.project_name,
    role_id: roleId,
    permissions,
  });
  const index = grants.value.findIndex((grant) =>
    grant.user_id === row.user_id && grant.project_id === row.project_id,
  );
  grants.value = index >= 0
    ? grants.value.map((grant, i) => (i === index ? nextGrant : grant))
    : [...grants.value, nextGrant];
}

function removeLocalGrant(row) {
  grants.value = grants.value.filter((grant) =>
    grant.user_id !== row.user_id || grant.project_id !== row.project_id,
  );
}

async function deleteGrant(row) {
  const res = await authFetch(
    `/api/admin/permissions?user_id=${row.user_id}&project_id=${encodeURIComponent(row.project_id)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "移除失败");
}
</script>

<style scoped>
.preset-select {
  font-size: 12px;
  padding: 3px 6px;
  border: 1px solid #d6dcd0;
  border-radius: 6px;
  background: #fff;
}
.dept-select {
  width: 120px;
  font-size: 12px;
  padding: 3px 6px;
  border: 1px solid #d6dcd0;
  border-radius: 6px;
}
.dept-select:disabled { background: #f4f5f2; color: #aaa; }
.dept-col { min-width: 120px; }
.perm-table th { white-space: nowrap; }
.perm-table .crud-col { min-width: 46px; text-align: center; }

.permission-management {
  margin: 0;
}

.perm-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.perm-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.hint {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  max-width: 640px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
}

.filter-bar label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}

.filter-bar select {
  min-width: 200px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
}

.perm-table-wrap {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: auto;
}

.perm-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 720px;
}

.perm-table th,
.perm-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.perm-table thead {
  background: var(--bg-accent);
}

.crud-col {
  width: 56px;
  text-align: center !important;
}

.crud-col input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.sub {
  display: block;
  font-size: 12px;
  color: var(--muted);
}

.owner-label { color: var(--muted); font-size: 13px; }

.empty {
  text-align: center;
  color: var(--muted);
  padding: 32px !important;
}

.loading {
  text-align: center;
  padding: 40px;
  color: var(--muted);
}

.error {
  color: var(--danger);
  background: #fee;
  padding: 12px 16px;
  border-radius: 8px;
}

.error.inline {
  margin-top: 8px;
}

.btn-primary,
.btn-secondary {
  padding: 10px 18px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  border: none;
}

.btn-primary {
  background: var(--primary);
  color: #fff;
}

.btn-secondary {
  background: #fff;
  border: 1px solid var(--line);
}

.btn-sm {
  padding: 6px 12px;
  font-size: 13px;
}

.btn-danger {
  background: #dc3545;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #fff;
  padding: 28px;
  border-radius: 12px;
  width: min(480px, 92vw);
}

.modal-content h3 {
  margin: 0 0 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  font-size: 14px;
}

.form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  box-sizing: border-box;
}

.crud-picks {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 16px 0;
  font-size: 14px;
}

.crud-picks label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>
