<template>
  <div>
    <DashboardWidget
      v-for="widget in widgets"
      :key="widget.id"
      :widget="widget"
      :dashboard="dashboard"
    />
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'

export default {
  name: 'WidgetBoard',
  components: { DashboardWidget },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({
      isEditMode: 'dashboardApplication/isEditMode',
      widgets: 'dashboardApplication/getWidgets',
    }),
  },
}
</script>
