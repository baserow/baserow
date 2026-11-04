import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'dashboard-realtime',
  dependsOn: ['realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/dashboard/plugins/realtimeApplication')
      await registerApplication(nuxtApp)
    }
  },
})
