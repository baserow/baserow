<template>
  <Alert v-if="error.visible" type="error">
    <template #title>{{ error.title }}</template>
    <p>{{ error.message }}</p>
  </Alert>
</template>

<script>
/**
 * This component works the best if the parent has the error mixin.
 */
export default {
  name: 'Error',
  props: {
    error: {
      required: true,
      type: Object,
    },
  },
}
</script>
