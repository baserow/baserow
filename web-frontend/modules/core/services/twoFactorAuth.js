export default (client) => {
  return {
    configure(type, params) {
      return client.post('/two-factor-auth/configuration/', { type, ...params })
    },
    getConfiguration() {
      return client.get('/two-factor-auth/configuration/')
    },
    disable(password) {
      return client.post('/two-factor-auth/disable/', { password })
    },
    verify(type, email, token, params) {
      return client.post(
        '/two-factor-auth/verify/',
        { type, email, ...params },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
    },
  }
}
