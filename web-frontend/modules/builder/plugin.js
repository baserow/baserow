import { defineNuxtPlugin } from '#app'
import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'
import registerRuntime from '@baserow/modules/builder/pluginRuntime'

export default defineNuxtPlugin({
  name: 'builder',
  dependsOn: ['core', 'store', 'application-shell'],
  async setup(nuxtApp) {
    await registerRuntime(nuxtApp)
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerMetadata } =
        await import('@baserow/modules/builder/pluginMetadata')
      await registerMetadata(nuxtApp)
    }
    registerApplicationBundle(nuxtApp, 'builder', async (app) => {
      if (!app.$registry.getAll('application')['builder']) {
        const { default: registerMetadata } =
          await import('@baserow/modules/builder/pluginMetadata')
        await registerMetadata(app)
      }
      const bundle = await import('@baserow/modules/builder/applicationBundle')
      await bundle.default(app)
      return bundle
    })
  },
})
