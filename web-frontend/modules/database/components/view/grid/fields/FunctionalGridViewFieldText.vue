<template>
  <div class="grid-view__cell">
    <div class="grid-field-text">{{ value }}</div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldText',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
}
</script>
