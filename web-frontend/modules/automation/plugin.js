import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'automation',
  dependsOn: ['core', 'store', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/automation/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
