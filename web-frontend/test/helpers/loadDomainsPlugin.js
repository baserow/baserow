// Tests never run route middleware, so load every lazy registry domain at boot.
export default defineNuxtPlugin({
  name: 'test-load-domains',
  enforce: 'post',
  async setup(nuxtApp) {
    const { $registry } = nuxtApp
    await Promise.all(
      Object.keys($registry.domainLoaders).map((domain) =>
        $registry.loadDomain(domain)
      )
    )
  },
})
