import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(baseService(client, '/admin/users/'), {
    update(userId, values) {
      return client.patch(`/admin/users/${userId}/`, values)
    },
    delete(userId) {
      return client.delete(`/admin/users/${userId}/`)
    },
    impersonate(userId) {
      return client.post(`/admin/users/impersonate/`, {
        user: userId,
      })
    },
  })
}
