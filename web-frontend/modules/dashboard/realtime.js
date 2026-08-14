export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('widget_created', async ({ store }, data) => {
    const dashboardId = data.dashboard_id
    if (dashboardId === store.getters['dashboardApplication/getDashboardId']) {
      await store.dispatch(
        'dashboardApplication/handleNewWidgetCreated',
        data.widget
      )
      if (
        dashboardId !== store.getters['dashboardApplication/getDashboardId']
      ) {
        return
      }
      await Promise.allSettled([
        store.dispatch('dashboardApplication/fetchWidgets', dashboardId),
        store.dispatch('dashboardApplication/fetchNewDataSources', dashboardId),
      ])
    }
  })
  realtime.registerEvent('widget_updated', async ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      await store
        .dispatch('dashboardApplication/handleWidgetUpdated', data.widget)
        .catch(() => {})
    }
  })
  realtime.registerEvent('widget_deleted', async ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      await store
        .dispatch('dashboardApplication/handleWidgetDeleted', data.widget.id)
        .catch(() => {})
    }
  })
  realtime.registerEvent('widgets_layout_updated', async ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      await store.dispatch('dashboardApplication/handleWidgetsLayoutUpdated')
    }
  })
  realtime.registerEvent('data_source_updated', async ({ store }, data) => {
    if (
      data.dashboard_id === store.getters['dashboardApplication/getDashboardId']
    ) {
      await store
        .dispatch(
          'dashboardApplication/handleDataSourceUpdated',
          data.data_source
        )
        .catch(() => {})
    }
  })
}
