import { loadFeatureBundle } from '@baserow/modules/core/utils/featureBundles'

/** Initialize route features before named middleware selects data or renders UI. */
export default defineNuxtRouteMiddleware(async (to) => {
  const feature = to.meta.applicationBundle || to.meta.featureBundle
  if (feature) await loadFeatureBundle(useNuxtApp(), feature)
})
