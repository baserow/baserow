import { AuditLogExportJobType } from '@baserow_enterprise/jobTypes'
import { registerRealtimeEvents } from '@baserow_enterprise/realtime'
import {
  RolePermissionManagerType,
  WriteFieldValuesPermissionManagerType,
} from '@baserow_enterprise/permissionManagerTypes'
import { AuditLogType, AuthProvidersType } from '@baserow_enterprise/adminTypes'
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
import { EnterpriseMembersPagePluginType } from '@baserow_enterprise/membersPagePluginTypes'
import {
  AdvancedLicenseType,
  EnterpriseLicenseType,
  EnterpriseWithoutSupportLicenseType,
} from '@baserow_enterprise/licenseTypes'
import { EnterprisePlugin } from '@baserow_enterprise/plugins'
import { LocalBaserowUserSourceType } from '@baserow_enterprise/integrations/userSourceTypes'
import {
  LocalBaserowPasswordAppAuthProviderType,
  OpenIdConnectAppAuthProviderType,
  SamlAppAuthProviderType,
} from '@baserow_enterprise/integrations/appAuthProviderTypes'
import {
  AuthFormElementType,
  FileInputElementType,
} from '@baserow_enterprise/builder/elementTypes'
import {
  EnterpriseAdminRoleType,
  EnterpriseBuilderRoleType,
  EnterpriseCommenterRoleType,
  EnterpriseEditorRoleType,
  EnterpriseMemberRoleType,
  EnterpriseViewerRoleType,
  NoAccessRoleType,
  NoRoleLowPriorityRoleType,
} from '@baserow_enterprise/roleTypes'
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
  CoBrandingPaidFeature,
  DataSyncPaidFeature,
  DateDependencyPaidFeature,
  FieldLevelPermissionsPaidFeature,
  RBACPaidFeature,
  SSOPaidFeature,
  SupportPaidFeature,
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

export default defineNuxtPlugin({
  name: 'enterprise',
  dependsOn: ['premium', 'registry'],
  setup(nuxtApp) {
    const { $registry, $store, $featureFlagIsEnabled } = nuxtApp

    const context = { app: nuxtApp }

    $registry.register('plugin', new EnterprisePlugin(context))

    $registry.register(
      'permissionManager',
      new RolePermissionManagerType(context)
    )
    $registry.register(
      'permissionManager',
      new WriteFieldValuesPermissionManagerType(context)
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
    $registry.register(
      'authProvider',
      new OpenIdConnectAuthProviderType(context)
    )

    $registry.register('admin', new AuditLogType(context))
    $registry.register('plugin', new EnterprisePlugin(context))

    $registry.register(
      'membersPagePlugins',
      new EnterpriseMembersPagePluginType(context)
    )

    $registry.register(
      'workspaceSettingsPage',
      new TeamsWorkspaceSettingsPageType(context)
    )

    $registry.register('job', new AuditLogExportJobType(context))

    $registry.register('license', new AdvancedLicenseType(context))
    $registry.register(
      'license',
      new EnterpriseWithoutSupportLicenseType(context)
    )
    $registry.register('license', new EnterpriseLicenseType(context))

    $registry.register('userSource', new LocalBaserowUserSourceType(context))

    $registry.register(
      'appAuthProvider',
      new LocalBaserowPasswordAppAuthProviderType(context)
    )

    $registry.register('appAuthProvider', new SamlAppAuthProviderType(context))
    $registry.register(
      'appAuthProvider',
      new OpenIdConnectAppAuthProviderType(context)
    )

    $registry.register('roles', new EnterpriseAdminRoleType(context))
    $registry.register('roles', new EnterpriseMemberRoleType(context))
    $registry.register('roles', new EnterpriseBuilderRoleType(context))
    $registry.register('roles', new EnterpriseEditorRoleType(context))
    $registry.register('roles', new EnterpriseCommenterRoleType(context))
    $registry.register('roles', new EnterpriseViewerRoleType(context))
    $registry.register('roles', new NoAccessRoleType(context))
    $registry.register('roles', new NoRoleLowPriorityRoleType(context))

    $registry.register('element', new AuthFormElementType(context))
    $registry.register('element', new FileInputElementType(context))

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
      'configureDataSync',
      new PeriodicIntervalFieldsConfigureDataSyncType(context)
    )

    $registry.register(
      'webhookEvent',
      new RowsEnterViewWebhookEventType(context)
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

    $registry.register('paidFeature', new DateDependencyPaidFeature(context))
    $registry.register(
      'timelineFieldRules',
      new DateDependencyTimelineComponent(context)
    )
    $registry.register(
      'fieldContextItem',
      new DateDependencyContextItemType(context)
    )

    // Register builder page decorator namespace and types
    $registry.register(
      'builderPageDecorator',
      new MadeWithBaserowBuilderPageDecoratorType(context)
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
      'builderSettings',
      new CustomCodeBuilderSettingType(context)
    )

    $registry.register(
      'twoWaySyncStrategy',
      new RealtimePushTwoWaySyncStrategyType(context)
    )

    if ($featureFlagIsEnabled('view_permissions')) {
      $registry.register(
        'viewOwnershipType',
        new RestrictedViewOwnershipType(context)
      )
    }
  },
})
