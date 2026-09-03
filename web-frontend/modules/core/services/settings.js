import { getRealtimeRecoveryRequestConfig } from '@baserow/modules/core/plugins/realtimeProtocol'

export default (client) => {
  return {
    get(realtimeRecovery = false) {
      return client.get(
        '/settings/',
        realtimeRecovery ? getRealtimeRecoveryRequestConfig() : {}
      )
    },
    getInstanceID() {
      return client.get('/settings/instance-id/')
    },
    update(values) {
      return client.patch('/settings/update/', values)
    },
  }
}
