export default (client) => {
  return {
    fetchAll(databaseId) {
      return client.get(`/database/tables/database/${databaseId}/`)
    },
    create(
      databaseId,
      values,
      initialData = null,
      firstRowHeader = false,
      config = null
    ) {
      if (initialData !== null) {
        values.data = initialData
        values.first_row_header = firstRowHeader
      }

      return client.post(
        `/database/tables/database/${databaseId}/async/`,
        values,
        config
      )
    },
    createSync(databaseId, values, initialData = null, firstRowHeader = false) {
      if (initialData !== null) {
        values.data = initialData
        values.first_row_header = firstRowHeader
      }

      return client.post(`/database/tables/database/${databaseId}/`, values)
    },
    importData(tableId, data, config = null, importConfiguration = null) {
      const payload = { data }
      if (importConfiguration) {
        payload.configuration = importConfiguration
      }

      return client.post(
        `/database/tables/${tableId}/import/async/`,
        payload,
        config
      )
    },
    get(tableId) {
      return client.get(`/database/tables/${tableId}/`)
    },
    update(tableId, values) {
      return client.patch(`/database/tables/${tableId}/`, values)
    },
    order(databaseId, order) {
      return client.post(`/database/tables/database/${databaseId}/order/`, {
        table_ids: order,
      })
    },
    asyncDuplicate(tableId) {
      return client.post(`/database/tables/${tableId}/duplicate/async/`)
    },
    delete(tableId) {
      return client.delete(`/database/tables/${tableId}/`)
    },
  }
}
