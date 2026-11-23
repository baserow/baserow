import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'enterprise-realtime',
  dependsOn: ['realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow_enterprise/plugins/realtimeApplication')
      await registerApplication(nuxtApp)
    }
  },
})
