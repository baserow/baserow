export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('widget_created', ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      store.dispatch('dashboardApplication/handleNewWidgetCreated', data.widget)
    }
  })
  realtime.registerEvent('widget_updated', ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      store.dispatch('dashboardApplication/handleWidgetUpdated', data.widget)
    }
  })
  realtime.registerEvent('widget_deleted', ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      store.dispatch('dashboardApplication/handleWidgetDeleted', data.widget.id)
    }
  })
  realtime.registerEvent('data_source_updated', ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      store.dispatch(
        'dashboardApplication/handleDataSourceUpdated',
        data.data_source
      )
    }
  })
}
