export default (client) => {
  return {
    get(config = {}) {
      return client.get('/settings/', config)
    },
    getInstanceID() {
      return client.get('/settings/instance-id/')
    },
    update(values) {
      return client.patch('/settings/update/', values)
    },
  }
}
