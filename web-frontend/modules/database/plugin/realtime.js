import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'database-realtime',
  dependsOn: ['realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/database/plugin/realtimeApplication')
      await registerApplication(nuxtApp)
    }
  },
})
