<template>
  <div v-if="visible" class="modal-backdrop" @mousedown.self="close">
    <div class="modal-panel">
      <div class="modal-head">
        <h3>修改密码</h3>
        <button type="button" class="icon-btn" @click="close">✕</button>
      </div>
      <form class="modal-body" @submit.prevent="submit">
        <label class="field">
          <span>当前密码</span>
          <input v-model="currentPassword" type="password" autocomplete="current-password" required />
        </label>
        <label class="field">
          <span>新密码</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" minlength="6" required />
        </label>
        <label class="field">
          <span>确认新密码</span>
          <input v-model="confirmPassword" type="password" autocomplete="new-password" minlength="6" required />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="success" class="success">{{ success }}</p>
        <div class="modal-actions">
          <button type="button" class="ghost-btn" @click="close">取消</button>
          <button type="submit" class="primary-btn" :disabled="saving">
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { authFetch } from "./api.js";

const props = defineProps({
  visible: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);

const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const saving = ref(false);
const error = ref("");
const success = ref("");

watch(
  () => props.visible,
  (open) => {
    if (open) reset();
  }
);

function reset() {
  currentPassword.value = "";
  newPassword.value = "";
  confirmPassword.value = "";
  error.value = "";
  success.value = "";
  saving.value = false;
}

function close() {
  emit("close");
}

async function submit() {
  error.value = "";
  success.value = "";

  if (newPassword.value.length < 6) {
    error.value = "新密码至少 6 位";
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = "两次输入的新密码不一致";
    return;
  }

  saving.value = true;
  try {
    const res = await authFetch("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword.value,
        new_password: newPassword.value,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "修改失败");
    }
    success.value = "密码已更新";
    setTimeout(() => close(), 1200);
  } catch (err) {
    error.value = err.message || "修改失败";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-panel {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
}

.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px;
  border-bottom: 1px solid var(--line);
}

.modal-head h3 {
  margin: 0;
  font-size: 18px;
}

.modal-body {
  padding: 18px;
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}

.field input {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 14px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

.primary-btn,
.ghost-btn {
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 14px;
  cursor: pointer;
}

.primary-btn {
  border: 0;
  background: var(--primary);
  color: #fff;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost-btn {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
}

.icon-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  color: var(--muted);
}

.error {
  color: var(--danger);
  margin: 0;
  font-size: 13px;
}

.success {
  color: #15803d;
  margin: 0;
  font-size: 13px;
}
</style>
