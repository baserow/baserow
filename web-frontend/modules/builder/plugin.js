import { defineNuxtPlugin } from '#app'
import registerRuntime from '@baserow/modules/builder/pluginRuntime'

export default defineNuxtPlugin({
  name: 'builder',
  dependsOn: ['core', 'store', 'application-shell'],
  async setup(nuxtApp) {
    await registerRuntime(nuxtApp)
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow/modules/builder/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
