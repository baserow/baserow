import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'automation-realtime',
  dependsOn: ['realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/automation/plugins/realtimeApplication')
      await registerApplication(nuxtApp)
    }
  },
})
