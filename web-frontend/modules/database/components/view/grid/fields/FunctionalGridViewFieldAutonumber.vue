<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-number">{{ value }}</div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldAutonumber',
  props: {
    value: {
      type: null,
      default: null,
    },
  },
}
</script>
