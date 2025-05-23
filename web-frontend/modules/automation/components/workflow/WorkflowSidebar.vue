<template>
  <div>
    <pre v-if="props.node">{{ JSON.stringify(props.node, null, 2) }}</pre>

    <br />
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
const props = defineProps({
  node: {
    type: Object,
    required: true,
    default: null,
  },
})
</script>
