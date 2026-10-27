export default (client) => ({
  fetchAll(dashboardId) {
    return client.get(`/dashboard/${dashboardId}/filters/`)
  },
  create(dashboardId, values) {
    return client.post(`/dashboard/${dashboardId}/filters/`, values)
  },
  order(dashboardId, order) {
    return client.post(`/dashboard/${dashboardId}/filters/order/`, { order })
  },
  update(filterId, values) {
    return client.patch(`/dashboard/filters/${filterId}/`, values)
  },
  delete(filterId) {
    return client.delete(`/dashboard/filters/${filterId}/`)
  },
  options(filterId, values) {
    return client.post(`/dashboard/filters/${filterId}/options/`, values)
  },
})
