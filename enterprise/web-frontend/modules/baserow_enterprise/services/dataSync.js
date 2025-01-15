export default (client) => {
  return {
    getPeriodicInterval(dataSyncId) {
      return client.get(`/data-sync/${dataSyncId}/periodic-interval/`)
    },
    updatePeriodicInterval(dataSyncId, interval, when) {
      return client.patch(`/data-sync/${dataSyncId}/periodic-interval/`, {
        interval,
        when,
      })
    },
  }
}
