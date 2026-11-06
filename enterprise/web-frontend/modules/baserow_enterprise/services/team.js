import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(
    baseService(
      client,
      ({ workspaceId }) => `/teams/workspace/${workspaceId}/`,
      false
    ),
    {
      get(id) {
        return client.get(`/teams/${id}/`)
      },
      fetchAll(workspaceId) {
        return client.get(`/teams/workspace/${workspaceId}/`)
      },
      create(workspaceId, values) {
        return client.post(`/teams/workspace/${workspaceId}/`, values)
      },
      update(id, values) {
        return client.put(`/teams/${id}/`, values)
      },
      delete(id) {
        return client.delete(`/teams/${id}/`)
      },
      createSubject(teamId, values) {
        return client.post(`/teams/${teamId}/subjects/`, values)
      },
      fetchAllSubjects(teamId) {
        return client.get(`/teams/${teamId}/subjects/`)
      },
      deleteSubject(teamId, subjectId) {
        return client.delete(`/teams/${teamId}/subjects/${subjectId}/`)
      },
      fetchInvitations(teamId) {
        return client.get(`/teams/${teamId}/invitations/`)
      },
      createInvitation(teamId, { email, captchaToken }) {
        const values = { email }
        if (captchaToken) {
          values.captcha_token = captchaToken
        }
        return client.post(`/teams/${teamId}/invitations/`, values)
      },
      deleteInvitation(teamId, teamInvitationId) {
        return client.delete(
          `/teams/${teamId}/invitations/${teamInvitationId}/`
        )
      },
    }
  )
}
