<template>
  <ClientOnly>
    <DashboardWidgetGrid :dashboard="dashboard" :store-prefix="storePrefix" />
    <template #fallback>
      <div
        class="dashboard-widget-board__fallback"
        data-testid="dashboard-widget-board-fallback"
      >
        <DashboardWidgetGridLoading />
      </div>
    </template>
  </ClientOnly>
</template>

<script>
import DashboardWidgetGrid from '@baserow/modules/dashboard/components/DashboardWidgetGrid.client'
import DashboardWidgetGridLoading from '@baserow/modules/dashboard/components/DashboardWidgetGridLoading'

export default {
  name: 'WidgetBoard',
  components: { DashboardWidgetGrid, DashboardWidgetGridLoading },
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
