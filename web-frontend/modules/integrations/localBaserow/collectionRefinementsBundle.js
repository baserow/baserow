import { defineComponent, h } from 'vue'
import { useNuxtApp } from '#app'
import LocalBaserowAdhocHeader from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowAdhocHeader.vue'
import registerDatabase from '@baserow/modules/database/pluginApplication'
import registerDatabaseStore from '@baserow/modules/database/plugin/storeApplication'

const registrations = new WeakMap()

/**
 * Public filtering controls reuse Database registries and stores. Load them only
 * when a collection enables refinements, and initialize once per Nuxt app so
 * concurrent collections and SSR requests keep their own registration state.
 */
export async function loadCollectionRefinements(app) {
  if (!registrations.has(app) && !app.$store.hasModule('field')) {
    registrations.set(
      app,
      (async () => {
        await registerDatabaseStore(app)
        await registerDatabase(app)
      })()
    )
  }
  if (registrations.has(app)) await registrations.get(app)
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
