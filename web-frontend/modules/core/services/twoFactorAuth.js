export default (client) => {
  return {
    configure(type, enabled) {
      return client.post('/two-factor-auth/configuration/', { type, enabled })
    },
    getConfiguration() {
      return client.get('/two-factor-auth/configuration/')
    },
  }
}
