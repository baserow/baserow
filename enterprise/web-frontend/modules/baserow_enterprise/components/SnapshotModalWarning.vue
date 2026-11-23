<template>
  <span>{{ message }}</span>
</template>

<script>
export default {
  name: 'SnapshotModalWarning',
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  computed: {
    message() {
      return this.$registry
        .get('application', this.application.type)
        .getSnapshotPermissionDescription()
    },
  },
}
</script>
