<template>
  <div class="dashboard-sidebar">
    <WidgetSettings
      v-if="selectedWidget"
      :dashboard="dashboard"
      :widget="selectedWidget"
    />
    <EmptyDashboardSidebar v-else />
  </div>
</template>

<script>
import EmptyDashboardSidebar from '@baserow/modules/dashboard/components/EmptyDashboardSidebar'
import WidgetSettings from '@baserow/modules/dashboard/components/widget/WidgetSettings'

export default {
  name: 'DashboardSidebar',
  components: { EmptyDashboardSidebar, WidgetSettings },
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
    selectedWidget() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getSelectedWidget`
      ]
    },
  },
}
</script>
