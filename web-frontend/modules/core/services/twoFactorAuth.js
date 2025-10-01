export default (client) => {
  return {
    configure(type, params) {
      return client.post('/two-factor-auth/configuration/', { type, ...params })
    },
    getConfiguration() {
      return client.get('/two-factor-auth/configuration/')
    },
    disable(password) {
      // TODO:
    },
  }
}
