export default (client) => {
  return {
    getAllDataSources(dashboardId) {
      return client.get(`/dashboard/${dashboardId}/data-sources/`)
    },
    update(dataSourceId, values = {}) {
      return client.patch(`/dashboard/data-sources/${dataSourceId}/`, values)
    },
    dispatch(dataSourceId) {
      return client.post(`/dashboard/data-sources/${dataSourceId}/dispatch/`)
    },
  }
}
