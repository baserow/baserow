import { registerRealtimeEvents } from '@baserow_premium/realtime'

export default defineNuxtPlugin({
  name: 'premium-realtime',
  dependsOn: ['realtime'],
  async setup(nuxtApp) {
    registerRealtimeEvents(nuxtApp.$realtime)
  },
})
