export default (client) => {
  return {
    getAllWidgets(dashboardId) {
      return client.get(`/dashboard/${dashboardId}/widgets/`)
    },
    create(dashboardId, widget = {}) {
      return client.post(`/dashboard/${dashboardId}/widgets/`, {
        ...widget,
      })
    },
    update(widgetId, values = {}) {
      return client.patch(`/dashboard/widgets/${widgetId}/`, values)
    },
    updateLayout(dashboardId, widgets) {
      return client.patch(`/dashboard/${dashboardId}/widgets/layout/`, {
        widgets,
      })
    },
    deleteWithLayout(dashboardId, widgetId, widgets) {
      return client.post(`/dashboard/${dashboardId}/widgets/layout/delete/`, {
        widget_id: widgetId,
        widgets,
      })
    },
    delete(widgetId) {
      return client.delete(`/dashboard/widgets/${widgetId}/`)
    },
  }
}
