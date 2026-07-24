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
    fetchSyncJobs(dataSyncId, { limit = 10, offset = 0, states = null } = {}) {
      const params = {
        type: 'sync_data_sync_table',
        sync_data_sync_table_data_sync_id: dataSyncId,
        limit,
        offset,
      }
      if (states) {
        params.states = states.join(',')
      }
      return client.get(`/jobs/`, { params })
    },
    fetchProperties(values) {
      return client.post(`/database/data-sync/properties/`, values)
    },
    fetchPropertiesOfDataSync(dataSyncId) {
      return client.get(`/database/data-sync/${dataSyncId}/properties/`)
    },
  }
}
