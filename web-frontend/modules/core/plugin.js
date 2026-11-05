import { defineNuxtPlugin } from '#app'
import registerRuntime from '@baserow/modules/core/pluginRuntime'

export default defineNuxtPlugin({
  name: 'core',
  dependsOn: ['priorityBus', 'registry', 'i18n', 'application-shell'],
  async setup(nuxtApp) {
    await registerRuntime(nuxtApp)
    if (
      nuxtApp.$isApplicationShell !== false ||
      nuxtApp.$isAuthenticationPage
    ) {
      const { default: registerAuthentication } =
        await import('@baserow/modules/core/pluginAuthentication')
      await registerAuthentication(nuxtApp)
    }
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/core/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
