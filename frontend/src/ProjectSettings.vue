<template>
  <section class="project-settings">
    <header class="header">
      <div>
        <h1>项目设置</h1>
        <p class="subtitle">{{ project?.name || "当前项目" }}：管理项目成员与访问权限</p>
      </div>
      <button type="button" class="btn-secondary" @click="$emit('close')">返回项目</button>
    </header>

    <div v-if="!canManage" class="notice">
      你当前没有管理项目成员的权限。
    </div>

    <template v-else>
      <form class="add-member" @submit.prevent="addMember">
        <label>
          用户名
          <input v-model.trim="newMember.username" required placeholder="输入已有用户名" :disabled="saving" />
        </label>
        <label>
          项目角色
          <select v-model="newMember.role" :disabled="saving">
            <option value="read">只读</option>
            <option value="entry">录入</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        <button type="submit" class="btn-primary" :disabled="saving">
          {{ saving ? "保存中..." : "添加成员" }}
        </button>
      </form>

      <p v-if="message" class="message">{{ message }}</p>
      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="loading" class="loading">加载成员中...</div>
      <div v-else class="members-card">
        <h2>项目成员</h2>
        <p v-if="members.length === 0" class="empty">暂未添加其他成员。</p>
        <table v-else>
          <thead>
            <tr><th>用户</th><th>角色</th><th>加入时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="member in members" :key="member.user_id">
              <td>
                <strong>{{ member.full_name || member.username }}</strong>
                <small v-if="member.full_name">{{ member.username }}</small>
              </td>
              <td>{{ roleLabel(member.role) }}</td>
              <td>{{ formatDate(member.joined_at) }}</td>
              <td><button type="button" class="btn-danger" :disabled="saving" @click="removeMember(member)">移除</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { authFetch } from "./api.js";

const props = defineProps({
  projectId: { type: String, required: true },
  project: { type: Object, default: null },
  isOwner: { type: Boolean, default: false },
  userRole: { type: String, default: "" },
});
const emit = defineEmits(["close", "updated"]);

const members = ref([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const message = ref("");
const newMember = ref({ username: "", role: "read" });
const canManage = computed(() => props.isOwner || props.project?.can_manage_members || props.userRole === "admin");

watch(() => props.projectId, loadMembers);
onMounted(loadMembers);

async function loadMembers() {
  if (!props.projectId || !canManage.value) return;
  loading.value = true;
  error.value = "";
  try {
    const res = await authFetch(`/api/projects/${props.projectId}/members`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载成员失败");
    members.value = data.members || [];
  } catch (err) {
    error.value = err.message || "加载成员失败";
  } finally {
    loading.value = false;
  }
}

async function addMember() {
  if (!newMember.value.username || saving.value) return;
  saving.value = true;
  error.value = "";
  message.value = "";
  try {
    const res = await authFetch(`/api/projects/${props.projectId}/members`, {
      method: "POST",
      body: JSON.stringify(newMember.value),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "添加成员失败");
    newMember.value = { username: "", role: "read" };
    message.value = data.message || "成员已添加";
    await loadMembers();
    emit("updated");
  } catch (err) {
    error.value = err.message || "添加成员失败";
  } finally {
    saving.value = false;
  }
}

async function removeMember(member) {
  if (!confirm(`确定移除成员「${member.username}」吗？`) || saving.value) return;
  saving.value = true;
  error.value = "";
  message.value = "";
  try {
    const res = await authFetch(`/api/projects/${props.projectId}/members/${member.user_id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "移除成员失败");
    message.value = data.message || "成员已移除";
    await loadMembers();
    emit("updated");
  } catch (err) {
    error.value = err.message || "移除成员失败";
  } finally {
    saving.value = false;
  }
}

function roleLabel(role) {
  return { admin: "管理员", entry: "录入", read: "只读" }[role] || role;
}

function formatDate(value) {
  return value ? new Date(value).toLocaleDateString("zh-CN") : "-";
}
</script>

<style scoped>
.project-settings { max-width: 1000px; margin: 40px auto; padding: 0 20px 40px; }
.header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 24px; }
h1, h2 { color: var(--primary); margin: 0; }
h1 { font-size: 32px; } h2 { font-size: 20px; }
.subtitle, .empty { color: var(--muted); margin: 6px 0 0; }
.add-member, .members-card, .notice { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 20px; }
.add-member { display: flex; align-items: end; gap: 14px; margin-bottom: 16px; }
label { display: grid; gap: 6px; flex: 1; color: var(--muted); font-size: 14px; }
input, select { border: 1px solid var(--line); border-radius: 6px; padding: 9px 10px; font: inherit; color: var(--ink); }
button { cursor: pointer; border-radius: 7px; padding: 9px 16px; font-weight: 600; }
.btn-primary { border: 1px solid var(--primary); background: var(--primary); color: #fff; }
.btn-secondary { border: 1px solid var(--line); background: #fff; color: var(--ink); }
.btn-danger { border: 1px solid #d44; background: #fff; color: #b22; padding: 6px 10px; }
button:disabled { cursor: not-allowed; opacity: .6; }
.members-card { margin-top: 16px; } table { width: 100%; border-collapse: collapse; margin-top: 14px; }
th, td { border-bottom: 1px solid var(--line); padding: 11px 8px; text-align: left; } th { color: var(--muted); font-size: 13px; }
small { display: block; color: var(--muted); margin-top: 3px; }.loading, .error, .message { margin: 12px 0; }.error { color: var(--danger); }.message { color: #16794c; }
@media (max-width: 640px) { .header, .add-member { align-items: stretch; flex-direction: column; } .add-member label { width: 100%; } }
</style>
