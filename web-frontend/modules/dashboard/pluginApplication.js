import { DashboardSearchType } from '@baserow/modules/dashboard/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'
import { DashboardLastViewedItemType } from '@baserow/modules/dashboard/lastViewedItemTypes'
import { SummaryWidgetType } from '@baserow/modules/dashboard/widgetTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const { $store, $registry } = nuxtApp
  const context = { app: nuxtApp }
  if (!$store.hasModule('dashboardApplication')) {
    $store.registerModuleNuxtSafe(
      'dashboardApplication',
      dashboardApplicationStore
    )
    $store.registerModuleNuxtSafe(
      'template/dashboardApplication',
      dashboardApplicationStore
    )
  }
  $registry.registerNamespace('dashboardWidget')
  $registry.register('application', new DashboardApplicationType(context))
  $registry.register('lastViewedItem', new DashboardLastViewedItemType(context))
  $registry.register('dashboardWidget', new SummaryWidgetType(context))
  searchTypeRegistry.register(new DashboardSearchType(context))
}
