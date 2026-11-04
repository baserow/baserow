import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'agent-realtime',
  dependsOn: ['realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/agent/plugins/realtimeApplication')
      await registerApplication(nuxtApp)
    }
  },
})
