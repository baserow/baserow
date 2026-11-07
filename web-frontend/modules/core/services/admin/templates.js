import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(baseService(client, '/admin/templates/'), {
    // The number of templates in each state of the admin page.
    counts() {
      return client.get('/admin/templates/counts/')
    },
    // The state and listing the admin saw, refused if changed since.
    approve(templateId, revisionId, state, listed) {
      return client.post(`/admin/templates/${templateId}/approve/`, {
        revision_id: revisionId,
        state,
        listed,
      })
    },
    reject(templateId, revisionId, reason, state, listed) {
      return client.post(`/admin/templates/${templateId}/reject/`, {
        revision_id: revisionId,
        reason,
        state,
        listed,
      })
    },
  })
}
