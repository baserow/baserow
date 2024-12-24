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
import { mapGetters } from 'vuex'

export default {
  name: 'DashboardSidebar',
  components: { EmptyDashboardSidebar, WidgetSettings },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({
      selectedWidget: 'dashboardApplication/getSelectedWidget',
    }),
  },
}
</script>
