<template functional>
  <a
    class="grid-view__row-more"
    @click="listeners['edit-modal'] && listeners['edit-modal']()"
  >
    <i class="baserow-icon-enlarge-row"></i>
  </a>
</template>
<script>
export default {
  name: 'GridViewRowExpandButton',
  functional: true,
}
</script>
