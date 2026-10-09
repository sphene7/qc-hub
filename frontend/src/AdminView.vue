<template>
  <div class="admin-view">
    <div class="header">
      <div>
        <h1>管理</h1>
        <p class="subtitle">系统用户、模块权限与界面显示配置</p>
      </div>
      <button class="btn-secondary" @click="$emit('close')">返回</button>
    </div>

    <div class="admin-tabs">
      <button
        type="button"
        :class="{ on: tab === 'users' }"
        @click="tab = 'users'"
      >用户管理</button>
      <button
        type="button"
        :class="{ on: tab === 'permissions' }"
        @click="tab = 'permissions'"
      >权限管理</button>
      <button
        type="button"
        :class="{ on: tab === 'interface' }"
        @click="tab = 'interface'"
      >界面管理</button>
    </div>

    <UserManagement v-if="tab === 'users'" embedded />
    <PermissionManagement v-else-if="tab === 'permissions'" />
    <InterfaceSettings v-else @updated="$emit('settings-updated')" />
  </div>
</template>

<script setup>
import { ref } from "vue";
import UserManagement from "./UserManagement.vue";
import PermissionManagement from "./PermissionManagement.vue";
import InterfaceSettings from "./InterfaceSettings.vue";

defineEmits(["close", "settings-updated"]);

const tab = ref("users");
</script>

<style scoped>
.admin-view {
  max-width: 1200px;
  margin: 40px auto;
  padding: 0 20px 40px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header h1 {
  margin: 0;
  font-size: 32px;
  color: var(--primary);
}

.subtitle {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 14px;
}

.btn-secondary {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  background: white;
  border: 1px solid var(--line);
  color: var(--ink);
}

.admin-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.admin-tabs button {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--muted);
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
}

.admin-tabs button.on {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}
</style>
