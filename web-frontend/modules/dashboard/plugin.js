// import en from '@baserow/modules/dashboard/locales/en.json'
// import fr from '@baserow/modules/dashboard/locales/fr.json'
// import nl from '@baserow/modules/dashboard/locales/nl.json'
// import de from '@baserow/modules/dashboard/locales/de.json'
// import es from '@baserow/modules/dashboard/locales/es.json'
// import it from '@baserow/modules/dashboard/locales/it.json'
// import pl from '@baserow/modules/dashboard/locales/pl.json'
// import ko from '@baserow/modules/dashboard/locales/ko.json'

// import { registerRealtimeEvents } from '@baserow/modules/dashboard/realtime'
// import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'
// import { SummaryWidgetType } from '@baserow/modules/dashboard/widgetTypes'
// import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'
// import { DashboardSearchType } from '@baserow/modules/dashboard/searchTypes'
// import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

// export default (context) => {
//   const { app, isDev, store } = context

//   // Allow locale file hot reloading in dev
//   if (isDev && app.i18n) {
//     const { i18n } = app
//     i18n.mergeLocaleMessage('en', en)
//     i18n.mergeLocaleMessage('fr', fr)
//     i18n.mergeLocaleMessage('nl', nl)
//     i18n.mergeLocaleMessage('de', de)
//     i18n.mergeLocaleMessage('es', es)
//     i18n.mergeLocaleMessage('it', it)
//     i18n.mergeLocaleMessage('pl', pl)
//     i18n.mergeLocaleMessage('ko', ko)
//   }

//   registerRealtimeEvents(app.$realtime)

//   store.registerModule('dashboardApplication', dashboardApplicationStore)
//   store.registerModule(
//     'template/dashboardApplication',
//     dashboardApplicationStore
//   )

//   app.$registry.register('application', new DashboardApplicationType(context))
//   app.$registry.register('dashboardWidget', new SummaryWidgetType(context))

//   searchTypeRegistry.register(new DashboardSearchType())
// }

import { registerRealtimeEvents } from '@baserow/modules/dashboard/realtime'
import { DashboardSearchType } from '@baserow/modules/dashboard/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'
import { SummaryWidgetType } from '@baserow/modules/dashboard/widgetTypes'

// Import translations
/*import en from '@baserow/modules/dashboard/locales/en.json'
import fr from '@baserow/modules/dashboard/locales/fr.json'
import nl from '@baserow/modules/dashboard/locales/nl.json'
import de from '@baserow/modules/dashboard/locales/de.json'
import es from '@baserow/modules/dashboard/locales/es.json'
import it from '@baserow/modules/dashboard/locales/it.json'
import pl from '@baserow/modules/dashboard/locales/pl.json'
import ko from '@baserow/modules/dashboard/locales/ko.json'*/

export default defineNuxtPlugin({
  dependsOn: ['core', 'store'],
  async setup(nuxtApp) {
    const { $store, $registry, $i18n } = nuxtApp
    const context = { app: nuxtApp }

    // Merge dashboard translations into i18n
    /*if ($i18n) {
      $i18n.mergeLocaleMessage('en', en)
      $i18n.mergeLocaleMessage('fr', fr)
      $i18n.mergeLocaleMessage('nl', nl)
      $i18n.mergeLocaleMessage('de', de)
      $i18n.mergeLocaleMessage('es', es)
      $i18n.mergeLocaleMessage('it', it)
      $i18n.mergeLocaleMessage('pl', pl)
      $i18n.mergeLocaleMessage('ko', ko)
    } */

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
