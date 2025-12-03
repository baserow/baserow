<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-text">
      {{ value }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldPhoneNumber',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
}
</script>
