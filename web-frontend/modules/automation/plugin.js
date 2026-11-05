import { defineNuxtPlugin } from '#app'
import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'

export default defineNuxtPlugin({
  name: 'automation',
  dependsOn: ['core', 'store', 'realtime', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerMetadata } =
        await import('@baserow/modules/automation/pluginMetadata')
      await registerMetadata(nuxtApp)
    }
    registerApplicationBundle(nuxtApp, 'automation', async (app) => {
      if (!app.$registry.getAll('application')['automation']) {
        const { default: registerMetadata } =
          await import('@baserow/modules/automation/pluginMetadata')
        await registerMetadata(app)
      }
      const bundle =
        await import('@baserow/modules/automation/applicationBundle')
      await bundle.default(app)
      return bundle
    })
  },
})
