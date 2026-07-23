import { DashboardSearchType } from '@baserow/modules/dashboard/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'

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

    // Widget types load on dashboard routes.
    $registry.registerDomainLoader('dashboard', async () => {
      const { default: register } =
        await import('@baserow/modules/dashboard/lazyRegistrations')
      register(nuxtApp)
    })

    searchTypeRegistry.register(new DashboardSearchType(context))
  },
})
