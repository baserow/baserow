/*export default function ({ app }, inject) {
  const { $registry } = app
  function hasFeature(feature, forSpecificWorkspace) {
    return Object.values($registry.getAll('plugin')).some((p) =>
      p.hasFeature(feature, forSpecificWorkspace)
    )
  }
  inject('hasFeature', hasFeature)
}
*/

export default defineNuxtPlugin((nuxtApp) => {
  const hasFeature = (feature, forSpecificWorkspace) =>
    Object.values(nuxtApp.$registry.getAll('plugin')).some((plugin) =>
      plugin.hasFeature(feature, forSpecificWorkspace)
    )

  nuxtApp.provide('hasFeature', hasFeature)
})
