export default (client) => {
  return {
    get(fieldId) {
      return client.get(`/field-permissions/${fieldId}/`)
    },
    fetchSubjectOptions(fieldId, params) {
      return client.get(`/field-permissions/${fieldId}/subjects/`, { params })
    },
    update(fieldId, { role, allowInForms, subjects }) {
      const data = {}
      if (role !== undefined) {
        data.role = role
      }
      if (allowInForms !== undefined) {
        data.allow_in_forms = allowInForms
      }
      if (subjects !== undefined) {
        data.subjects = subjects
      }
      return client.patch(`/field-permissions/${fieldId}/`, data)
    },
  }
}
