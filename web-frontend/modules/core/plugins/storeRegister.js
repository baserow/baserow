export default defineNuxtPlugin({
  name: 'store',
  dependsOn: [
    'create-store',
    'vuex-state',
    'client-handler',
    'core',
    'i18n',
    'bus',
  ],
  async setup(nuxtApp) {
    const {
      $store,
      $i18n,
      $config,
      $client,
      $registry,
      $router,
      $bus,
      runWithContext,
    } = nuxtApp

    $store.app = nuxtApp
    $store.$i18n = $i18n
    $store.$config = $config
    $store.$client = $client
    $store.$registry = $registry
    $store.$router = $router
    $store.$bus = $bus
    $store.runWithContext = runWithContext
  },
})
