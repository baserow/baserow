<template>
  <div class="card-single-select-option__wrapper">
    <div
      v-if="value"
      class="card-single-select-option"
      :class="'background-color--' + value.color"
    >
      {{ value.value }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldSingleSelect',
  height: 20,
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
