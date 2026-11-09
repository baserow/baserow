import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'
import { defineNuxtPlugin } from '#app'
import registerRuntime from '@baserow_premium/pluginRuntime'

export default defineNuxtPlugin({
  name: 'premium',
  dependsOn: [
    'core',
    'builder',
    'database',
    'dashboard',
    'automation',
    'agent',
    'client-handler',
    'application-shell',
  ],
  async setup(nuxtApp) {
    await registerRuntime(nuxtApp)
    registerApplicationBundle(nuxtApp, 'database', async (app) => {
      const bundle = await import('@baserow_premium/databaseBundle')
      await bundle.default(app)
      return bundle.getComponents()
    })
    registerApplicationBundle(nuxtApp, 'dashboard', async (app) => {
      const bundle = await import('@baserow_premium/dashboardBundle')
      await bundle.default(app)
      return bundle
    })
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow_premium/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
