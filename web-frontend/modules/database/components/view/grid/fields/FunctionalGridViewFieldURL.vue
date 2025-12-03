<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-text">
      <u>
        {{ value }}
      </u>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldURL',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
}
</script>
