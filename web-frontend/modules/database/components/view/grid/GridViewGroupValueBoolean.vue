<template>
  <span
    class="grid-view__group-value-boolean"
    :class="{
      'grid-view__group-value-boolean--true': value,
      'grid-view__group-value-boolean--false': !value,
    }"
  >
    <i :class="value ? 'iconoir-check' : 'iconoir-cancel'"></i>
  </span>
</template>

<script>
export default {
  name: 'GridViewGroupValueBoolean',
  props: {
    value: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
