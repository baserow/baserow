import {
  AuditLogExportJobType,
  DataScanResultExportJobType,
} from '@baserow_enterprise/jobTypes'
import {
  AuditLogType,
  AuthProvidersType,
  DataScannerType,
} from '@baserow_enterprise/adminTypes'
import authProviderAdminStore from '@baserow_enterprise/store/authProviderAdmin'
import assistantStore from '@baserow_enterprise/store/assistant'
import { PasswordAuthProviderType as CorePasswordAuthProviderType } from '@baserow/modules/core/authProviderTypes'
import { MadeWithBaserowBuilderPageDecoratorType } from '@baserow_enterprise/builderPageDecoratorTypes'
import {
  FacebookAuthProviderType,
  GitHubAuthProviderType,
  GitLabAuthProviderType,
  GoogleAuthProviderType,
  OpenIdConnectAuthProviderType,
  PasswordAuthProviderType,
  SamlAuthProviderType,
} from '@baserow_enterprise/authProviderTypes'
import { TeamsWorkspaceSettingsPageType } from '@baserow_enterprise/workspaceSettingsPageTypes'
import {
  EnterpriseRolesAgentExtensionType,
  EnterpriseTeamsAgentExtensionType,
} from '@baserow_enterprise/agentExtensionTypes'
import { EnterpriseTeamsAgentSettingsType } from '@baserow_enterprise/agentSettingsTypes'
import { TeamSubjectType } from '@baserow_enterprise/subjectTypes.jsx'
import { ScopeInvitationTargetType } from '@baserow_enterprise/invitationTargetTypes'
import { MemberInvitationRouteType } from '@baserow_enterprise/invitationRouteTypes'
import { EnterpriseMembersPagePluginType } from '@baserow_enterprise/membersPagePluginTypes'
import {
  AdvancedLicenseType,
  EnterpriseLicenseType,
  EnterpriseWithoutSupportLicenseType,
} from '@baserow_enterprise/licenseTypes'
import { EnterprisePlugin } from '@baserow_enterprise/plugins'
import {
  GitHubIssuesDataSyncType,
  GitLabIssuesDataSyncType,
  HubspotContactsDataSyncType,
  PostgreSQLDataSyncType,
  JiraIssuesDataSyncType,
  LocalBaserowTableDataSyncType,
} from '@baserow_enterprise/dataSyncTypes'
import { PeriodicIntervalFieldsConfigureDataSyncType } from '@baserow_enterprise/configureDataSyncTypes'
import {
  ApplicationUserLimitNotificationType,
  DataScanNewResultsNotificationType,
  PeriodicDataSyncDeactivatedNotificationType,
  TwoWayDataSyncUpdateFiledNotificationType,
  TwoWaySyncDeactivatedNotificationType,
} from '@baserow_enterprise/notificationTypes'
import { RowsEnterViewWebhookEventType } from '@baserow_enterprise/webhookEventTypes'
import {
  AdvancedWebhooksPaidFeature,
  AuditLogPaidFeature,
  BuilderBrandingPaidFeature,
  BuilderCustomCodePaidFeature,
  BuilderFileInputElementPaidFeature,
  BuilderGraphElementPaidFeature,
  CodeRunnerPaidFeature,
  CoBrandingPaidFeature,
  DataScannerPaidFeature,
  DataSyncPaidFeature,
  DateDependencyPaidFeature,
  FieldLevelPermissionsPaidFeature,
  RBACPaidFeature,
  SSOPaidFeature,
  SupportPaidFeature,
  SemanticSearchPaidFeature,
  XLSFileReaderPaidFeature,
} from '@baserow_enterprise/paidFeatures'
import { FieldPermissionsContextItemType } from '@baserow_enterprise/fieldContextItemTypes'
import {
  DateDependencyContextItemType,
  DateDependencyTimelineComponent,
} from '@baserow_enterprise/dateDependencyTypes'
import { CustomCodeBuilderSettingType } from '@baserow_enterprise/builderSettingTypes'
import { RealtimePushTwoWaySyncStrategyType } from '@baserow_enterprise/twoWaySyncStrategyTypes'
import { RestrictedViewOwnershipType } from '@baserow_enterprise/viewOwnershipTypes'
import { AIDatabaseOnboardingStepType } from '@baserow_enterprise/databaseOnboardingStepTypes'
import { AIPromptOnboardingType } from '@baserow_enterprise/onboardingTypes'
import { CoreCodeServiceType } from '@baserow_enterprise/integrations/core/serviceTypes'
import { CoreCodeWorkflowActionType } from '@baserow_enterprise/builder/workflowActionTypes'
import {
  CoreCodeActionNodeType,
  CoreXLSFileReaderActionNodeType,
} from '@baserow_enterprise/automation/nodeTypes'
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
import { KumaAIProviderModelFeatureType } from '@baserow_enterprise/aiProviderModelFeatureTypes'
import { FF_SEMANTIC_SEARCH } from '@baserow/modules/core/plugins/featureFlags'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const { $config, $registry, $store, $featureFlagIsEnabled } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register('plugin', new EnterprisePlugin(context))
  $registry.register(
    'aiProviderModelFeature',
    new KumaAIProviderModelFeatureType(context)
  )
  $store.registerModuleNuxtSafe('authProviderAdmin', authProviderAdminStore)
  $store.registerModuleNuxtSafe('assistant', assistantStore)
  $registry.register('admin', new AuthProvidersType(context))
  $registry.unregister(
    'authProvider',
    new CorePasswordAuthProviderType(context)
  )
  $registry.register('authProvider', new PasswordAuthProviderType(context))
  $registry.register('authProvider', new SamlAuthProviderType(context))
  $registry.register('authProvider', new GoogleAuthProviderType(context))
  $registry.register('authProvider', new FacebookAuthProviderType(context))
  $registry.register('authProvider', new GitHubAuthProviderType(context))
  $registry.register('authProvider', new GitLabAuthProviderType(context))
  $registry.register('authProvider', new OpenIdConnectAuthProviderType(context))
  $registry.register('admin', new AuditLogType(context))
  $registry.register('admin', new DataScannerType(context))
  $registry.register('plugin', new EnterprisePlugin(context))
  $registry.register(
    'membersPagePlugins',
    new EnterpriseMembersPagePluginType(context)
  )
  $registry.register(
    'workspaceSettingsPage',
    new TeamsWorkspaceSettingsPageType(context)
  )
  $registry.register(
    'agentExtension',
    new EnterpriseTeamsAgentExtensionType(context)
  )
  $registry.register(
    'agentExtension',
    new EnterpriseRolesAgentExtensionType(context)
  )
  $registry.register(
    'agentSettings',
    new EnterpriseTeamsAgentSettingsType(context)
  )
  $registry.register('subject', new TeamSubjectType(context))
  $registry.register('invitationTarget', new ScopeInvitationTargetType(context))
  $registry.register('invitationRoute', new MemberInvitationRouteType(context))
  $registry.register('job', new AuditLogExportJobType(context))
  $registry.register('job', new DataScanResultExportJobType(context))
  $registry.register('license', new AdvancedLicenseType(context))
  $registry.register(
    'license',
    new EnterpriseWithoutSupportLicenseType(context)
  )
  $registry.register('license', new EnterpriseLicenseType(context))
  if ($config.public.baserowEnterpriseCodeRunnerDefaultType) {
    $registry.register('node', new CoreCodeActionNodeType(context))
  }
  $registry.register('node', new CoreXLSFileReaderActionNodeType(context))
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
    'notification',
    new PeriodicDataSyncDeactivatedNotificationType(context)
  )
  $registry.register(
    'notification',
    new TwoWayDataSyncUpdateFiledNotificationType(context)
  )
  $registry.register(
    'notification',
    new TwoWaySyncDeactivatedNotificationType(context)
  )
  $registry.register(
    'notification',
    new DataScanNewResultsNotificationType(context)
  )
  $registry.register(
    'notification',
    new ApplicationUserLimitNotificationType(context)
  )
  $registry.register(
    'configureDataSync',
    new PeriodicIntervalFieldsConfigureDataSyncType(context)
  )
  $registry.register('webhookEvent', new RowsEnterViewWebhookEventType(context))
  $registry.register('paidFeature', new SSOPaidFeature(context))
  $registry.register('paidFeature', new AuditLogPaidFeature(context))
  $registry.register('paidFeature', new RBACPaidFeature(context))
  $registry.register('paidFeature', new DataSyncPaidFeature(context))
  $registry.register('paidFeature', new CoBrandingPaidFeature(context))
  $registry.register('paidFeature', new AdvancedWebhooksPaidFeature(context))
  $registry.register(
    'paidFeature',
    new FieldLevelPermissionsPaidFeature(context)
  )
  $registry.register('paidFeature', new SupportPaidFeature(context))
  $registry.register('paidFeature', new BuilderBrandingPaidFeature(context))
  $registry.register('paidFeature', new BuilderCustomCodePaidFeature(context))
  $registry.register(
    'paidFeature',
    new BuilderFileInputElementPaidFeature(context)
  )
  $registry.register('paidFeature', new BuilderGraphElementPaidFeature(context))
  $registry.register('paidFeature', new CodeRunnerPaidFeature(context))
  $registry.register('paidFeature', new XLSFileReaderPaidFeature(context))
  if ($featureFlagIsEnabled(FF_SEMANTIC_SEARCH)) {
    $registry.register('paidFeature', new SemanticSearchPaidFeature(context))
  }
  $registry.register('paidFeature', new DataScannerPaidFeature(context))
  $registry.register('paidFeature', new DateDependencyPaidFeature(context))
  $registry.register(
    'timelineFieldRules',
    new DateDependencyTimelineComponent(context)
  )
  $registry.register(
    'fieldContextItem',
    new DateDependencyContextItemType(context)
  )
  $registry.register(
    'builderPageDecorator',
    new MadeWithBaserowBuilderPageDecoratorType(context)
  )
  $registry.register(
    'databaseOnboardingStep',
    new AIDatabaseOnboardingStepType(context)
  )
  $registry.register('onboarding', new AIPromptOnboardingType(context))
  $registry.register(
    'fieldContextItem',
    new FieldPermissionsContextItemType(context)
  )
  $registry.register(
    'builderSettings',
    new CustomCodeBuilderSettingType(context)
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
