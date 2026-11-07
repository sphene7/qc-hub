<template>
  <div class="role-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="hint">角色定义一次，用户在「权限管理」里按项目套用即可。</span>
      </div>
      <div class="toolbar-right">
        <button class="btn-primary" @click="openCreate">+ 新增角色</button>
        <button class="btn-secondary" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>角色</th>
            <th>说明</th>
            <th>权限</th>
            <th class="num">使用中</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="5" class="empty">加载中…</td></tr>
          <tr v-else-if="!roles.length"><td colspan="5" class="empty">还没有角色</td></tr>
          <template v-else>
            <tr v-for="r in roles" :key="r.id">
              <td><strong>{{ r.name }}</strong><span v-if="r.is_system" class="system-tag">内置</span></td>
              <td class="desc">{{ r.description || '-' }}</td>
              <td>
                <span v-for="chip in summary(r)" :key="chip" class="chip">{{ chip }}</span>
                <span v-if="!summary(r).length" class="muted">无</span>
              </td>
              <td class="num">{{ r.member_count }}</td>
              <td class="ops">
                <button class="link" @click="openEdit(r)">编辑</button>
                <button class="link danger" :disabled="r.member_count > 0" @click="remove(r)">删除</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="modal.open" class="overlay">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ modal.id ? '编辑角色' : '新增角色' }}</h3>
          <button class="close" @click="closeModal">✕</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>角色名称<span class="req">*</span></span>
            <input v-model="form.name" placeholder="如：送检员" />
          </label>
          <label class="field">
            <span>说明</span>
            <input v-model="form.description" placeholder="这个角色能做什么" />
          </label>

          <div class="perm-box">
            <div class="perm-title">权限点</div>
            <label v-for="p in permFields" :key="p.key" class="perm-row">
              <input v-model="form.permissions[p.key]" type="checkbox" />
              <span>{{ p.label }}</span>
              <em>{{ p.desc }}</em>
            </label>
          </div>

          <div v-if="modal.error" class="modal-error">{{ modal.error }}</div>
        </div>
        <div class="modal-foot">
          <button class="btn-secondary" @click="closeModal">取消</button>
          <button class="btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { authFetch } from "./api.js";

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const roles = ref([]);
const modal = ref({ open: false, id: null, error: "" });
const form = ref(blankForm());

const permFields = [
  { key: "read", label: "查看", desc: "看列表与详情" },
  { key: "submit", label: "送检", desc: "新增/修改送检单" },
  { key: "inspect", label: "抽检", desc: "登记抽检与不良" },
  { key: "handle", label: "异常", desc: "OA/责任/对策/结案" },
  { key: "delete", label: "删除", desc: "删除记录" },
  { key: "create", label: "通用新增", desc: "巡检/客诉等模块" },
  { key: "update", label: "通用修改", desc: "巡检/客诉等模块" },
];

function blankForm() {
  return {
    name: "",
    description: "",
    permissions: { read: true, create: false, update: false, delete: false, submit: false, inspect: false, handle: false },
  };
}

function summary(role) {
  const p = role.permissions || {};
  const map = [["submit", "送检"], ["inspect", "抽检"], ["handle", "异常"], ["delete", "删除"]];
  return map.filter(([k]) => p[k]).map(([, label]) => label);
}

async function readJson(res) {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const res = await authFetch("/api/admin/roles");
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "加载角色失败");
    roles.value = data.roles || [];
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function flash(message) {
  notice.value = message;
  setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 4000);
}

function openCreate() {
  form.value = blankForm();
  modal.value = { open: true, id: null, error: "" };
}

function openEdit(role) {
  form.value = {
    name: role.name,
    description: role.description || "",
    permissions: {
      read: true, create: false, update: false, delete: false,
      submit: false, inspect: false, handle: false,
      ...(role.permissions || {}),
    },
  };
  modal.value = { open: true, id: role.id, error: "" };
}

