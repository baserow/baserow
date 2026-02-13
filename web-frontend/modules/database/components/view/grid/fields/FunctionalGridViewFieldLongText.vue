<template>
  <div class="grid-view__cell grid-field-long-text__cell">
    <div class="grid-field-long-text">{{ value }}</div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldLongText',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
}
</script>
