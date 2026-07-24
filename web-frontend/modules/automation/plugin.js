import { defineNuxtPlugin } from '#app'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import automationApplicationStore from '@baserow/modules/automation/store/automationApplication'
import automationWorkflowStore from '@baserow/modules/automation/store/automationWorkflow'
import automationWorkflowNodeStore from '@baserow/modules/automation/store/automationWorkflowNode'
import automationHistoryStore from '@baserow/modules/automation/store/automationHistory'
import {
  DuplicateAutomationWorkflowJobType,
  PublishAutomationWorkflowJobType,
} from '@baserow/modules/automation/jobTypes'
import { WorkflowDisabledNotificationType } from '@baserow/modules/automation/notificationTypes.jsx'
import { AutomationSearchType } from '@baserow/modules/automation/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

export default defineNuxtPlugin({
  name: 'automation',
  dependsOn: ['core', 'store'],
  setup(nuxtApp) {
    const { $registry, $store } = nuxtApp

    const context = { app: nuxtApp }

    // Register stores
    $store.registerModuleNuxtSafe(
      'automationApplication',
      automationApplicationStore
    )
    $store.registerModuleNuxtSafe('automationWorkflow', automationWorkflowStore)
    $store.registerModuleNuxtSafe(
      'automationWorkflowNode',
      automationWorkflowNodeStore
    )
    $store.registerModuleNuxtSafe('automationHistory', automationHistoryStore)
    $store.registerModuleNuxtSafe(
      'template/automationApplication',
      automationApplicationStore
    )

    $registry.registerNamespace('automationDataProvider')
    $registry.registerNamespace('node')
    $registry.registerNamespace('editorSidePanel')
    $registry.registerNamespace('automationSettings')

    $registry.register('application', new AutomationApplicationType(context))

    // Job and notification types stay eager: sidebar jobs and the notifications panel resolve them on any page.
    $registry.register('job', new DuplicateAutomationWorkflowJobType(context))
    $registry.register('job', new PublishAutomationWorkflowJobType(context))
    $registry.register(
      'notification',
      new WorkflowDisabledNotificationType(context)
    )

    // Automation search type
    searchTypeRegistry.register(new AutomationSearchType(context))

    // Node types, data providers, side panels, settings and tours load on automation routes.
    $registry.registerDomainLoader('automation', async () => {
      const { default: register } =
        await import('@baserow/modules/automation/lazyRegistrations')
      register(nuxtApp)
    })
  },
})
