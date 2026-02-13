import { registerRealtimeEvents } from '@baserow/modules/database/realtime'

export default defineNuxtPlugin({
  name: 'database-realtime',
  dependsOn: ['realtime'],
  async setup(nuxtApp) {
    registerRealtimeEvents(nuxtApp.$realtime)
  },
})
