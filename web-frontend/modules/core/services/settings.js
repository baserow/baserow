export default (client) => {
  return {
    get() {
      return client.get('/settings/')
    },
    getInstanceID() {
      return client.get('/settings/instance-id/')
    },
    update(values) {
      return client.patch('/settings/update/', values)
    },
  }
}
