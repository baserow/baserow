<template>
  <ClientOnly>
    <DashboardWidgetGrid :dashboard="dashboard" :store-prefix="storePrefix" />
    <template #fallback>
      <div
        class="dashboard-widget-board__fallback"
        data-testid="dashboard-widget-board-fallback"
      >
        <DashboardWidget
          v-for="widget in widgets"
          :key="widget.id"
          :widget="widget"
          :dashboard="dashboard"
          :store-prefix="storePrefix"
          :is-layout-editable="false"
        />
      </div>
    </template>
  </ClientOnly>
</template>

<script>
import DashboardWidgetGrid from '@baserow/modules/dashboard/components/DashboardWidgetGrid.client'
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'

export default {
  name: 'WidgetBoard',
  components: { DashboardWidget, DashboardWidgetGrid },
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
  computed: {
    widgets() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getWidgets`
      ]
    },
  },
}
</script>
