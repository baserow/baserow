<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-password">
      <div class="grid-field-password__dots">
        {{ value ? '••••••••••' : '' }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridVIewFieldPassword',
  props: {
    value: {
      type: null,
      default: '',
    },
  },
}
</script>
