<template>
  <div class="admin-shell">
    <aside class="admin-sider">
      <div class="sider-brand">
        <span class="brand-dot"></span>
        <div>
          <strong>管理后台</strong>
          <small>人员 · 组织 · 权限</small>
        </div>
      </div>
      <nav class="sider-nav">
        <button
          v-for="item in tabs"
          :key="item.key"
          type="button"
          :class="{ active: tab === item.key }"
          @click="tab = item.key"
        >
          <span class="nav-icon" v-html="item.icon"></span>
          <span>{{ item.label }}</span>
        </button>
      </nav>
      <div class="sider-foot">
        <button type="button" class="back-btn" @click="$emit('close')">← 返回项目</button>
      </div>
    </aside>

    <section class="admin-main">
      <header class="admin-header">
        <div>
          <h1>{{ current.label }}</h1>
          <p class="desc">{{ current.desc }}</p>
        </div>
      </header>

      <UserManagement v-if="tab === 'users'" embedded />
      <RoleManagement v-else-if="tab === 'roles'" />
      <PermissionManagement v-else-if="tab === 'permissions'" />
      <DepartmentManagement v-else-if="tab === 'departments'" />
      <InterfaceSettings v-else @updated="$emit('settings-updated')" />
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import UserManagement from "./UserManagement.vue";
import PermissionManagement from "./PermissionManagement.vue";
import InterfaceSettings from "./InterfaceSettings.vue";
import DepartmentManagement from "./DepartmentManagement.vue";
import RoleManagement from "./RoleManagement.vue";

defineEmits(["close", "settings-updated"]);

const tabs = [
  { key: "users", label: "用户管理", desc: "维护账号、部门归属与登录状态", icon: "&#128100;" },
  { key: "departments", label: "部门/课室", desc: "维护组织层级，送检范围的归属单位", icon: "&#127970;" },
  { key: "roles", label: "角色管理", desc: "定义角色与权限点，一次配置多处复用", icon: "&#128273;" },
  { key: "permissions", label: "权限管理", desc: "给用户按项目分配角色", icon: "&#128274;" },
  { key: "interface", label: "界面管理", desc: "控制列表展示与导航顺序", icon: "&#9881;" },
];

const tab = ref("users");
const current = computed(() => tabs.find((t) => t.key === tab.value) || tabs[0]);
</script>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 210px minmax(0, 1fr);
  gap: 18px;
  max-width: 1400px;
  margin: 24px auto 40px;
  padding: 0 20px;
  align-items: start;
}

.admin-sider {
  position: sticky;
  top: 18px;
  background: #fff;
  border: 1px solid #e6e8e3;
  border-radius: 12px;
  padding: 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.sider-brand { display: flex; align-items: center; gap: 10px; padding: 4px 10px 12px; border-bottom: 1px solid #f0f2ee; }
.brand-dot { width: 10px; height: 10px; border-radius: 3px; background: #548235; }
.sider-brand strong { display: block; font-size: 14px; color: #2b3028; }
.sider-brand small { font-size: 11px; color: #909688; }

.sider-nav { display: flex; flex-direction: column; gap: 2px; }
.sider-nav button {
  display: flex; align-items: center; gap: 10px;
  border: none; background: transparent; text-align: left;
  padding: 9px 12px; border-radius: 8px; font-size: 13.5px;
  color: #4b5247; cursor: pointer; transition: background 0.15s, color 0.15s;
}
.sider-nav button:hover { background: #f4f7f1; }
.sider-nav button.active { background: #eef6ea; color: #3f6427; font-weight: 600; }
.nav-icon { font-size: 14px; opacity: 0.8; width: 18px; text-align: center; }

.sider-foot { margin-top: auto; padding-top: 10px; border-top: 1px solid #f0f2ee; }
.back-btn {
  width: 100%; border: 1px solid #e2e6dd; background: #fff; border-radius: 8px;
  padding: 8px 10px; font-size: 12.5px; color: #5a6157; cursor: pointer;
}
.back-btn:hover { background: #f8faf6; }

.admin-main { min-width: 0; }
.admin-header { margin-bottom: 16px; }
.admin-header h1 { margin: 0 0 4px; font-size: 22px; color: #262b24; }
.admin-header .desc { margin: 0; color: #7f857a; font-size: 13px; }

@media (max-width: 960px) {
  .admin-shell { grid-template-columns: 1fr; }
  .admin-sider { position: static; }
  .sider-nav { flex-direction: row; flex-wrap: wrap; }
}
</style>
