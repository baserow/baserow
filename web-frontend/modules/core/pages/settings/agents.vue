<template><AgentsTable :workspace="workspace" /></template>
<script>
import AgentsTable from '@baserow/modules/core/components/settings/agents/AgentsTable'
export default {
  name: 'Agents',
  components: { AgentsTable },
  props: { workspace: { type: Object, required: true } },
}
</script>
