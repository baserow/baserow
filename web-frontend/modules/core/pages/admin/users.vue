<template>
  <UsersAdminTable></UsersAdminTable>
</template>

<script>
import { useHead } from '#imports'
import UsersAdminTable from '@baserow/modules/core/components/admin/users/UsersAdminTable'

export default {
  components: { UsersAdminTable },
  layout: 'app',
  middleware: 'staff',
  setup() {
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('adminUsers.title') })
  },
}
</script>
