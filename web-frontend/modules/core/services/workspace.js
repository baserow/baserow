import baseService from '@baserow/modules/core/crudTable/baseService'
import { getRealtimeRecoveryRequestConfig } from '@baserow/modules/core/plugins/realtimeProtocol'

export default (client) => {
  return Object.assign(
    baseService(
      client,
      ({ workspaceId }) => `/workspaces/users/workspace/${workspaceId}/`,
      false
    ),
    {
      fetchAll(realtimeRecovery = false) {
        return client.get(
          '/workspaces/',
          realtimeRecovery ? getRealtimeRecoveryRequestConfig() : {}
        )
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
      sendInvitation(workspaceId, { captchaToken = '', ...values }) {
        if (captchaToken) {
          values.captcha_token = captchaToken
        }
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
      acceptInvitation(invitationId, token = null) {
        return client.post(
          `/workspaces/invitations/${invitationId}/accept/`,
          token ? { token } : {}
        )
      },
      fetchAllInvitationLinks(workspaceId) {
        return client.get(
          `/workspaces/invitation-links/workspace/${workspaceId}/`
        )
      },
      createInvitationLink(workspaceId, values) {
        return client.post(
          `/workspaces/invitation-links/workspace/${workspaceId}/`,
          values
        )
      },
      updateInvitationLink(invitationLinkId, values) {
        return client.patch(
          `/workspaces/invitation-links/${invitationLinkId}/`,
          values
        )
      },
      deleteInvitationLink(invitationLinkId) {
        return client.delete(
          `/workspaces/invitation-links/${invitationLinkId}/`
        )
      },
      fetchInvitationLinkBySlug(slug) {
        return client.get(
          `/workspaces/invitation-links/slug/${encodeURIComponent(slug)}/`
        )
      },
      joinInvitationLink(slug) {
        return client.post(
          `/workspaces/invitation-links/slug/${encodeURIComponent(slug)}/join/`
        )
      },
      createInitialWorkspace(values) {
        return client.post('/workspaces/create-initial-workspace/', values)
      },
    }
  )
}
