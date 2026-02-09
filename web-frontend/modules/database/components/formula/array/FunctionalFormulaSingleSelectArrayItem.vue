<template>
  <div
    v-if="value"
    class="array-field__single-option"
    :class="'background-color--' + value.color"
  >
    <div class="array-field__ellipsis">{{ value.value }}</div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalFormulaSingleSelectArrayItem',
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
