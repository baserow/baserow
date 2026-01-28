<template>
  <div ref="cell" class="grid-view__cell grid-field-single-select__cell">
    <div class="grid-field-single-select">
      <div
        v-if="value"
        class="grid-field-single-select__option"
        :class="'background-color--' + value.color"
      >
        {{ value.value }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldSingleSelect',
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
