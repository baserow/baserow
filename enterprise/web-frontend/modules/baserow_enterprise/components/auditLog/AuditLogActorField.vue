<template>
  <div :title="displayValue">
    {{ displayValue }}
  </div>
</template>

<script>
export default {
  name: 'AuditLogActorField',
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
    displayValue() {
      const actor = this.row.actor
      if (!actor?.id) {
        return this.row[this.column.key] || ''
      }

      return this.$t('auditLog.actorDisplay', {
        name: actor.name,
        id: actor.id,
      })
    },
  },
}
</script>
