export default (client) => {
  return {
    get(fieldId) {
      return client.get(`/field-permissions/${fieldId}/`)
    },
    update(fieldId, { role, allowInForms }) {
      const data = {}
      if (role !== undefined) {
        data.role = role
      }
      if (allowInForms !== undefined) {
        data.allow_in_forms = allowInForms
      }
      return client.patch(`/field-permissions/${fieldId}/`, data)
    },
  }
}
