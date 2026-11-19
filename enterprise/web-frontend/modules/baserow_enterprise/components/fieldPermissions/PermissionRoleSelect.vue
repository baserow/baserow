<template>
  <Dropdown
    :value="model"
    :show-search="false"
    :fixed-items="true"
    :size="size"
    @input="model = $event"
  >
    <DropdownItem
      v-for="option in options"
      :key="option.uid"
      :name="option.title"
      :value="option.uid"
      :description="option.desc"
      :disabled="option.disabled"
    />
  </Dropdown>
</template>
<script setup>
defineProps({
  size: { type: String, default: 'large' },
  options: { type: Array, required: true },
})
const model = defineModel({ type: String, default: null })
</script>