function closeModal() {
  modal.value = { open: false, id: null, error: "" };
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
      permissions: { ...form.value.permissions },
    };
    const url = modal.value.id ? `/api/admin/roles/${modal.value.id}` : "/api/admin/roles";
    const res = await authFetch(url, {
      method: modal.value.id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "保存失败");
    flash(modal.value.id ? "角色已更新" : "角色已新增");
    closeModal();
    await load();
  } catch (err) {
    modal.value.error = err.message;
  } finally {
    saving.value = false;
  }
}

async function remove(role) {
  if (!confirm(`确定删除角色「${role.name}」吗？`)) return;
  try {
    const res = await authFetch(`/api/admin/roles/${role.id}`, { method: "DELETE" });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "删除失败");
    flash("角色已删除");
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

function onKeydown(ev) {
  if (ev.key === "Escape" && modal.value.open) closeModal();
}
onMounted(() => {
  load();
  window.addEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
.role-page { display: flex; flex-direction: column; gap: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.hint { font-size: 12.5px; color: #7f857a; }
.toolbar-right { display: flex; gap: 8px; }
.notice { padding: 8px 12px; border-radius: 8px; background: #eef6ea; color: #3a6b28; font-size: 13px; }
.error { padding: 8px 12px; border-radius: 8px; background: #fdecea; color: #b03a2e; font-size: 13px; }
.table-card { background: #fff; border: 1px solid #e6e8e3; border-radius: 12px; overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 14px; border-bottom: 1px solid #f0f2ee; text-align: left; }
th { background: #fafbf8; color: #5a6057; font-weight: 600; font-size: 12.5px; }
tbody tr:hover td { background: #f9fbf7; }
.desc { color: #6f756c; }
.num { text-align: right; }
.ops { text-align: right; white-space: nowrap; }
.empty { text-align: center; color: #999; padding: 32px; }
.system-tag { margin-left: 6px; font-size: 11px; padding: 1px 6px; border-radius: 6px; background: #eef0ec; color: #777d73; }
.chip { display: inline-block; font-size: 11.5px; padding: 1px 8px; border-radius: 999px; background: #eef6ea; color: #3a6b28; margin-right: 4px; }
.muted { color: #aaa; font-size: 12px; }
.link { background: none; border: none; color: #5a7a3a; cursor: pointer; font-size: 12.5px; padding: 2px 6px; border-radius: 6px; }
.link:hover { background: #eef6ea; }
.link.danger { color: #c0392b; }
.link:disabled { color: #c3c8bf; cursor: not-allowed; background: none; }
.overlay { position: fixed; inset: 0; background: rgba(24, 30, 20, 0.38); display: flex; align-items: center; justify-content: center; z-index: 60; padding: 20px; }
.modal { background: #fff; border-radius: 12px; width: min(520px, 100%); box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22); overflow: hidden; }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid #eef0ec; }
.modal-head h3 { margin: 0; font-size: 16px; }
.close { background: none; border: none; font-size: 16px; color: #999; cursor: pointer; }
.modal-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; max-height: 70vh; overflow: auto; }
.field { display: flex; flex-direction: column; gap: 5px; font-size: 13px; }
.field > span { color: #6f756c; }
.field input:not([type="checkbox"]) { padding: 8px 10px; border: 1px solid #dce1d6; border-radius: 8px; font-size: 13px; }
.req { color: #c0392b; margin-left: 2px; }
.perm-box { border: 1px solid #eef0ec; border-radius: 10px; padding: 10px 12px; }
.perm-title { font-size: 12.5px; color: #6f756c; margin-bottom: 8px; }
.perm-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 13px; cursor: pointer; }
.perm-row em { font-style: normal; color: #9aa096; font-size: 12px; margin-left: auto; }
.modal-error { color: #b03a2e; font-size: 12.5px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid #eef0ec; background: #fbfcfa; }
.btn-primary, .btn-secondary { padding: 6px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #548235; color: #fff; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #fff; border-color: #d6dbcf; color: #444; }
</style>
