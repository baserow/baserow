import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'database',
  dependsOn: ['core', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/database/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
