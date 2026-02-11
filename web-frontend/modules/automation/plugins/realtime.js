import { registerRealtimeEvents } from '@baserow/modules/automation/realtime'

export default defineNuxtPlugin({
  name: 'automation-realtime',
  dependsOn: ['realtime'],
  async setup(nuxtApp) {
    registerRealtimeEvents(nuxtApp.$realtime)
  },
})
