import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(baseService(client, '/admin/templates/'), {
    counts() {
      return client.get('/admin/templates/counts/')
    },
    approve(templateId, revisionId, state, listed, reviewedOn) {
      return client.post(`/admin/templates/${templateId}/approve/`, {
        revision_id: revisionId,
        state,
        listed,
        reviewed_on: reviewedOn,
      })
    },
    reject(templateId, revisionId, reason, state, listed, reviewedOn) {
      return client.post(`/admin/templates/${templateId}/reject/`, {
        revision_id: revisionId,
        reason,
        state,
        listed,
        reviewed_on: reviewedOn,
      })
    },
    block(templateId, reason) {
      return client.post(`/admin/templates/${templateId}/block/`, { reason })
    },
    unblock(templateId) {
      return client.post(`/admin/templates/${templateId}/unblock/`)
    },
  })
}
