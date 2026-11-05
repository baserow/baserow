import { defineNuxtPlugin } from '#app'
import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'

export default defineNuxtPlugin({
  name: 'database',
  dependsOn: ['core', 'store', 'realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerMetadata } =
        await import('@baserow/modules/database/pluginMetadata')
      await registerMetadata(nuxtApp)
    }
    registerApplicationBundle(nuxtApp, 'database', async (app) => {
      if (!app.$registry.getAll('application')['database']) {
        const { default: registerMetadata } =
          await import('@baserow/modules/database/pluginMetadata')
        await registerMetadata(app)
      }
      const bundle = await import('@baserow/modules/database/applicationBundle')
      await bundle.default(app)
      return bundle
    })
  },
})
