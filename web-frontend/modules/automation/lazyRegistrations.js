import {
  GeneralAutomationSettingsType,
  IntegrationsAutomationSettingsType,
} from '@baserow/modules/automation/automationSettingTypes'
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
  LocalBaserowAggregateRowsActionNodeType,
  CoreCSVFileReaderNodeType,
  CoreHttpRequestNodeType,
  CoreIteratorNodeType,
  CoreSMTPEmailNodeType,
  CoreRouterNodeType,
  CorePeriodicTriggerNodeType,
  CoreStartWorkflowNodeType,
  CoreManualTriggerNodeType,
  AIAgentActionNodeType,
  SlackWriteMessageNodeType,
} from '@baserow/modules/automation/nodeTypes'
import {
  HistoryEditorSidePanelType,
  NodeEditorSidePanelType,
} from '@baserow/modules/automation/editorSidePanelTypes'
import { AutomationGuidedTourType } from '@baserow/modules/automation/guidedTourTypes'
import {
  PreviousNodeDataProviderType,
  CurrentIterationDataProviderType,
} from '@baserow/modules/automation/dataProviderTypes'

export default function registerAutomationDomain(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }

  $registry.register(
    'automationDataProvider',
    new PreviousNodeDataProviderType(context)
  )
  $registry.register(
    'automationDataProvider',
    new CurrentIterationDataProviderType(context)
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
  $registry.register('node', new LocalBaserowCreateRowActionNodeType(context))
  $registry.register('node', new LocalBaserowCreateRowsActionNodeType(context))
  $registry.register('node', new LocalBaserowUpdateRowActionNodeType(context))
  $registry.register('node', new LocalBaserowUpdateRowsActionNodeType(context))
  $registry.register('node', new CoreHttpRequestNodeType(context))
  $registry.register('node', new CoreSMTPEmailNodeType(context))
  $registry.register('node', new CoreRouterNodeType(context))
  $registry.register('node', new CoreIteratorNodeType(context))
  $registry.register('node', new CoreCSVFileReaderNodeType(context))
  $registry.register('node', new CoreStartWorkflowNodeType(context))
  $registry.register('node', new SlackWriteMessageNodeType(context))
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

  $registry.register('guidedTour', new AutomationGuidedTourType(context))
}
