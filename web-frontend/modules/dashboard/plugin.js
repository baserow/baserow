import { defineNuxtPlugin } from '#app'
import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'

export default defineNuxtPlugin({
  name: 'dashboard',
  dependsOn: ['core', 'store', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerMetadata } =
        await import('@baserow/modules/dashboard/pluginMetadata')
      await registerMetadata(nuxtApp)
    }
    registerApplicationBundle(nuxtApp, 'dashboard', async (app) => {
      if (!app.$registry.getAll('application')['dashboard']) {
        const { default: registerMetadata } =
          await import('@baserow/modules/dashboard/pluginMetadata')
        await registerMetadata(app)
      }
      const bundle =
        await import('@baserow/modules/dashboard/applicationBundle')
      await bundle.default(app)
      return bundle
    })
  },
})
