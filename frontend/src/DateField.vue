<template>
  <input
    type="date"
    class="date-field"
    :value="modelValue"
    :disabled="disabled"
    v-bind="$attrs"
    @input="onInput"
    @change="onChange"
  />
</template>

<script setup>
defineOptions({ inheritAttrs: false });

defineProps({
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "change"]);

function onInput(e) {
  emit("update:modelValue", e.target.value);
}

function onChange(e) {
  emit("change", e.target.value);
}
</script>

<style scoped>
.date-field {
  width: 100%;
}
</style>
