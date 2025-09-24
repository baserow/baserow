export default (client) => {
  return {
    configure(type, enabled) {
      return client.post('/two-factor-auth/configuration/', { type, enabled })
    },
  }
}
