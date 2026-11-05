import { defineNuxtPlugin } from '#app'
import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'

export default defineNuxtPlugin({
  name: 'agent',
  dependsOn: ['core', 'store', 'application-shell'],
  async setup(nuxtApp) {
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerMetadata } =
        await import('@baserow/modules/agent/pluginMetadata')
      await registerMetadata(nuxtApp)
    }
    registerApplicationBundle(nuxtApp, 'agent', async (app) => {
      if (!app.$registry.getAll('application')['agent']) {
        const { default: registerMetadata } =
          await import('@baserow/modules/agent/pluginMetadata')
        await registerMetadata(app)
      }
      const bundle = await import('@baserow/modules/agent/applicationBundle')
      await bundle.default(app)
      return bundle
    })
  },
})
