<template>
  <a class="grid-view__row-more" @click="onClick">
    <i class="baserow-icon-enlarge-row"></i>
  </a>
</template>
<script>
export default {
  name: 'GridViewRowExpandButton',
  emits: ['edit-modal'],
  methods: {
    onClick() {
      this.$emit('edit-modal')
    },
  },
}
</script>
