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
    delete(widgetId) {
      return client.delete(`/dashboard/widgets/${widgetId}/`)
    },
  }
}
