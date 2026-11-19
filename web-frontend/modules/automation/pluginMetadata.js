import registerRealtimeMetadata from '@baserow/modules/automation/realtimeMetadata'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import { AutomationWorkflowLastViewedItemType } from '@baserow/modules/automation/lastViewedItemTypes'
import {
  DuplicateAutomationWorkflowJobType,
  PublishAutomationWorkflowJobType,
} from '@baserow/modules/automation/jobTypes'
import { AutomationSearchType } from '@baserow/modules/automation/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

/** Register lightweight application metadata for workspace lists and navigation. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  if (nuxtApp.$realtime) registerRealtimeMetadata(nuxtApp)
  $registry.register('application', new AutomationApplicationType(context))
  $registry.register(
    'lastViewedItem',
    new AutomationWorkflowLastViewedItemType(context)
  )
  $registry.register('job', new DuplicateAutomationWorkflowJobType(context))
  $registry.register('job', new PublishAutomationWorkflowJobType(context))
  searchTypeRegistry.register(new AutomationSearchType(context))
}
