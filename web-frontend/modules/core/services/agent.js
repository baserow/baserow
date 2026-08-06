import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) =>
  Object.assign(
    baseService(
      client,
      ({ workspaceId }) => `/agents/workspace/${workspaceId}/`
    ),
    {
      create(workspaceId, values) {
        return client.post(`/agents/workspace/${workspaceId}/`, values)
      },
      list(workspaceId) {
        return client.get(`/agents/workspace/${workspaceId}/`, {
          params: { size: 200 },
        })
      },
      update(agentId, values) {
        return client.patch(`/agents/${agentId}/`, values)
      },
      delete(agentId) {
        return client.delete(`/agents/${agentId}/`)
      },
    }
  )
