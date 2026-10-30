<template>
  <div class="dashboard-sidebar">
    <WidgetSettings
      v-if="selectedWidget"
      :dashboard="dashboard"
      :widget="selectedWidget"
      :store-prefix="storePrefix"
    />
    <DashboardFilterSettings
      v-else-if="selectedFilter"
      :filter="selectedFilter"
      :dashboard="dashboard"
      :store-prefix="storePrefix"
    />
    <EmptyDashboardSidebar v-else />
  </div>
</template>

<script>
import EmptyDashboardSidebar from '@baserow/modules/dashboard/components/EmptyDashboardSidebar'
import WidgetSettings from '@baserow/modules/dashboard/components/widget/WidgetSettings'
import DashboardFilterSettings from '@baserow/modules/dashboard/components/filter/DashboardFilterSettings'

export default {
  name: 'DashboardSidebar',
  components: {
    EmptyDashboardSidebar,
    WidgetSettings,
    DashboardFilterSettings,
  },
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
    selectedFilter() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getSelectedFilter`
      ]
    },
    selectedWidget() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getSelectedWidget`
      ]
    },
  },
}
</script>
