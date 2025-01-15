export default (client) => {
  return {
    getPeriodicInterval(dataSyncId) {
      return client.get(`/data-sync/${dataSyncId}/periodic-interval/`)
    },
    updatePeriodicInterval(dataSyncId, interval, when, automaticallyDeactivated) {
      return client.patch(`/data-sync/${dataSyncId}/periodic-interval/`, {
        interval,
        when,
        automatically_deactivated: automaticallyDeactivated,
      })
    },
  }
}
