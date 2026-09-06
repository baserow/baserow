<template>
  <Dashboard
    :dashboard="pageValue.dashboard"
    :loading="loading"
    store-prefix="template/"
  />
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
  computed: {
    loading() {
      return this.$store.getters['template/dashboardApplication/isLoading']
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
          'template/dashboardApplication/fetchInitial',
          {
            dashboardId: dashboard.id,
            forEditing: false,
          }
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
  },
}
</script>
