import { registerRealtimeEvents } from '@baserow/modules/whiteboard/realtime'

export default defineNuxtPlugin({
  name: 'whiteboard-realtime',
  dependsOn: ['realtime'],
  async setup(nuxtApp) {
    registerRealtimeEvents(nuxtApp.$realtime)
  },
})
