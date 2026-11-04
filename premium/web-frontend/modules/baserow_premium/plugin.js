import { defineNuxtPlugin } from '#app'
import registerRuntime from '@baserow_premium/pluginRuntime'

export default defineNuxtPlugin({
  name: 'premium',
  dependsOn: [
    'core',
    'builder',
    'database',
    'client-handler',
    'application-shell',
  ],
  async setup(nuxtApp) {
    await registerRuntime(nuxtApp)
    if (nuxtApp.$isApplicationShell !== false) {
      const { default: registerApplication } =
        await import('@baserow_premium/pluginApplication')
      await registerApplication(nuxtApp)
    }
  },
})
