<template>
  <div class="permission-management">
    <div class="perm-head">
      <div>
        <h2>权限管理</h2>
        <p class="hint">
          在此只给用户<strong>按业务模块分配角色</strong>。具体能看、能改、能送检/抽检/异常，请到
          <strong>角色管理</strong>里配置。抽检模块还可限定「课室」（留空=全部）。
          超级管理员与模块所有者默认全部权限。
        </p>
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
              <th>权限摘要</th>
              <th v-if="showSamplingCols" class="dept-col">课室</th>
              <th>状态</th>
              <th class="ops-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredGrants.length === 0">
              <td :colspan="tableColspan" class="empty">暂无可配置的用户或业务模块</td>
            </tr>
            <tr v-for="row in filteredGrants" :key="row.user_id + '-' + row.project_id">
              <td>
                <strong>{{ row.full_name || row.username }}</strong>
                <span class="sub">{{ row.username }}</span>
              </td>
              <td>
                {{ row.project_name }}
                <span v-if="row.module_key" class="module-tag">{{ moduleLabel(row.module_key) }}</span>
              </td>
              <td>
                <span v-if="row.is_owner" class="owner-label">所有者（全部权限）</span>
                <select
                  v-else
                  class="preset-select"
                  :value="row.role_id || ''"
                  :disabled="savingKey === rowKey(row)"
                  @change="applyRole(row, $event.target.value)"
                >
                  <option value="">未分配</option>
                  <option v-for="r in rolesFor(row)" :key="r.id" :value="r.id">{{ r.name }}</option>
                </select>
              </td>
              <td>
                <template v-if="row.is_owner">
                  <span class="chip">全部</span>
                </template>
                <template v-else-if="row.role_id">
                  <span v-for="chip in permChips(row)" :key="chip" class="chip">{{ chip }}</span>
                  <span v-if="!permChips(row).length" class="muted">仅查看</span>
                </template>
                <span v-else class="muted">—</span>
              </td>
              <td v-if="showSamplingCols" class="dept-col">
                <select
                  v-if="isSampling(row) && row.hasGrant && !row.is_owner"
                  class="dept-select"
                  :value="row.permissions.dept || ''"
                  :disabled="!row.permissions.submit || savingKey === rowKey(row)"
                  @change="setDept(row, $event.target.value)"
                >
                  <option value="">全部</option>
                  <option v-for="d in activeDepartments" :key="d.id" :value="d.name">{{ d.name }}</option>
                </select>
                <span v-else class="muted">—</span>
              </td>
              <td>
                <span v-if="row.is_owner" class="owner-label">所有者</span>
                <span v-else class="grant-hint">{{ row.hasGrant ? "已分配" : "未分配" }}</span>
              </td>
              <td class="ops-col">
                <button
                  v-if="!row.is_owner && row.hasGrant"
                  type="button"
                  class="btn-link danger"
                  :disabled="savingKey === rowKey(row)"
                  @click="clearGrant(row)"
                >
                  取消分配
                </button>
                <span v-else class="muted">—</span>
              </td>
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
const roles = ref([]);
const departments = ref([]);
const loading = ref(false);
const error = ref("");
const savingKey = ref("");

const filterUserId = ref("");
const filterProjectId = ref("");

const MODULE_LABELS = {
  inspection: "产线巡检",
  complaint: "客诉跟进",
  sampling: "产品抽检",
};

