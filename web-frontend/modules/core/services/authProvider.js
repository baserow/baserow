export default (client) => {
  return {
    async fetchLoginOptions() {
      return client.get('/auth-provider/login-options/')
    },
  }
}
