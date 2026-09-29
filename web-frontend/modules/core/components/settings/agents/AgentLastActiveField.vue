<template>
  <span>{{ row.last_active ? formatted : '—' }}</span>
</template>

<script>
export default {
  name: 'AgentLastActiveField',
  props: { row: { type: Object, required: true } },
  computed: {
    formatted() {
      return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
        new Date(this.row.last_active)
      )
    },
  },
}
</script>
