<template><WorkspaceIntegrationsTable :workspace="workspace" /></template>
<script>
import WorkspaceIntegrationsTable from '@baserow/modules/core/components/settings/integrations/WorkspaceIntegrationsTable'
export default {
  name: 'Integrations',
  components: { WorkspaceIntegrationsTable },
  props: { workspace: { type: Object, required: true } },
}
</script>
