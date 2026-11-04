import tableStore from '@baserow/modules/database/store/table'
import viewStore from '@baserow/modules/database/store/view'
import fieldStore from '@baserow/modules/database/store/field'
import gridStore from '@baserow/modules/database/store/view/grid'
import galleryStore from '@baserow/modules/database/store/view/gallery'
import formStore from '@baserow/modules/database/store/view/form'
import rowModal from '@baserow/modules/database/store/rowModal'
import publicStore from '@baserow/modules/database/store/view/public'
import rowModalNavigationStore from '@baserow/modules/database/store/rowModalNavigation'
import rowHistoryStore from '@baserow/modules/database/store/rowHistory'
import fieldRulesStore from '@baserow/modules/database/store/fieldRules'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const { $store } = nuxtApp
  if (!$store.hasModule('table')) {
    $store.registerModuleNuxtSafe('table', tableStore)
    $store.registerModuleNuxtSafe('view', viewStore)
    $store.registerModuleNuxtSafe('field', fieldStore)
    $store.registerModuleNuxtSafe('rowModal', rowModal)
    $store.registerModuleNuxtSafe('rowModalNavigation', rowModalNavigationStore)
    $store.registerModuleNuxtSafe('rowHistory', rowHistoryStore)
    $store.registerModuleNuxtSafe('fieldRules', fieldRulesStore)
    $store.registerModuleNuxtSafe('page/view/grid', gridStore)
    $store.registerModuleNuxtSafe('page/view/gallery', galleryStore)
    $store.registerModuleNuxtSafe('page/view/form', formStore)
    $store.registerModuleNuxtSafe('page/view/public', publicStore)
    $store.registerModuleNuxtSafe('template/view/grid', gridStore)
    $store.registerModuleNuxtSafe('template/view/gallery', galleryStore)
    $store.registerModuleNuxtSafe('template/view/form', formStore)
  }
}
