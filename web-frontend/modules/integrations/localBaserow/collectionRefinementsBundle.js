import { defineComponent, h } from 'vue'
import { useNuxtApp } from '#app'
import LocalBaserowAdhocHeader from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowAdhocHeader.vue'
import { loadApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'

/** Public refinement controls explicitly request the shared Database feature. */
export async function loadCollectionRefinements(app) {
  await loadApplicationBundle(app, 'database')
  return LocalBaserowAdhocHeader
}

// Async component loaders are cached across SSR requests. Per-app registration
// belongs in setup, which runs for every rendered collection and request.
export default defineComponent({
  name: 'LocalBaserowCollectionRefinements',
  inheritAttrs: false,
  async setup(_, { attrs }) {
    const header = await loadCollectionRefinements(useNuxtApp())
    return () => h(header, attrs)
  },
})
