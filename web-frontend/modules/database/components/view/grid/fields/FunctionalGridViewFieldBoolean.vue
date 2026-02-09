<template>
  <div class="grid-view__cell">
    <div class="grid-field-boolean">
      <div class="grid-field-boolean__checkbox" :class="{ active: value }">
        <i class="iconoir-check grid-field-boolean__checkbox-icon"></i>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldBoolean',
  props: {
    value: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
