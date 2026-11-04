import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'dashboard',
  dependsOn: ['core', 'store', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/dashboard/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
