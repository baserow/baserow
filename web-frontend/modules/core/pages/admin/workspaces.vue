<template>
  <WorkspacesAdminTable></WorkspacesAdminTable>
</template>

<script>
import { useHead } from '#imports'
import { useNuxtApp } from '#app'
import WorkspacesAdminTable from '@baserow/modules/core/components/admin/workspaces/WorkspacesAdminTable'

export default {
  components: { WorkspacesAdminTable },
  layout: 'app',
  middleware: 'staff',
  setup() {
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('adminWorkspaces.title') })
  },
}
</script>
