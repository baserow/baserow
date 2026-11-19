import {
  WidgetDataProviderType,
  DashboardDataSourceContextDataProviderType,
} from '@baserow/modules/dashboard/dataProviderTypes'
import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'
import {
  SummaryWidgetType,
  TextFilterWidgetType,
} from '@baserow/modules/dashboard/widgetTypes'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $registry, $store } = nuxtApp
  const context = { app: nuxtApp }
  $registry.registerNamespace('dashboardDataProvider')
  $registry.register(
    'dashboardDataProvider',
    new WidgetDataProviderType(context)
  )
  $registry.register(
    'dashboardDataProvider',
    new DashboardDataSourceContextDataProviderType(context)
  )
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
  $registry.register('dashboardWidget', new TextFilterWidgetType(context))
  $registry.register('dashboardWidget', new SummaryWidgetType(context))
}
