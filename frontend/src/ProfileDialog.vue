<template>
  <div v-if="visible" class="backdrop" @mousedown.self="$emit('close')">
    <form class="panel" @submit.prevent="save">
      <h3>个人资料</h3>
      <label>显示名称<input v-model.trim="form.full_name" maxlength="100" /></label>
      <label>邮箱<input v-model.trim="form.email" type="email" maxlength="100" /></label>
      <p v-if="error" class="error">{{ error }}</p><p v-if="success" class="success">{{ success }}</p>
      <div class="actions"><button type="button" @click="$emit('close')">取消</button><button class="primary" :disabled="saving">保存</button></div>
    </form>
  </div>
</template>
<script setup>
import { ref, watch } from "vue";
import { authFetch, saveCurrentUser } from "./api.js";
const props = defineProps({ visible: Boolean, user: { type: Object, default: null } });
const emit = defineEmits(["close", "updated"]);
const form = ref({ full_name: "", email: "" }); const saving = ref(false); const error = ref(""); const success = ref("");
watch(() => props.visible, open => { if (open) { form.value = { full_name: props.user?.full_name || "", email: props.user?.email || "" }; error.value = ""; success.value = ""; } });
async function save() { saving.value = true; error.value = ""; try { const res = await authFetch("/api/auth/profile", { method: "PUT", body: JSON.stringify(form.value) }); const data = await res.json(); if (!res.ok) throw new Error(data.detail || "保存失败"); emit("updated", saveCurrentUser(data.user)); success.value = data.message || "已保存"; setTimeout(() => emit("close"), 700); } catch (e) { error.value = e.message || "保存失败"; } finally { saving.value = false; } }
</script>
<style scoped>
.backdrop{position:fixed;inset:0;background:#0006;display:grid;place-items:center;z-index:1000}.panel{background:#fff;border-radius:12px;padding:22px;width:min(420px,calc(100% - 32px));display:grid;gap:14px}.panel h3{margin:0}.panel label{display:grid;gap:6px;color:var(--muted);font-size:13px}.panel input{padding:9px;border:1px solid var(--line);border-radius:6px}.actions{display:flex;justify-content:flex-end;gap:8px}.actions button{padding:8px 16px;border:1px solid var(--line);border-radius:6px;background:#fff}.actions .primary{background:var(--primary);color:#fff;border-color:var(--primary)}.error{color:var(--danger)}.success{color:#16794c}
</style>
