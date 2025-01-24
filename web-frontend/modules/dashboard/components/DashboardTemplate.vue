<template>
  <Dashboard :dashboard="pageValue.dashboard" store-prefix="template/" />
</template>

<script>
import Dashboard from '@baserow/modules/dashboard/components/Dashboard'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'DashboardTemplate',
  components: { Dashboard },
  props: {
    pageValue: {
      type: Object,
      required: true,
    },
  },
  watch: {
    pageValue: {
      handler(pageValue) {
        this.fetchDashboard(pageValue.dashboard)
      },
    },
  },
  mounted() {
    this.fetchDashboard(this.pageValue.dashboard)
  },
  methods: {
    async fetchDashboard(dashboard) {
      try {
        await this.$store.dispatch(
          'template/dashboardApplication/setLoading',
          true
        )
        await this.$store.dispatch(
          'template/dashboardApplication/fetchInitial',
          {
            dashboardId: dashboard.id,
            forEditing: false,
          }
        )
        await this.$store.dispatch(
          'template/dashboardApplication/setLoading',
          false
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
  },
}
</script>
