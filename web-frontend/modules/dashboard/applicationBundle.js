import registerApplication from '@baserow/modules/dashboard/pluginApplication'
import registerRealtime from '@baserow/modules/dashboard/plugins/realtimeApplication'

/** Initialize this application's registries, stores and realtime handlers together. */
export default async function register(app) {
  await registerApplication(app)
  if (app.$realtime) await registerRealtime(app)
}

export { default as ApplicationContext } from '@baserow/modules/dashboard/components/application/ApplicationContext'
export { default as DashboardForm } from '@baserow/modules/dashboard/components/form/DashboardForm'
export { default as SidebarComponentDashboard } from '@baserow/modules/dashboard/components/sidebar/SidebarComponentDashboard'
export { default as DashboardTemplateSidebar } from '@baserow/modules/dashboard/components/sidebar/DashboardTemplateSidebar'
export { default as DashboardTemplate } from '@baserow/modules/dashboard/components/DashboardTemplate'
