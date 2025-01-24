export default (client) => {
  return {
    get(dataSyncId) {
      return client.get(`/database/data-sync/${dataSyncId}/`)
    },
    create(databaseId, values) {
      return client.post(`/database/data-sync/database/${databaseId}/`, values)
    },
    update(dataSyncId, values) {
      return client.patch(`/database/data-sync/${dataSyncId}/`, values)
    },
    syncTable(dataSyncId) {
      return client.post(`/database/data-sync/${dataSyncId}/sync/async/`)
    },
    fetchProperties(values) {
      return client.post(`/database/data-sync/properties/`, values)
    },
    fetchPropertiesOfDataSync(dataSyncId) {
      return client.get(`/database/data-sync/${dataSyncId}/properties/`)
    },
  }
}
