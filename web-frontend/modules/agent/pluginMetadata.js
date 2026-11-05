import { AgentApplicationType } from '@baserow/modules/agent/applicationTypes'
import { AgentLastViewedItemType } from '@baserow/modules/agent/lastViewedItemTypes'
import { AgentApplicationSearchType } from '@baserow/modules/agent/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

/** Register lightweight application metadata for workspace lists and navigation. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  nuxtApp.$registry.register('application', new AgentApplicationType(context))
  nuxtApp.$registry.register(
    'lastViewedItem',
    new AgentLastViewedItemType(context)
  )
  searchTypeRegistry.register(new AgentApplicationSearchType(context))
}