const allRows = computed(() => {
  const existing = new Map(grants.value.map((g) => [`${g.user_id}-${g.project_id}`, g]));
  const rows = [];
  for (const user of users.value) {
    for (const project of projects.value) {
      const key = `${user.id}-${project.id}`;
      const grant = existing.get(key);
      const isOwner = project.owner_id === user.id;
      const moduleKey = project.module_key || "";
      rows.push(
        normalizeGrant({
          user_id: user.id,
          username: user.username,
          full_name: user.full_name,
          project_id: project.id,
          project_name: project.name,
          module_key: moduleKey,
          permissions: grant?.permissions || {},
          role_id: grant?.role_id ?? null,
          is_owner: isOwner,
          hasGrant: !!grant,
        }),
      );
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

const showSamplingCols = computed(() =>
  filteredGrants.value.some((r) => r.module_key === "sampling"),
);

const tableColspan = computed(() => (showSamplingCols.value ? 7 : 6));
const activeDepartments = computed(() => departments.value.filter((d) => d.active));

onMounted(() => {
  loadAll();
  loadDepartments();
  loadRoles();
});

function rowKey(row) {
  return `${row.user_id}-${row.project_id}`;
}

function isSampling(row) {
  return row?.module_key === "sampling";
}

function moduleLabel(key) {
  return MODULE_LABELS[key] || key || "";
}

function rolesFor(row) {
  if (isSampling(row)) return roles.value;
  // 巡检/客诉：隐藏「只含送检/抽检/异常」的抽检专用角色
  return roles.value.filter((r) => {
    const p = r.permissions || {};
    const samplingOnly =
      !!(p.submit || p.inspect || p.handle) && !p.create && !p.update && !p.delete;
    return !samplingOnly;
  });
}

function permChips(row) {
  const role = roles.value.find((r) => r.id === row.role_id);
  const p = role?.permissions || row.permissions || {};
  const chips = [];
  if (p.read) chips.push("查看");
  if (p.create || p.update) chips.push("编辑");
  if (p.delete) chips.push("删除");
  if (isSampling(row)) {
    if (p.submit) chips.push("送检");
    if (p.inspect) chips.push("抽检");
    if (p.handle) chips.push("异常");
  }
  return chips;
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
      submit: !!p.submit,
      inspect: !!p.inspect,
      handle: !!p.handle,
      dept: p.dept || "",
    },
  };
}

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

async function loadRoles() {
  try {
    const res = await authFetch("/api/admin/roles");
    if (!res.ok) return;
    const data = await res.json();
    roles.value = data.roles || [];
  } catch {
    /* ignore */
  }
}

async function loadDepartments() {
  try {
    const res = await authFetch("/api/admin/departments");
    if (!res.ok) return;
    const data = await res.json();
    departments.value = data.departments || [];
  } catch {
    /* ignore */
  }
}

async function saveGrant(userId, projectId, permissions, roleId) {
  const res = await authFetch("/api/admin/permissions", {
    method: "PUT",
    body: JSON.stringify({
      user_id: Number(userId),
      project_id: projectId,
      permissions,
      role_id: roleId,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "保存失败");
}

async function deleteGrant(row) {
  const res = await authFetch(
    `/api/admin/permissions?user_id=${row.user_id}&project_id=${encodeURIComponent(row.project_id)}`,
    { method: "DELETE" },
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "移除失败");
}

function setLocalGrant(row, permissions, roleId) {
  const nextGrant = normalizeGrant({
    user_id: row.user_id,
    username: row.username,
    full_name: row.full_name,
    project_id: row.project_id,
    project_name: row.project_name,
    module_key: row.module_key,
    role_id: roleId,
    permissions,
  });
  const index = grants.value.findIndex(
    (grant) => grant.user_id === row.user_id && grant.project_id === row.project_id,
  );
  grants.value =
    index >= 0
      ? grants.value.map((grant, i) => (i === index ? nextGrant : grant))
      : [...grants.value, nextGrant];
}

function removeLocalGrant(row) {
  grants.value = grants.value.filter(
    (grant) => grant.user_id !== row.user_id || grant.project_id !== row.project_id,
  );
}

function sanitizeForModule(row, permissions) {
  const next = { ...permissions };
  if (!isSampling(row)) {
    next.submit = false;
    next.inspect = false;
    next.handle = false;
    next.dept = "";
  }
  return next;
}

async function applyRole(row, value) {
  const roleId = value ? Number(value) : null;
  savingKey.value = rowKey(row);
  error.value = "";

  try {
    if (!roleId) {
      if (row.hasGrant) {
        removeLocalGrant(row);
        await deleteGrant(row);
      }
      return;
    }

    const role = roles.value.find((r) => r.id === roleId);
    if (!role) throw new Error("角色不存在");

    const next = sanitizeForModule(row, {
      ...role.permissions,
      dept: isSampling(row) ? row.permissions.dept || "" : "",
    });
    if (!next.read && !next.create && !next.update && !next.delete && !next.submit && !next.inspect && !next.handle) {
      next.read = true;
    }
    setLocalGrant(row, next, roleId);
    await saveGrant(row.user_id, row.project_id, next, roleId);
  } catch (err) {
    error.value = err.message || String(err);
    await loadAll();
  } finally {
    savingKey.value = "";
  }
}

async function setDept(row, value) {
  if (!row.role_id) return;
  const next = sanitizeForModule(row, {
    ...row.permissions,
    dept: String(value || "").trim(),
  });
  savingKey.value = rowKey(row);
  error.value = "";
  setLocalGrant(row, next, row.role_id);
  try {
    await saveGrant(row.user_id, row.project_id, next, row.role_id);
  } catch (err) {
    error.value = err.message || String(err);
    await loadAll();
  } finally {
    savingKey.value = "";
  }
}

async function clearGrant(row) {
  if (row.is_owner || !row.hasGrant) return;
  if (!confirm(`确定取消「${row.full_name || row.username}」在「${row.project_name}」的角色分配？`)) {
    return;
  }
  savingKey.value = rowKey(row);
  error.value = "";
  const snapshot = grants.value.slice();
  removeLocalGrant(row);
  try {
    await deleteGrant(row);
  } catch (err) {
    grants.value = snapshot;
    error.value = err.message || String(err);
    await loadAll();
  } finally {
    savingKey.value = "";
  }
}
</script>

<style scoped>
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
  max-width: 780px;
  line-height: 1.5;
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
  max-height: calc(100vh - 240px);
}

.perm-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

.perm-table th,
.perm-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: middle;
}

.perm-table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg-accent);
  box-shadow: 0 1px 0 var(--line);
  white-space: nowrap;
}

.preset-select {
  min-width: 140px;
  font-size: 12px;
  padding: 4px 8px;
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

.dept-select:disabled {
  background: #f4f5f2;
  color: #aaa;
}

.dept-col {
  min-width: 120px;
}

.ops-col {
  min-width: 88px;
  white-space: nowrap;
}

.sub {
  display: block;
  font-size: 12px;
  color: var(--muted);
}

.module-tag {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  color: #4a5d4e;
  background: #eef3ea;
  vertical-align: middle;
}

.chip {
  display: inline-block;
  font-size: 11.5px;
  padding: 1px 8px;
  border-radius: 999px;
  background: #eef6ea;
  color: #3a6b28;
  margin-right: 4px;
}

.owner-label,
.muted {
  color: var(--muted);
  font-size: 13px;
}

.grant-hint {
  font-size: 13px;
}

.btn-link {
  border: none;
  background: transparent;
  color: var(--primary, #3d6b4f);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.btn-link.danger {
  color: #b03a2e;
}

.btn-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

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
  margin-bottom: 12px;
}
</style>
