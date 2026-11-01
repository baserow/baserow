export default (client) => {
  return {
    assignRole(
      subjectId,
      subjectType,
      workspaceId,
      scopeId,
      scopeType,
      roleUid
    ) {
      return client.post(`/role/${workspaceId}/`, {
        subject_id: subjectId,
        subject_type: subjectType,
        scope_id: scopeId,
        scope_type: scopeType,
        role: roleUid,
      })
    },
    assignRoleBatch(workspaceId, items) {
      return client.post(`/role/${workspaceId}/batch/`, {
        items,
      })
    },
    getRoleAssignments(workspaceId, scopeId, scopeType) {
      return client.get(`/role/${workspaceId}/`, {
        params: {
          scope_id: scopeId,
          scope_type: scopeType,
        },
      })
    },
    getSubjectRoleAssignments(
      workspaceId,
      subjectType,
      subjectId,
      { offset = 0, limit = 10 } = {}
    ) {
      return client.get(`/role/${workspaceId}/subject-role-assignments/`, {
        params: {
          subject_type: subjectType,
          subject_id: subjectId,
          offset,
          limit,
        },
      })
    },
    getEffectiveAccess(workspaceId, scopeId, scopeType) {
      return client.get(`/role/${workspaceId}/effective-access/`, {
        params: {
          scope_id: scopeId,
          scope_type: scopeType,
        },
      })
    },
    createScopedInvitation(
      workspaceId,
      { email, roleUid, scopeId, scopeType, captchaToken = '' }
    ) {
      const values = {
        email,
        role: roleUid,
        scope_id: scopeId,
        scope_type: scopeType,
      }
      if (captchaToken) {
        values.captcha_token = captchaToken
      }
      return client.post(`/role/${workspaceId}/invitations/`, values)
    },
    getScopedInvitations(workspaceId, scopeId, scopeType) {
      return client.get(`/role/${workspaceId}/invitations/`, {
        params: {
          scope_id: scopeId,
          scope_type: scopeType,
        },
      })
    },
    updateScopedInvitation(scopedInvitationId, roleUid) {
      return client.patch(`/role/invitations/${scopedInvitationId}/`, {
        role: roleUid,
      })
    },
    deleteScopedInvitation(scopedInvitationId) {
      return client.delete(`/role/invitations/${scopedInvitationId}/`)
    },
  }
}
