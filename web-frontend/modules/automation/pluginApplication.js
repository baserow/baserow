import {
  GeneralAutomationSettingsType,
  IntegrationsAutomationSettingsType,
} from '@baserow/modules/automation/automationSettingTypes'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import { AutomationWorkflowLastViewedItemType } from '@baserow/modules/automation/lastViewedItemTypes'
import automationApplicationStore from '@baserow/modules/automation/store/automationApplication'
import automationWorkflowStore from '@baserow/modules/automation/store/automationWorkflow'
import automationWorkflowNodeStore from '@baserow/modules/automation/store/automationWorkflowNode'
import automationHistoryStore from '@baserow/modules/automation/store/automationHistory'
import {
  LocalBaserowCreateRowActionNodeType,
  LocalBaserowCreateRowsActionNodeType,
  LocalBaserowUpdateRowActionNodeType,
  LocalBaserowUpdateRowsActionNodeType,
  LocalBaserowDeleteRowActionNodeType,
  LocalBaserowGetRowActionNodeType,
  LocalBaserowListRowsActionNodeType,
  LocalBaserowRowsCreatedTriggerNodeType,
  LocalBaserowRowsUpdatedTriggerNodeType,
  LocalBaserowRowsDeletedTriggerNodeType,
  LocalBaserowFieldsUpdatedTriggerNodeType,
  CoreHTTPTriggerNodeType,
  CoreInboundEmailTriggerNodeType,
  LocalBaserowAggregateRowsActionNodeType,
  CoreCSVFileReaderActionNodeType,
  CoreHTTPRequestActionNodeType,
  CoreIteratorActionNodeType,
  CoreSMTPEmailActionNodeType,
  CoreRouterActionNodeType,
  CoreGotoActionNodeType,
  CorePeriodicTriggerNodeType,
  CoreResponseActionNodeType,
  CoreStartWorkflowActionNodeType,
  CoreManualTriggerNodeType,
  AIAgentActionNodeType,
  SlackWriteMessageActionNodeType,
} from '@baserow/modules/automation/nodeTypes'
import {
  ForLoopNodeRecipeType,
  WhileLoopNodeRecipeType,
} from '@baserow/modules/automation/nodeRecipeTypes'
import {
  DuplicateAutomationWorkflowJobType,
  PublishAutomationWorkflowJobType,
} from '@baserow/modules/automation/jobTypes'
import { WorkflowDisabledNotificationType } from '@baserow/modules/automation/notificationTypes.jsx'
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
  CurrentNodeDataProviderType,
} from '@baserow/modules/automation/dataProviderTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const { $registry, $store } = nuxtApp
  const context = { app: nuxtApp }
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
  $registry.registerNamespace('automationNodeRecipe')
  $registry.registerNamespace('editorSidePanel')
  $registry.register('application', new AutomationApplicationType(context))
  $registry.register(
    'lastViewedItem',
    new AutomationWorkflowLastViewedItemType(context)
  )
  $registry.register(
    'automationDataProvider',
    new PreviousNodeDataProviderType(context)
  )
  $registry.register(
    'automationDataProvider',
    new CurrentIterationDataProviderType(context)
  )
  $registry.register(
    'automationDataProvider',
    new CurrentNodeDataProviderType(context)
  )
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
  $registry.register(
    'node',
    new LocalBaserowFieldsUpdatedTriggerNodeType(context)
  )
  $registry.register('node', new CoreHTTPTriggerNodeType(context))
  $registry.register('node', new CoreInboundEmailTriggerNodeType(context))
  $registry.register('node', new LocalBaserowCreateRowActionNodeType(context))
  $registry.register('node', new LocalBaserowCreateRowsActionNodeType(context))
  $registry.register('node', new LocalBaserowUpdateRowActionNodeType(context))
  $registry.register('node', new LocalBaserowUpdateRowsActionNodeType(context))
  $registry.register('node', new CoreHTTPRequestActionNodeType(context))
  $registry.register('node', new CoreSMTPEmailActionNodeType(context))
  $registry.register('node', new CoreRouterActionNodeType(context))
  $registry.register('node', new CoreGotoActionNodeType(context))
  $registry.register('node', new CoreResponseActionNodeType(context))
  $registry.register('node', new CoreIteratorActionNodeType(context))
  $registry.register('node', new CoreCSVFileReaderActionNodeType(context))
  $registry.register('node', new CoreStartWorkflowActionNodeType(context))
  $registry.register('node', new SlackWriteMessageActionNodeType(context))
  $registry.register('node', new LocalBaserowDeleteRowActionNodeType(context))
  $registry.register('node', new LocalBaserowGetRowActionNodeType(context))
  $registry.register('node', new LocalBaserowListRowsActionNodeType(context))
  $registry.register(
    'node',
    new LocalBaserowAggregateRowsActionNodeType(context)
  )
  $registry.register('node', new CorePeriodicTriggerNodeType(context))
  $registry.register('node', new CoreManualTriggerNodeType(context))
  $registry.register('node', new AIAgentActionNodeType(context))
  $registry.register('automationNodeRecipe', new ForLoopNodeRecipeType(context))
  $registry.register(
    'automationNodeRecipe',
    new WhileLoopNodeRecipeType(context)
  )
  $registry.register('job', new DuplicateAutomationWorkflowJobType(context))
  $registry.register('job', new PublishAutomationWorkflowJobType(context))
  $registry.register(
    'notification',
    new WorkflowDisabledNotificationType(context)
  )
  $registry.registerNamespace('automationSettings')
  $registry.register(
    'automationSettings',
    new GeneralAutomationSettingsType(context)
  )
  $registry.register(
    'automationSettings',
    new IntegrationsAutomationSettingsType(context)
  )
  $registry.register('editorSidePanel', new NodeEditorSidePanelType(context))
  $registry.register('editorSidePanel', new HistoryEditorSidePanelType(context))
  searchTypeRegistry.register(new AutomationSearchType(context))
  $registry.register('guidedTour', new AutomationGuidedTourType(context))
}
