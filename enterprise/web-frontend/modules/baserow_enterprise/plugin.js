import { defineNuxtPlugin } from '#app'
import registerRuntime from '@baserow_enterprise/pluginRuntime'

export default defineNuxtPlugin({
  name: 'enterprise',
  dependsOn: ['premium', 'registry', 'feature-flags', 'application-shell'],
  async setup(nuxtApp) {
    await registerRuntime(nuxtApp)
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow_enterprise/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
