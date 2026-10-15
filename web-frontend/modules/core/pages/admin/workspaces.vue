<template>
  <WorkspacesAdminTable></WorkspacesAdminTable>
</template>

<script>
import { useHead } from '#imports'
import { useNuxtApp } from '#app'
import WorkspacesAdminTable from '@baserow/modules/core/components/admin/workspaces/WorkspacesAdminTable'

export default {
  components: { WorkspacesAdminTable },
  setup() {
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('adminWorkspaces.title') })
  },
}
</script>

<script setup>
definePageMeta({
  layout: 'app',
  middleware: 'staff',
})
</script>
