import registerApplication from '@baserow/modules/automation/pluginApplication'
import registerRealtime from '@baserow/modules/automation/plugins/realtimeApplication'

/** Initialize this application's registries, stores and realtime handlers together. */
export default async function register(app) {
  await registerApplication(app)
  if (app.$realtime) await registerRealtime(app)
}

export { default as ApplicationContext } from '@baserow/modules/automation/components/application/ApplicationContext'
export { default as AutomationForm } from '@baserow/modules/automation/components/form/AutomationForm'
export { default as SidebarComponentAutomation } from '@baserow/modules/automation/components/sidebar/SidebarComponentAutomation'
export { default as WorkflowTemplate } from '@baserow/modules/automation/components/workflow/WorkflowTemplate.vue'
export { default as WorkflowTemplateSideBar } from '@baserow/modules/automation/components/workflow/WorkflowTemplateSideBar.vue'
