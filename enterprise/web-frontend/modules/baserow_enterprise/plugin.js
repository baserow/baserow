import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'
import { defineNuxtPlugin } from '#app'
import registerRuntime from '@baserow_enterprise/pluginRuntime'

export default defineNuxtPlugin({
  name: 'enterprise',
  dependsOn: ['premium', 'registry', 'feature-flags', 'application-shell'],
  async setup(nuxtApp) {
    await registerRuntime(nuxtApp)
    registerApplicationBundle(nuxtApp, 'database', async (app) => {
      const bundle = await import('@baserow_enterprise/databaseBundle')
      await bundle.default(app)
      return bundle
    })
    registerApplicationBundle(nuxtApp, 'builder', async (app) => {
      const bundle = await import('@baserow_enterprise/builderBundle')
      await bundle.default(app)
      return bundle
    })
    registerApplicationBundle(nuxtApp, 'automation', async (app) => {
      const bundle = await import('@baserow_enterprise/automationBundle')
      await bundle.default(app)
      return bundle
    })
    if (
      nuxtApp.$isApplicationShell !== false ||
      nuxtApp.$isAuthenticationPage
    ) {
      const { default: registerAuthentication } =
        await import('@baserow_enterprise/pluginAuthentication')
      await registerAuthentication(nuxtApp)
    }
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow_enterprise/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
