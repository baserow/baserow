import { loadApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'

/** Routes initialize their feature before named middleware selects its data. */
export default defineNuxtRouteMiddleware(async (to) => {
  if (to.meta.applicationBundle) {
    await loadApplicationBundle(useNuxtApp(), to.meta.applicationBundle)
  }
})
