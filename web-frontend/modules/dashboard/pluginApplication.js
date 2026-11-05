import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'
import { SummaryWidgetType } from '@baserow/modules/dashboard/widgetTypes'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $registry, $store } = nuxtApp
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
  $registry.register('dashboardWidget', new SummaryWidgetType(context))
}
