<template>
  <WorkspacesAdminTable></WorkspacesAdminTable>
</template>

<script>
import WorkspacesAdminTable from '@baserow/modules/core/components/admin/workspaces/WorkspacesAdminTable'

export default {
  components: { WorkspacesAdminTable },
  layout: 'app',
  middleware: 'staff',
}
</script>
