import { useNuxtApp, useRuntimeConfig } from '#imports'

export default defineNuxtPlugin({
  name: 'enterprise-extra-client-script-runtime',
  dependsOn: ['enterprise'],
  setup() {
    if (!import.meta.client) return

    if (!window.__baserow) return

    const nuxtApp = useNuxtApp()
    const runtimeConfig = useRuntimeConfig()
    const queuedHooks = window.__baserow._queuedHooks || []

    window.__baserow = {
      ...window.__baserow,
      $router: nuxtApp.$router,
      config: runtimeConfig.public,
      hook: (name, fn) => nuxtApp.hook(name, fn),
    }

    for (const [name, fn] of queuedHooks) {
      nuxtApp.hook(name, fn)
    }

    delete window.__baserow._queuedHooks
  },
})
