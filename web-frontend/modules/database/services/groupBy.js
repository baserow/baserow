export default (client) => {
  return {
    fetchAll(viewId) {
      return client.get(`/database/views/${viewId}/group_bys/`)
    },
    create(viewId, values) {
      return client.post(`/database/views/${viewId}/group_bys/`, values)
    },
    get(viewGroupById) {
      return client.get(`/database/views/group_by/${viewGroupById}/`)
    },
    update(viewGroupById, values) {
      return client.patch(`/database/views/group_by/${viewGroupById}/`, values)
    },
    delete(viewGroupById) {
      return client.delete(`/database/views/group_by/${viewGroupById}/`)
    },
    prioritize(viewId, viewGroupByIds) {
      return client.post(`/database/views/${viewId}/group_bys/prioritize/`, {
        view_group_by_ids: viewGroupByIds,
      })
    },
  }
}
