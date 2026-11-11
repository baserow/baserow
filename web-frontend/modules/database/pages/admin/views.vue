<template>
  <ViewsAdminTable></ViewsAdminTable>
</template>

<script>
import { useHead } from '#imports'
import ViewsAdminTable from '@baserow/modules/database/components/admin/views/ViewsAdminTable'

definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

export default {
  components: { ViewsAdminTable },
  setup() {
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('viewsAdmin.title') })
  },
}
</script>
