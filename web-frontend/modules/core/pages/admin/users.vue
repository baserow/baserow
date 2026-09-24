<template>
  <UsersAdminTable></UsersAdminTable>
</template>

<script>
import { useHead } from '#imports'
import UsersAdminTable from '@baserow/modules/core/components/admin/users/UsersAdminTable'

export default {
  components: { UsersAdminTable },
  setup() {
    // Must be declared via `definePageMeta` because Nuxt ignores the legacy
    // `layout` and `middleware` component options.
    definePageMeta({
      layout: 'app',
      middleware: 'staff',
    })
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('adminUsers.title') })
  },
}
</script>
