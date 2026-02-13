<template>
  <div v-if="value" class="array-field__item">
    <div class="array-field__ellipsis" :title="value">
      {{ value }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalFormulaArrayItem',
  props: {
    value: {
      type: null,
      default: null,
    },
  },
}
</script>
