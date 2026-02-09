export default defineNuxtPlugin((nuxtApp) => {
  const hasFeature = (feature, forSpecificWorkspace) =>
    Object.values(nuxtApp.$registry.getAll('plugin')).some((plugin) =>
      plugin.hasFeature(feature, forSpecificWorkspace)
    )

  nuxtApp.provide('hasFeature', hasFeature)
})
