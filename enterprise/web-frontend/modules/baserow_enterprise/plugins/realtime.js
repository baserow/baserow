import { registerRealtimeEvents } from '@baserow_enterprise/realtime'

export default defineNuxtPlugin({
  name: 'enterprise-realtime',
  dependsOn: ['realtime'],
  async setup(nuxtApp) {
    registerRealtimeEvents(nuxtApp.$realtime)
  },
})
