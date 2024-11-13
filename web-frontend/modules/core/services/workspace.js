import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(
    baseService(
      client,
      ({ workspaceId }) => `/workspaces/users/workspace/${workspaceId}/`,
      false
    ),
    {
      fetchAll() {
        return client.get('/workspaces/')
      },
      order(order) {
        return client.post('/workspaces/order/', {
          workspaces: order,
        })
      },
      create(values) {
        return client.post('/workspaces/', values)
      },
      update(id, values) {
        return client.patch(`/workspaces/${id}/`, values)
      },
      leave(id) {
        return client.post(`/workspaces/${id}/leave/`)
      },
      delete(id) {
        return client.delete(`/workspaces/${id}/`)
      },
      sendInvitation(workspaceId, baseUrl, values) {
        values.base_url = baseUrl
        return client.post(
          `/workspaces/invitations/workspace/${workspaceId}/`,
          values
        )
      },
      fetchAllUsers(workspaceId) {
        return client.get(`/workspaces/users/workspace/${workspaceId}/`)
      },
      updateUser(workspaceUserId, values) {
        return client.patch(`/workspaces/users/${workspaceUserId}/`, values)
      },
      deleteUser(workspaceUserId) {
        return client.delete(`/workspaces/users/${workspaceUserId}/`)
      },
      fetchAllInvitations(workspaceId) {
        return client.get(`/workspaces/invitations/workspace/${workspaceId}/`)
      },
      fetchInvitationByToken(token) {
        return client.get(`/workspaces/invitations/token/${token}/`)
      },
      updateInvitation(invitationId, values) {
        return client.patch(`/workspaces/invitations/${invitationId}/`, values)
      },
      deleteInvitation(invitationId) {
        return client.delete(`/workspaces/invitations/${invitationId}/`)
      },
      rejectInvitation(invitationId) {
        return client.post(`/workspaces/invitations/${invitationId}/reject/`)
      },
      acceptInvitation(invitationId) {
        return client.post(`/workspaces/invitations/${invitationId}/accept/`)
      },
      getGenerativeAISettings(workspaceId) {
        return client.get(`/workspaces/${workspaceId}/settings/generative-ai/`)
      },
      updateGenerativeAISettings(workspaceId, values) {
        return client.patch(
          `/workspaces/${workspaceId}/settings/generative-ai/`,
          values
        )
      },
      createInitialWorkspace(values) {
        return client.post('/workspaces/create-initial-workspace/', values)
      },
    }
  )
}
