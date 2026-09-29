import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(baseService(client, '/database/admin/views/'), {
    update(viewId, values) {
      return client.patch(`/database/admin/views/${viewId}/`, values)
    },
    rotateSlug(viewId) {
      return client.post(`/database/admin/views/${viewId}/rotate-slug/`)
    },
  })
}
