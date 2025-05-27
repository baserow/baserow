<template>
  <div>
    <FormGroup label="Action" small-label required>
      <Dropdown />
    </FormGroup>

    <div class="separator" />

    <FormGroup label="Action" small-label required>
      <Dropdown />
    </FormGroup>
  </div>
</template>

<script setup>
// eslint-disable-next-line no-unused-vars
const props = defineProps({
  node: {
    type: Object,
    required: true,
    default: null,
  },
})
</script>
