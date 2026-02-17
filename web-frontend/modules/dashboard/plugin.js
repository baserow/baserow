import { DashboardSearchType } from '@baserow/modules/dashboard/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'
import { SummaryWidgetType } from '@baserow/modules/dashboard/widgetTypes'

export default defineNuxtPlugin({
  name: 'dashboard',
  dependsOn: ['core', 'store'],
  async setup(nuxtApp) {
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
    $registry.register('dashboardWidget', new SummaryWidgetType(context))

    searchTypeRegistry.register(new DashboardSearchType(context))
  },
})
