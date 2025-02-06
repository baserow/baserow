<template>
  <div class="dashboard-app">
    <DashboardHeader :dashboard="dashboard" />
    <DashboardContent :dashboard="dashboard" />
  </div>
</template>

<script>
import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'
import DashboardContent from '@baserow/modules/dashboard/components/DashboardContent'

export default {
  name: 'Dashboard',
  components: { DashboardHeader, DashboardContent },
  beforeRouteLeave(to, from, next) {
    this.$store.dispatch('application/unselect')
    next()
  },
  layout: 'app',
  middleware: 'dashboardLoading',
  async asyncData({ app, store, params, error, $registry }) {
    const dashboardId = parseInt(params.dashboardId)
    const data = {}
    try {
      const dashboard = await store.dispatch(
        'application/selectById',
        dashboardId
      )
      const workspace = await store.dispatch(
        'workspace/selectById',
        dashboard.workspace.id
      )
      data.workspace = workspace
      data.dashboard = dashboard
    } catch (e) {
      return error({ statusCode: 404, message: 'Dashboard not found.' })
    }
    return data
  },
  mounted() {
    const forEditing = this.$hasPermission(
      'application.update',
      this.dashboard,
      this.dashboard.workspace.id
    )
    this.$store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: this.dashboard.id,
      forEditing,
    })
    this.$realtime.subscribe('dashboard', { dashboard_id: this.dashboard.id })
  },
  beforeDestroy() {
    this.$realtime.unsubscribe('dashboard', { dashboard_id: this.dashboard.id })
  },
}
</script>
