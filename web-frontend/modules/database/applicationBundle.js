import registerApplication from '@baserow/modules/database/pluginApplication'
import registerStore from '@baserow/modules/database/plugin/storeApplication'
import registerRealtime from '@baserow/modules/database/plugin/realtimeApplication'

/** Initialize this application's registries, stores and realtime handlers together. */
export default async function register(app) {
  await registerStore(app)
  await registerApplication(app)
  if (app.$realtime) await registerRealtime(app)
}

export { default as Sidebar } from '@baserow/modules/database/components/sidebar/Sidebar'
export { default as TemplateSidebar } from '@baserow/modules/database/components/sidebar/TemplateSidebar'
export { default as TableTemplate } from '@baserow/modules/database/components/table/TableTemplate'
export { default as GridViewRowExpandButton } from '@baserow/modules/database/components/view/grid/GridViewRowExpandButton'
export { default as DatabaseForm } from '@baserow/modules/database/components/form/DatabaseForm'
export { default as ApplicationContext } from '@baserow/modules/database/components/application/ApplicationContext'
