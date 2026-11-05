import { KumaAIProviderModelFeatureType } from '@baserow_enterprise/aiProviderModelFeatureTypes'
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
import { EnterprisePlugin } from '@baserow_enterprise/plugins'
import {
  ApplicationUserLimitNotificationType,
  DataScanNewResultsNotificationType,
  PeriodicDataSyncDeactivatedNotificationType,
  TwoWayDataSyncUpdateFiledNotificationType,
  TwoWaySyncDeactivatedNotificationType,
} from '@baserow_enterprise/notificationTypes'
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
import { AIPromptOnboardingType } from '@baserow_enterprise/onboardingTypes'
import { FF_SEMANTIC_SEARCH } from '@baserow/modules/core/plugins/featureFlags'

/** Register shared shell features; application-specific UI is initialized separately. */
export default async function register(nuxtApp) {
  const { $registry, $store, $featureFlagIsEnabled } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register(
    'aiProviderModelFeature',
    new KumaAIProviderModelFeatureType(context)
  )
  $registry.register('plugin', new EnterprisePlugin(context))
  $store.registerModuleNuxtSafe('authProviderAdmin', authProviderAdminStore)
  $store.registerModuleNuxtSafe('assistant', assistantStore)
  $registry.register('admin', new AuthProvidersType(context))
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
  $registry.register('onboarding', new AIPromptOnboardingType(context))
}
