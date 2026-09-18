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
    // Must be declared via `definePageMeta` because Nuxt ignores the legacy
    // `layout` and `middleware` component options.
    definePageMeta({
      layout: 'app',
      middleware: 'staff',
    })
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('adminWorkspaces.title') })
  },
}
</script>
