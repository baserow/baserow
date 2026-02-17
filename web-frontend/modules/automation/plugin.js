import { defineNuxtPlugin } from '#app'
import {
  GeneralAutomationSettingsType,
  IntegrationsAutomationSettingsType,
} from '@baserow/modules/automation/automationSettingTypes'

import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import automationApplicationStore from '@baserow/modules/automation/store/automationApplication'
import automationWorkflowStore from '@baserow/modules/automation/store/automationWorkflow'
import automationWorkflowNodeStore from '@baserow/modules/automation/store/automationWorkflowNode'
import automationHistoryStore from '@baserow/modules/automation/store/automationHistory'
import {
  LocalBaserowCreateRowActionNodeType,
  LocalBaserowUpdateRowActionNodeType,
  LocalBaserowDeleteRowActionNodeType,
  LocalBaserowGetRowActionNodeType,
  LocalBaserowListRowsActionNodeType,
  LocalBaserowRowsCreatedTriggerNodeType,
  LocalBaserowRowsUpdatedTriggerNodeType,
  LocalBaserowRowsDeletedTriggerNodeType,
  CoreHTTPTriggerNodeType,
  LocalBaserowAggregateRowsActionNodeType,
  CoreHttpRequestNodeType,
  CoreIteratorNodeType,
  CoreSMTPEmailNodeType,
  CoreRouterNodeType,
  CorePeriodicTriggerNodeType,
  AIAgentActionNodeType,
  SlackWriteMessageNodeType,
} from '@baserow/modules/automation/nodeTypes'
import {
  DuplicateAutomationWorkflowJobType,
  PublishAutomationWorkflowJobType,
} from '@baserow/modules/automation/jobTypes'
import {
  HistoryEditorSidePanelType,
  NodeEditorSidePanelType,
} from '@baserow/modules/automation/editorSidePanelTypes'
import { AutomationSearchType } from '@baserow/modules/automation/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import { AutomationGuidedTourType } from '@baserow/modules/automation/guidedTourTypes'
import {
  PreviousNodeDataProviderType,
  CurrentIterationDataProviderType,
} from '@baserow/modules/automation/dataProviderTypes'

export default defineNuxtPlugin({
  name: 'automation',
  dependsOn: ['core', 'store'],
  setup(nuxtApp) {
    const { $registry, $store, $clientErrorMap, $i18n } = nuxtApp

    const context = { app: nuxtApp }

    $clientErrorMap.setError(
      'ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE',
      $i18n.t('automationWorkflowErrors.errorNameNotUnique'),
      $i18n.t('automationWorkflowErrors.errorNameNotUniqueDescription')
    )

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

    // Automation data providers
    $registry.register('application', new AutomationApplicationType(context))
    $registry.register(
      'automationDataProvider',
      new PreviousNodeDataProviderType(context)
    )
    $registry.register(
      'automationDataProvider',
      new CurrentIterationDataProviderType(context)
    )

    // Automation node types
    $registry.register(
      'node',
      new LocalBaserowRowsCreatedTriggerNodeType(context)
    )
    $registry.register(
      'node',
      new LocalBaserowRowsUpdatedTriggerNodeType(context)
    )
    $registry.register(
      'node',
      new LocalBaserowRowsDeletedTriggerNodeType(context)
    )
    $registry.register('node', new CoreHTTPTriggerNodeType(context))
    $registry.register('node', new LocalBaserowCreateRowActionNodeType(context))
    $registry.register('node', new LocalBaserowUpdateRowActionNodeType(context))
    $registry.register('node', new CoreHttpRequestNodeType(context))
    $registry.register('node', new CoreSMTPEmailNodeType(context))
    $registry.register('node', new CoreRouterNodeType(context))
    $registry.register('node', new CoreIteratorNodeType(context))
    $registry.register('node', new SlackWriteMessageNodeType(context))
    $registry.register('node', new LocalBaserowDeleteRowActionNodeType(context))
    $registry.register('node', new LocalBaserowGetRowActionNodeType(context))
    $registry.register('node', new LocalBaserowListRowsActionNodeType(context))
    $registry.register(
      'node',
      new LocalBaserowAggregateRowsActionNodeType(context)
    )
    $registry.register('node', new CorePeriodicTriggerNodeType(context))
    $registry.register('node', new AIAgentActionNodeType(context))

    // Automation job types
    $registry.register('job', new DuplicateAutomationWorkflowJobType(context))
    $registry.register('job', new PublishAutomationWorkflowJobType(context))

    // Automation settings
    $registry.registerNamespace('automationSettings')
    $registry.register(
      'automationSettings',
      new GeneralAutomationSettingsType(context)
    )
    $registry.register(
      'automationSettings',
      new IntegrationsAutomationSettingsType(context)
    )

    // Automation editor side panels
    $registry.register('editorSidePanel', new NodeEditorSidePanelType(context))
    $registry.register(
      'editorSidePanel',
      new HistoryEditorSidePanelType(context)
    )

    // Automation search type
    searchTypeRegistry.register(new AutomationSearchType(context))

    // Automation guided tour
    $registry.register('guidedTour', new AutomationGuidedTourType(context))
  },
})
