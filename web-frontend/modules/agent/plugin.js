import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'agent',
  dependsOn: ['core', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/agent/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
