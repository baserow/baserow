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
import { AIDatabaseOnboardingStepType } from '@baserow_enterprise/databaseOnboardingStepTypes'
import { SemanticSearchFieldFormAdvancedSettingType } from '@baserow_enterprise/fieldFormAdvancedSettingTypes'
import {
  AISemanticSearchFieldType,
  EmailSemanticSearchFieldType,
  FormulaSemanticSearchFieldType,
  LongTextSemanticSearchFieldType,
  LookupSemanticSearchFieldType,
  PhoneNumberSemanticSearchFieldType,
  RollupSemanticSearchFieldType,
  TextSemanticSearchFieldType,
  URLSemanticSearchFieldType,
} from '@baserow_enterprise/semanticSearchFieldTypes'
import { FF_SEMANTIC_SEARCH } from '@baserow/modules/core/plugins/featureFlags'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $registry, $featureFlagIsEnabled } = nuxtApp
  const context = { app: nuxtApp }

  for (const SemanticSearchFieldType of [
    TextSemanticSearchFieldType,
    LongTextSemanticSearchFieldType,
    URLSemanticSearchFieldType,
    EmailSemanticSearchFieldType,
    PhoneNumberSemanticSearchFieldType,
    FormulaSemanticSearchFieldType,
    LookupSemanticSearchFieldType,
    RollupSemanticSearchFieldType,
    AISemanticSearchFieldType,
  ]) {
    $registry.register(
      'semanticSearchFieldType',
      new SemanticSearchFieldType(context)
    )
  }
  if ($featureFlagIsEnabled(FF_SEMANTIC_SEARCH)) {
    $registry.register(
      'fieldFormAdvancedSetting',
      new SemanticSearchFieldFormAdvancedSettingType(context)
    )
  }
  $registry.unregister('dataSync', PostgreSQLDataSyncType.getType())
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
    'databaseOnboardingStep',
    new AIDatabaseOnboardingStepType(context)
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

export { default as MemberRolesTableContextItem } from '@baserow_enterprise/components/member-roles/MemberRolesTableContextItem'
export { default as MemberRolesViewContextItem } from '@baserow_enterprise/components/member-roles/MemberRolesViewContextItem'
export { default as DateDependencyMenuItem } from '@baserow_enterprise/components/dateDependency/DateDependencyMenuItem'
export { default as DateDependencyFieldTypeIcon } from '@baserow_enterprise/components/dateDependency/DateDependencyFieldTypeIcon'
export { default as AIDatabaseOnboardingForm } from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'
export { default as DatabaseAppLayoutPreview } from '@baserow/modules/database/components/onboarding/DatabaseAppLayoutPreview'
export { default as AIPromptStep } from '@baserow_enterprise/components/onboarding/AIPromptStep'
export { default as AssistantOnboardingMessage } from '@baserow_enterprise/components/assistant/AssistantOnboardingMessage.vue'
