export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent(
    'dashboard_filters_updated',
    async ({ store }, data) => {
      if (
        data.dashboard_id ===
        store.getters['dashboardApplication/getDashboardId']
      ) {
        // An order update can overtake a selection update. Reconcile both;
        // unchanged runtime inputs will not dispatch any widgets.
        await store.dispatch('dashboardApplication/handleFiltersUpdated')
      }
    }
  )
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
    const dashboardId = data.dashboard_id
    if (dashboardId === store.getters['dashboardApplication/getDashboardId']) {
      await store
        .dispatch(
          'dashboardApplication/handleDataSourceUpdated',
          data.data_source
        )
        .catch(() => {})
      if (
        dashboardId === store.getters['dashboardApplication/getDashboardId']
      ) {
        // Table schemas depend on this user's access and are omitted from broadcasts.
        await store.dispatch(
          'dashboardApplication/fetchNewDataSources',
          dashboardId
        )
      }
    }
  })
}
