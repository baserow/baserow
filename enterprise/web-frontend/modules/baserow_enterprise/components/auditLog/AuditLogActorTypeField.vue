<template>
  <div :title="actorType">
    {{ actorType }}
  </div>
</template>

<script>
export default {
  name: 'AuditLogActorTypeField',
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
  computed: {
    actorType() {
      const type = this.row.actor?.type
      if (!type) {
        return ''
      }
      return this.$registry.exists('subject', type)
        ? this.$registry.get('subject', type).getTypeDisplayName()
        : type
    },
  },
}
</script>
