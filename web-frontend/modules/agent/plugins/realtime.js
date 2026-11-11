import { registerRealtimeEvents } from '@baserow/modules/agent/realtime'

export default defineNuxtPlugin({
  name: 'agent-realtime',
  dependsOn: ['realtime'],
  setup(nuxtApp) {
    registerRealtimeEvents(nuxtApp.$realtime)
  },
})
