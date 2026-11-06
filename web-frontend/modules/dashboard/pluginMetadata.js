import { DashboardSearchType } from '@baserow/modules/dashboard/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'
import { DashboardLastViewedItemType } from '@baserow/modules/dashboard/lastViewedItemTypes'

/** Register lightweight application metadata for workspace lists and navigation. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register('application', new DashboardApplicationType(context))
  $registry.register('lastViewedItem', new DashboardLastViewedItemType(context))
  searchTypeRegistry.register(new DashboardSearchType(context))
}
