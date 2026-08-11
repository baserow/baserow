import baseService from '@baserow/modules/core/crudTable/baseService'

export const ADMIN_WORKSPACE_OPTIONS_URL = '/admin/workspaces/options/'

export const fetchWorkspaceOptions = (client, page, search) =>
  baseService(client, ADMIN_WORKSPACE_OPTIONS_URL).fetch(
    ADMIN_WORKSPACE_OPTIONS_URL,
    page,
    search,
    [],
    {}
  )

export default (client) => {
  return Object.assign(baseService(client, '/admin/workspaces/'), {
    delete(workspaceId) {
      return client.delete(`/admin/workspaces/${workspaceId}/`)
    },
  })
}
