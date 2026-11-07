<template>
  <div class="dept-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <input v-model="keyword" class="search" placeholder="搜索部门 / 负责人" />
        <span class="count">共 {{ departments.length }} 个部门</span>
      </div>
      <div class="toolbar-right">
        <button class="btn-primary" @click="openCreate(null)">+ 新增一级部门</button>
        <button class="btn-secondary" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th class="col-name">部门 / 课室</th>
            <th>负责人</th>
            <th class="num">人数</th>
            <th>状态</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="5" class="empty">加载中…</td></tr>
          <tr v-else-if="!rows.length"><td colspan="5" class="empty">还没有部门，点右上角新增</td></tr>
          <template v-else>
            <tr v-for="d in rows" :key="d.id">
              <td class="col-name">
                <span class="indent" :style="{ paddingLeft: d.depth * 20 + 'px' }">
                  <button
                    v-if="d.hasChildren && !keyword"
                    class="tree-toggle"
                    :class="{ open: expanded.has(d.id) }"
                    @click="toggle(d.id)"
                  >▸</button>
                  <span v-else class="tree-toggle placeholder"></span>
                  <span class="node-dot" :class="{ leaf: !d.hasChildren }"></span>
                  <strong>{{ d.name }}</strong>
                </span>
              </td>
              <td>{{ d.leader || '-' }}</td>
              <td class="num">{{ d.user_count }}</td>
              <td>
                <span class="badge" :class="d.active ? 'on' : 'off'">{{ d.active ? '启用' : '停用' }}</span>
              </td>
              <td class="ops">
                <button class="link" @click="openCreate(d.id)">加下级</button>
                <button class="link" @click="openEdit(d)">编辑</button>
                <button class="link" @click="toggleActive(d)">{{ d.active ? '停用' : '启用' }}</button>
                <button
                  class="link danger"
                  :disabled="d.user_count > 0 || d.hasChildren"
                  :title="d.user_count > 0 ? '还有用户属于该部门' : d.hasChildren ? '还有下级部门' : ''"
                  @click="remove(d)"
                >删除</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="modal.open" class="overlay">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ modal.id ? '编辑部门' : modal.parentId ? '新增下级部门' : '新增一级部门' }}</h3>
          <button class="close" @click="closeModal">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="modal.parentName" class="parent-hint">上级：{{ modal.parentName }}</div>
          <label class="field">
            <span>名称<span class="req">*</span></span>
            <input v-model="form.name" placeholder="如：变焦二课" />
          </label>
          <label class="field">
            <span>负责人</span>
            <input v-model="form.leader" placeholder="可选" />
          </label>
          <label class="field inline">
            <input v-model="form.active" type="checkbox" />
            <span>启用</span>
          </label>
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
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { authFetch } from "./api.js";

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const keyword = ref("");
const departments = ref([]);
const expanded = ref(new Set());
const modal = ref({ open: false, id: null, parentId: null, parentName: "", error: "" });
const form = ref({ name: "", leader: "", active: true });

