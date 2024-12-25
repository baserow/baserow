import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(baseService(client, '/admin/workspaces/'), {
    delete(workspaceId) {
      return client.delete(`/admin/workspaces/${workspaceId}/`)
    },
  })
}
