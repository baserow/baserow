export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('widget_created', ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      store.dispatch('dashboardApplication/handleNewWidgetCreated', data.widget)
    }
  })
}