async function readJson(res) {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

const tree = computed(() => {
  const map = new Map();
  for (const d of departments.value) map.set(d.id, { ...d, children: [] });
  const roots = [];
  for (const d of map.values()) {
    if (d.parent_id && map.has(d.parent_id)) map.get(d.parent_id).children.push(d);
    else roots.push(d);
  }
  const sort = (list) => {
    list.sort((a, b) => (a.sort_order - b.sort_order) || a.name.localeCompare(b.name, "zh-CN"));
    list.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
});

const rows = computed(() => {
  const kw = keyword.value.trim();
  if (kw) {
    return departments.value
      .filter((d) => (d.name || "").includes(kw) || (d.leader || "").includes(kw))
      .map((d) => ({ ...d, depth: 0, hasChildren: false }));
  }
  const out = [];
  const walk = (nodes, depth) => {
    for (const n of nodes) {
      out.push({ ...n, depth, hasChildren: n.children.length > 0 });
      if (expanded.value.has(n.id)) walk(n.children, depth + 1);
    }
  };
  walk(tree.value, 0);
  return out;
});

async function load(keepExpanded = false) {
  loading.value = true;
  error.value = "";
  try {
    const res = await authFetch("/api/admin/departments");
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "加载部门失败");
    departments.value = data.departments || [];
    if (!keepExpanded) {
      const next = new Set();
      for (const d of departments.value) if (d.parent_id == null) next.add(d.id);
      // 默认展开有下级的节点
      const parents = new Set(departments.value.filter((d) => d.parent_id).map((d) => d.parent_id));
      expanded.value = parents;
    }
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function toggle(id) {
  const next = new Set(expanded.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expanded.value = next;
}

function flash(message) {
  notice.value = message;
  setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 4000);
}

function openCreate(parentId) {
  const parent = parentId ? departments.value.find((d) => d.id === parentId) : null;
  form.value = { name: "", leader: "", active: true };
  modal.value = { open: true, id: null, parentId: parentId || null, parentName: parent?.name || "", error: "" };
}

function openEdit(d) {
  form.value = { name: d.name, leader: d.leader || "", active: d.active };
  modal.value = { open: true, id: d.id, parentId: d.parent_id || null, parentName: "", error: "" };
}

function closeModal() {
  modal.value = { open: false, id: null, parentId: null, parentName: "", error: "" };
}

async function save() {
  saving.value = true;
  modal.value.error = "";
  try {
    const payload = {
      name: form.value.name,
      leader: form.value.leader,
      active: form.value.active,
    };
    if (modal.value.id) {
      payload.parent_id = modal.value.parentId;
    } else {
      payload.parent_id = modal.value.parentId;
    }
    const url = modal.value.id ? `/api/admin/departments/${modal.value.id}` : "/api/admin/departments";
    const res = await authFetch(url, {
      method: modal.value.id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "保存失败");
    flash(modal.value.id ? "部门已更新" : "部门已新增");
    closeModal();
    await load(true);
  } catch (err) {
    modal.value.error = err.message;
  } finally {
    saving.value = false;
  }
}

async function toggleActive(d) {
  try {
    const res = await authFetch(`/api/admin/departments/${d.id}`, {
      method: "PUT",
      body: JSON.stringify({ name: d.name, leader: d.leader || "", active: !d.active, parent_id: d.parent_id ?? null }),
    });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "操作失败");
    await load(true);
  } catch (err) {
    error.value = err.message;
  }
}

async function remove(d) {
  if (!confirm(`确定删除部门「${d.name}」吗？`)) return;
  try {
    const res = await authFetch(`/api/admin/departments/${d.id}`, { method: "DELETE" });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.detail || "删除失败");
    flash("部门已删除");
    await load(true);
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
.dept-page { display: flex; flex-direction: column; gap: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.search {
  width: 240px; padding: 8px 12px; border: 1px solid #dce1d6;
  border-radius: 8px; font-size: 13px; background: #fff;
}
.search:focus { outline: none; border-color: #9dbb8a; box-shadow: 0 0 0 3px rgba(84, 130, 53, 0.12); }
.count { font-size: 12px; color: #8a9086; }
.toolbar-right { display: flex; gap: 8px; }

.notice { padding: 8px 12px; border-radius: 8px; background: #eef6ea; color: #3a6b28; font-size: 13px; }
.error { padding: 8px 12px; border-radius: 8px; background: #fdecea; color: #b03a2e; font-size: 13px; }

.table-card { background: #fff; border: 1px solid #e6e8e3; border-radius: 12px; overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 9px 14px; border-bottom: 1px solid #f0f2ee; text-align: left; white-space: nowrap; }
th { background: #fafbf8; color: #5a6057; font-weight: 600; font-size: 12.5px; }
tbody tr:hover td { background: #f9fbf7; }
.col-name { min-width: 260px; }
.indent { display: inline-flex; align-items: center; gap: 6px; }
.tree-toggle {
  width: 16px; height: 16px; border: none; background: none; cursor: pointer;
  color: #8a9086; font-size: 11px; transition: transform 0.15s; padding: 0;
}
.tree-toggle.open { transform: rotate(90deg); }
.tree-toggle.placeholder { display: inline-block; }
.node-dot { width: 6px; height: 6px; border-radius: 50%; background: #9dbb8a; }
.node-dot.leaf { background: #d5dcd0; }
.num { text-align: right; }
.ops { text-align: right; }
.empty { text-align: center; color: #999; padding: 32px; }
.badge { font-size: 12px; padding: 1px 9px; border-radius: 999px; }
.badge.on { background: #e6f4df; color: #3a6b28; }
.badge.off { background: #eef0ec; color: #777d73; }
.link { background: none; border: none; color: #5a7a3a; cursor: pointer; font-size: 12.5px; padding: 2px 6px; border-radius: 6px; }
.link:hover { background: #eef6ea; }
.link.danger { color: #c0392b; }
.link.danger:hover { background: #fdecea; }
.link:disabled { color: #c3c8bf; cursor: not-allowed; background: none; }

.overlay { position: fixed; inset: 0; background: rgba(24, 30, 20, 0.38); display: flex; align-items: center; justify-content: center; z-index: 60; padding: 20px; }
.modal { background: #fff; border-radius: 12px; width: min(440px, 100%); box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22); overflow: hidden; }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid #eef0ec; }
.modal-head h3 { margin: 0; font-size: 16px; }
.close { background: none; border: none; font-size: 16px; color: #999; cursor: pointer; }
.modal-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; }
.parent-hint { padding: 8px 10px; background: #f7f9f6; border-radius: 8px; font-size: 12.5px; color: #5d645a; }
.field { display: flex; flex-direction: column; gap: 5px; font-size: 13px; }
.field > span { color: #6f756c; }
.field input:not([type="checkbox"]) { padding: 8px 10px; border: 1px solid #dce1d6; border-radius: 8px; font-size: 13px; }
.field.inline { flex-direction: row; align-items: center; gap: 8px; }
.req { color: #c0392b; margin-left: 2px; }
.modal-error { color: #b03a2e; font-size: 12.5px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid #eef0ec; background: #fbfcfa; }
.btn-primary, .btn-secondary { padding: 6px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #548235; color: #fff; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #fff; border-color: #d6dbcf; color: #444; }
</style>
