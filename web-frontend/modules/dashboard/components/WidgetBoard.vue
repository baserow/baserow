<template>
  <ClientOnly fallback-tag="div">
    <DashboardWidgetGrid :dashboard="dashboard" :store-prefix="storePrefix" />
  </ClientOnly>
</template>

<script>
import DashboardWidgetGrid from '@baserow/modules/dashboard/components/DashboardWidgetGrid.client'

export default {
  name: 'WidgetBoard',
  components: { DashboardWidgetGrid },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
  },
}
</script>
