<template>
  <div class="rich-text-field">
    <textarea
      ref="textareaRef"
      :rows="rows"
      :value="modelValue"
      :placeholder="placeholder"
      @input="onInput"
      @paste="onPaste"
    />
    <div class="rich-toolbar">
      <button type="button" class="rich-btn" @click="pickImage">插入图片</button>
      <input ref="fileInputRef" type="file" accept="image/*" hidden @change="onFileChange" />
    </div>
    <div v-if="previewImages.length" class="rich-preview">
      <div v-for="(img, i) in previewImages" :key="i" class="rich-preview-item">
        <img :src="img.src" :alt="img.label || '已插入图片'" />
        <button
          type="button"
          class="rich-remove-btn"
          title="删除图片"
          @click="removeImage(i)"
        >✕</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  rows: { type: Number, default: 3 },
  placeholder: { type: String, default: "" },
  maxImageBytes: { type: Number, default: 2 * 1024 * 1024 },
});

const emit = defineEmits(["update:modelValue", "change"]);

const IMAGE_MARKDOWN_RE = /!\[([^\]]*)\]\((data:image\/[^)]+)\)/g;

const textareaRef = ref(null);
const fileInputRef = ref(null);

const previewImages = computed(() => {
  const text = props.modelValue || "";
  const items = [];
  for (const match of text.matchAll(IMAGE_MARKDOWN_RE)) {
    items.push({
      label: match[1] || "image",
      src: match[2],
      markdown: match[0],
    });
  }
  return items;
});

function removeImage(index) {
  const text = props.modelValue || "";
  let seen = 0;
  const next = text.replace(IMAGE_MARKDOWN_RE, (markdown) => {
    if (seen === index) {
      seen += 1;
      return "";
    }
    seen += 1;
    return markdown;
  });
  const cleaned = next.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  emit("update:modelValue", cleaned);
  emit("change", cleaned);
}

function onInput(event) {
  emit("update:modelValue", event.target.value);
  emit("change", event.target.value);
}

function pickImage() {
  fileInputRef.value?.click();
}

function insertAtCursor(snippet) {
  const el = textareaRef.value;
  if (!el) {
    emit("update:modelValue", `${props.modelValue || ""}${snippet}`);
    emit("change", `${props.modelValue || ""}${snippet}`);
    return;
  }
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? el.value.length;
  const next = `${el.value.slice(0, start)}${snippet}${el.value.slice(end)}`;
  emit("update:modelValue", next);
  emit("change", next);
  requestAnimationFrame(() => {
    el.focus();
    const pos = start + snippet.length;
    el.setSelectionRange(pos, pos);
  });
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function insertImageFile(file) {
  if (!file || !file.type.startsWith("image/")) return;
  if (file.size > props.maxImageBytes) {
    alert(`图片过大（>${Math.round(props.maxImageBytes / 1024 / 1024)}MB），请压缩后重试`);
    return;
  }
  const dataUrl = await readFileAsDataUrl(file);
  const name = file.name || "image";
  insertAtCursor(`\n![${name}](${dataUrl})\n`);
}

async function onFileChange(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  try {
    await insertImageFile(file);
  } catch {
    alert("读取图片失败，请重试");
  }
}

async function onPaste(event) {
  const items = event.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (!item.type.startsWith("image/")) continue;
    event.preventDefault();
    const file = item.getAsFile();
    if (file) await insertImageFile(file);
    return;
  }
}
</script>

<style scoped>
.rich-text-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

textarea {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--line, #e5e7eb);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.4;
  resize: vertical;
  box-sizing: border-box;
}

.rich-toolbar {
  display: flex;
  gap: 6px;
}

.rich-btn {
  border: 1px solid var(--line, #e5e7eb);
  background: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  color: var(--primary, #6366f1);
}

.rich-btn:hover {
  border-color: var(--primary, #6366f1);
}

.rich-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rich-preview-item {
  position: relative;
  display: inline-flex;
}

.rich-preview-item img {
  max-width: 120px;
  max-height: 80px;
  object-fit: contain;
  border: 1px solid var(--line, #e5e7eb);
  border-radius: 4px;
  background: #fafafa;
}

.rich-remove-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.rich-remove-btn:hover {
  background: #dc2626;
}
</style>
