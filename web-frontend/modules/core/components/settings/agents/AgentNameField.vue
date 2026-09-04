<template>
  <div class="agents-table__name">
    <span class="agents-table__icon"><i class="baserow-icon-agent"></i></span>
    <span>{{ row.name }}</span>
  </div>
</template>

<script>
export default {
  name: 'AgentNameField',
  props: { row: { type: Object, required: true } },
}
</script>
