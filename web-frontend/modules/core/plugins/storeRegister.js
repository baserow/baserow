export default defineNuxtPlugin({
  name: 'store',
  dependsOn: ['create-store', 'client-handler', 'core', 'i18n'],
  async setup(nuxtApp) {
    const { $store, $i18n, $config, $client, $registry, runWithContext } =
      nuxtApp

    $store.app = nuxtApp
    $store.$i18n = $i18n
    $store.$config = $config
    $store.$client = $client
    $store.$registry = $registry
    $store.runWithContext = runWithContext
  },
})
