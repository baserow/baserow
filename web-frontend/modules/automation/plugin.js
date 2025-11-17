import en from '@baserow/modules/automation/locales/en.json'
import fr from '@baserow/modules/automation/locales/fr.json'
import nl from '@baserow/modules/automation/locales/nl.json'
import de from '@baserow/modules/automation/locales/de.json'
import es from '@baserow/modules/automation/locales/es.json'
import it from '@baserow/modules/automation/locales/it.json'
import pl from '@baserow/modules/automation/locales/pl.json'
import ko from '@baserow/modules/automation/locales/ko.json'
import {
  GeneralAutomationSettingsType,
  IntegrationsAutomationSettingsType,
} from '@baserow/modules/automation/automationSettingTypes'

import { registerRealtimeEvents } from '@baserow/modules/automation/realtime'
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

export default (context) => {
  const { app, isDev, store } = context

  // Allow locale file hot reloading in dev
  if (isDev && app.i18n) {
    const { i18n } = app
    i18n.mergeLocaleMessage('en', en)
    i18n.mergeLocaleMessage('fr', fr)
    i18n.mergeLocaleMessage('nl', nl)
    i18n.mergeLocaleMessage('de', de)
    i18n.mergeLocaleMessage('es', es)
    i18n.mergeLocaleMessage('it', it)
    i18n.mergeLocaleMessage('pl', pl)
    i18n.mergeLocaleMessage('ko', ko)
  }

  registerRealtimeEvents(app.$realtime)

  app.$clientErrorMap.setError(
    'ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE',
    app.i18n.t('automationWorkflowErrors.errorNameNotUnique'),
    app.i18n.t('automationWorkflowErrors.errorNameNotUniqueDescription')
  )

  store.registerModule('automationApplication', automationApplicationStore)
  store.registerModule('automationWorkflow', automationWorkflowStore)
  store.registerModule('automationWorkflowNode', automationWorkflowNodeStore)
  store.registerModule('automationHistory', automationHistoryStore)
  store.registerModule(
    'template/automationApplication',
    automationApplicationStore
  )

  // Automation data providers.
  app.$registry.register('application', new AutomationApplicationType(context))
  app.$registry.register(
    'automationDataProvider',
    new PreviousNodeDataProviderType(context)
  )
  app.$registry.register(
    'automationDataProvider',
    new CurrentIterationDataProviderType(context)
  )

  // Automation node types.
  app.$registry.register(
    'node',
    new LocalBaserowRowsCreatedTriggerNodeType(context)
  )
  app.$registry.register(
    'node',
    new LocalBaserowRowsUpdatedTriggerNodeType(context)
  )
  app.$registry.register(
    'node',
    new LocalBaserowRowsDeletedTriggerNodeType(context)
  )
  app.$registry.register('node', new CoreHTTPTriggerNodeType(context))
  app.$registry.register(
    'node',
    new LocalBaserowCreateRowActionNodeType(context)
  )
  app.$registry.register(
    'node',
    new LocalBaserowUpdateRowActionNodeType(context)
  )
  app.$registry.register('node', new CoreHttpRequestNodeType(context))
  app.$registry.register('node', new CoreSMTPEmailNodeType(context))
  app.$registry.register('node', new CoreRouterNodeType(context))
  app.$registry.register('node', new CoreIteratorNodeType(context))
  app.$registry.register('node', new SlackWriteMessageNodeType(context))
  app.$registry.register(
    'node',
    new LocalBaserowDeleteRowActionNodeType(context)
  )
  app.$registry.register('node', new LocalBaserowGetRowActionNodeType(context))
  app.$registry.register(
    'node',
    new LocalBaserowListRowsActionNodeType(context)
  )
  app.$registry.register(
    'node',
    new LocalBaserowAggregateRowsActionNodeType(context)
  )
  app.$registry.register('node', new CorePeriodicTriggerNodeType(context))
  app.$registry.register('node', new AIAgentActionNodeType(context))

  // Automation job types.
  app.$registry.register('job', new DuplicateAutomationWorkflowJobType(context))
  app.$registry.register('job', new PublishAutomationWorkflowJobType(context))

  // Automation settings.
  app.$registry.registerNamespace('automationSettings')
  app.$registry.register(
    'automationSettings',
    new GeneralAutomationSettingsType(context)
  )
  app.$registry.register(
    'automationSettings',
    new IntegrationsAutomationSettingsType(context)
  )

  // Automation editor side panels.
  app.$registry.register(
    'editorSidePanel',
    new NodeEditorSidePanelType(context)
  )
  app.$registry.register(
    'editorSidePanel',
    new HistoryEditorSidePanelType(context)
  )

  // Automation search type
  searchTypeRegistry.register(new AutomationSearchType())

  // Automation guided tour.
  app.$registry.register('guidedTour', new AutomationGuidedTourType(context))
}
