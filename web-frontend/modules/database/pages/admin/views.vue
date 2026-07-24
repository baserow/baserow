<template>
  <ViewsAdminTable></ViewsAdminTable>
</template>

<script>
import { useHead } from '#imports'
import ViewsAdminTable from '@baserow/modules/database/components/admin/views/ViewsAdminTable'

export default {
  components: { ViewsAdminTable },
  layout: 'app',
  middleware: 'staff',
  setup() {
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('viewsAdmin.title') })
  },
}
</script>
