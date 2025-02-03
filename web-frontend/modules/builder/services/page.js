export default (client) => {
  return {
    create(builderId, name, path, pathParams = {}, queryParams = {}) {
      return client.post(`builder/${builderId}/pages/`, {
        name,
        path,
        path_params: pathParams,
        query_params: queryParams,
      })
    },
    update(pageId, values) {
      return client.patch(`builder/pages/${pageId}/`, values)
    },
    delete(pageId) {
      return client.delete(`builder/pages/${pageId}/`)
    },
    order(builderId, order) {
      return client.post(`/builder/${builderId}/pages/order/`, {
        page_ids: order,
      })
    },
    duplicate(pageId) {
      return client.post(`/builder/pages/${pageId}/duplicate/async/`)
    },
  }
}
