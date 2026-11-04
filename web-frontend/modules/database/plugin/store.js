import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'database-store',
  dependsOn: ['store', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/database/plugin/storeApplication')
      await registerApplication(nuxtApp)
    }
  },
})
