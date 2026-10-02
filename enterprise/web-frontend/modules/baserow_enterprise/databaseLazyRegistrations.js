import {
  GitHubIssuesDataSyncType,
  GitLabIssuesDataSyncType,
  HubspotContactsDataSyncType,
  PostgreSQLDataSyncType,
  JiraIssuesDataSyncType,
  LocalBaserowTableDataSyncType,
} from '@baserow_enterprise/dataSyncTypes'
import { PeriodicIntervalFieldsConfigureDataSyncType } from '@baserow_enterprise/configureDataSyncTypes'
import { RowsEnterViewWebhookEventType } from '@baserow_enterprise/webhookEventTypes'
import { FieldPermissionsContextItemType } from '@baserow_enterprise/fieldContextItemTypes'
import {
  DateDependencyContextItemType,
  DateDependencyTimelineComponent,
} from '@baserow_enterprise/dateDependencyTypes'
import { RealtimePushTwoWaySyncStrategyType } from '@baserow_enterprise/twoWaySyncStrategyTypes'
import { RestrictedViewOwnershipType } from '@baserow_enterprise/viewOwnershipTypes'

export default function registerEnterpriseDatabaseDomain(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }

  // Overrides core's postgresql type; enterprise's loader runs after core's.
  $registry.register('dataSync', new PostgreSQLDataSyncType(context))
  $registry.register('dataSync', new LocalBaserowTableDataSyncType(context))
  $registry.register('dataSync', new JiraIssuesDataSyncType(context))
  $registry.register('dataSync', new GitHubIssuesDataSyncType(context))
  $registry.register('dataSync', new GitLabIssuesDataSyncType(context))
  $registry.register('dataSync', new HubspotContactsDataSyncType(context))

  $registry.register(
    'configureDataSync',
    new PeriodicIntervalFieldsConfigureDataSyncType(context)
  )

  $registry.register('webhookEvent', new RowsEnterViewWebhookEventType(context))

  $registry.register(
    'timelineFieldRules',
    new DateDependencyTimelineComponent(context)
  )
  $registry.register(
    'fieldContextItem',
    new DateDependencyContextItemType(context)
  )

  $registry.register(
    'fieldContextItem',
    new FieldPermissionsContextItemType(context)
  )

  $registry.register(
    'twoWaySyncStrategy',
    new RealtimePushTwoWaySyncStrategyType(context)
  )

  $registry.register(
    'viewOwnershipType',
    new RestrictedViewOwnershipType(context)
  )
}
