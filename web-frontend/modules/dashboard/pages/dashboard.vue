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
      const forEditing = app.$hasPermission(
        'application.update',
        dashboard,
        dashboard.workspace.id
      )
      await store.dispatch('dashboardApplication/fetchInitial', {
        dashboardId: dashboard.id,
        forEditing,
      })
      data.workspace = workspace
      data.dashboard = dashboard
      await store.dispatch('dashboardApplication/setLoading', false)
    } catch (e) {
      return error({ statusCode: 404, message: 'Dashboard not found.' })
    }
    return data
  },
}
</script>
