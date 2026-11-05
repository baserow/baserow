import { registerFeatureBundle } from '@baserow/modules/core/utils/featureBundles'
import { defineNuxtPlugin } from '#app'
import registerRuntime from '@baserow/modules/core/pluginRuntime'

export default defineNuxtPlugin({
  name: 'core',
  dependsOn: ['priorityBus', 'registry', 'i18n', 'application-shell'],
  async setup(nuxtApp) {
    registerFeatureBundle(nuxtApp, 'onboarding', async (app) => {
      const bundle = await import('@baserow/modules/core/onboardingBundle')
      await bundle.default(app)
      return bundle
    })

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
