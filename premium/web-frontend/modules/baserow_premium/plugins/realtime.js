import { defineNuxtPlugin } from '#app'
import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'

export default defineNuxtPlugin({
  name: 'premium-realtime',
  dependsOn: ['realtime', 'premium'],
  setup(nuxtApp) {
    registerApplicationBundle(nuxtApp, 'database', async (app) => {
      const { default: register } =
        await import('@baserow_premium/plugins/realtimeApplication')
      await register(app)
    })
  },
})
