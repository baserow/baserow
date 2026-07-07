export default (client) => {
  return {
    fetchAll(viewId) {
      return client.get(`/database/views/${viewId}/sortings/`)
    },
    create(viewId, values) {
      return client.post(`/database/views/${viewId}/sortings/`, values)
    },
    get(viewSortId) {
      return client.get(`/database/views/sort/${viewSortId}/`)
    },
    update(viewSortId, values) {
      return client.patch(`/database/views/sort/${viewSortId}/`, values)
    },
    delete(viewSortId) {
      return client.delete(`/database/views/sort/${viewSortId}/`)
    },
    prioritize(viewId, viewSortIds) {
      return client.post(`/database/views/${viewId}/sortings/prioritize/`, {
        view_sort_ids: viewSortIds,
      })
    },
  }
}
