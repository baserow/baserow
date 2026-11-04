import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'premium-realtime',
  dependsOn: ['realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow_premium/plugins/realtimeApplication')
      await registerApplication(nuxtApp)
    }
  },
})
