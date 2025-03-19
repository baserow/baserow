import { registerRealtimeEvents } from '@baserow_enterprise/realtime'
import { RolePermissionManagerType } from '@baserow_enterprise/permissionManagerTypes'
import { AuthProvidersType, AuditLogType } from '@baserow_enterprise/adminTypes'
import authProviderAdminStore from '@baserow_enterprise/store/authProviderAdmin'
import { PasswordAuthProviderType as CorePasswordAuthProviderType } from '@baserow/modules/core/authProviderTypes'
import {
  PasswordAuthProviderType,
  SamlAuthProviderType,
  GitHubAuthProviderType,
  GoogleAuthProviderType,
  FacebookAuthProviderType,
  GitLabAuthProviderType,
  OpenIdConnectAuthProviderType,
} from '@baserow_enterprise/authProviderTypes'
import { TeamsWorkspaceSettingsPageType } from '@baserow_enterprise/workspaceSettingsPageTypes'
import { EnterpriseMembersPagePluginType } from '@baserow_enterprise/membersPagePluginTypes'
import en from '@baserow_enterprise/locales/en.json'
import fr from '@baserow_enterprise/locales/fr.json'
import nl from '@baserow_enterprise/locales/nl.json'
import de from '@baserow_enterprise/locales/de.json'
import es from '@baserow_enterprise/locales/es.json'
import it from '@baserow_enterprise/locales/it.json'
import ko from '@baserow_enterprise/locales/ko.json'
import {
  EnterpriseWithoutSupportLicenseType,
  EnterpriseLicenseType,
} from '@baserow_enterprise/licenseTypes'
import { EnterprisePlugin } from '@baserow_enterprise/plugins'
import { LocalBaserowUserSourceType } from '@baserow_enterprise/integrations/userSourceTypes'
import {
  LocalBaserowPasswordAppAuthProviderType,
  SamlAppAuthProviderType,
  OpenIdConnectAppAuthProviderType,
} from '@baserow_enterprise/integrations/appAuthProviderTypes'
import { AuthFormElementType } from '@baserow_enterprise/builder/elementTypes'
import {
  EnterpriseAdminRoleType,
  EnterpriseMemberRoleType,
  EnterpriseBuilderRoleType,
  EnterpriseEditorRoleType,
  EnterpriseCommenterRoleType,
  EnterpriseViewerRoleType,
  NoAccessRoleType,
  NoRoleLowPriorityRoleType,
} from '@baserow_enterprise/roleTypes'
import {
  LocalBaserowTableDataSyncType,
  JiraIssuesDataSyncType,
  GitHubIssuesDataSyncType,
  GitLabIssuesDataSyncType,
  HubspotContactsDataSyncType,
} from '@baserow_enterprise/dataSyncTypes'
import { ChartWidgetType } from '@baserow_enterprise/dashboard/widgetTypes'
import { SingleSelectFormattingType } from '@baserow_enterprise/dashboard/chartFieldFormatting'
import { PeriodicIntervalFieldsConfigureDataSyncType } from '@baserow_enterprise/configureDataSyncTypes'
import {
  CountViewAggregationType,
  EmptyCountViewAggregationType,
  NotEmptyCountViewAggregationType,
  CheckedCountViewAggregationType,
  NotCheckedCountViewAggregationType,
  EmptyPercentageViewAggregationType,
  NotEmptyPercentageViewAggregationType,
  CheckedPercentageViewAggregationType,
  NotCheckedPercentageViewAggregationType,
  UniqueCountViewAggregationType,
  MinViewAggregationType,
  MaxViewAggregationType,
  SumViewAggregationType,
  AverageViewAggregationType,
  StdDevViewAggregationType,
  VarianceViewAggregationType,
  MedianViewAggregationType,
} from '@baserow/modules/database/viewAggregationTypes'
import { PeriodicDataSyncDeactivatedNotificationType } from '@baserow_enterprise/notificationTypes'
import { RowsEnterViewWebhookEventType } from '@baserow_enterprise/webhookEventTypes'
import {
  TextFieldType,
  LongTextFieldType,
  URLFieldType,
  EmailFieldType,
  NumberFieldType,
  RatingFieldType,
  BooleanFieldType,
  SingleSelectFieldType,
  PhoneNumberFieldType,
  AutonumberFieldType,
} from '@baserow/modules/database/fieldTypes'

export default (context) => {
  const { app, isDev, store } = context

  // Allow locale file hot reloading
  if (isDev && app.i18n) {
    const { i18n } = app
    i18n.mergeLocaleMessage('en', en)
    i18n.mergeLocaleMessage('fr', fr)
    i18n.mergeLocaleMessage('nl', nl)
    i18n.mergeLocaleMessage('de', de)
    i18n.mergeLocaleMessage('es', es)
    i18n.mergeLocaleMessage('it', it)
    i18n.mergeLocaleMessage('ko', ko)
  }

  app.$registry.register('plugin', new EnterprisePlugin(context))

  app.$registry.register(
    'permissionManager',
    new RolePermissionManagerType(context)
  )

  store.registerModule('authProviderAdmin', authProviderAdminStore)

  app.$registry.register('admin', new AuthProvidersType(context))
  app.$registry.unregister(
    'authProvider',
    new CorePasswordAuthProviderType(context)
  )
  app.$registry.register('authProvider', new PasswordAuthProviderType(context))
  app.$registry.register('authProvider', new SamlAuthProviderType(context))
  app.$registry.register('authProvider', new GoogleAuthProviderType(context))
  app.$registry.register('authProvider', new FacebookAuthProviderType(context))
  app.$registry.register('authProvider', new GitHubAuthProviderType(context))
  app.$registry.register('authProvider', new GitLabAuthProviderType(context))
  app.$registry.register(
    'authProvider',
    new OpenIdConnectAuthProviderType(context)
  )

  app.$registry.register('admin', new AuditLogType(context))
  app.$registry.register('plugin', new EnterprisePlugin(context))

  registerRealtimeEvents(app.$realtime)

  app.$registry.register(
    'membersPagePlugins',
    new EnterpriseMembersPagePluginType(context)
  )

  app.$registry.register(
    'workspaceSettingsPage',
    new TeamsWorkspaceSettingsPageType(context)
  )

  app.$registry.register(
    'license',
    new EnterpriseWithoutSupportLicenseType(context)
  )

  app.$registry.register('license', new EnterpriseLicenseType(context))

  app.$registry.register('userSource', new LocalBaserowUserSourceType(context))

  app.$registry.register(
    'appAuthProvider',
    new LocalBaserowPasswordAppAuthProviderType(context)
  )

  app.$registry.register(
    'appAuthProvider',
    new SamlAppAuthProviderType(context)
  )
  app.$registry.register(
    'appAuthProvider',
    new OpenIdConnectAppAuthProviderType(context)
  )

  app.$registry.register('roles', new EnterpriseAdminRoleType(context))
  app.$registry.register('roles', new EnterpriseMemberRoleType(context))
  app.$registry.register('roles', new EnterpriseBuilderRoleType(context))
  app.$registry.register('roles', new EnterpriseEditorRoleType(context))
  app.$registry.register('roles', new EnterpriseCommenterRoleType(context))
  app.$registry.register('roles', new EnterpriseViewerRoleType(context))
  app.$registry.register('roles', new NoAccessRoleType(context))
  app.$registry.register('roles', new NoRoleLowPriorityRoleType(context))

  app.$registry.register('element', new AuthFormElementType(context))

  app.$registry.register('dataSync', new LocalBaserowTableDataSyncType(context))
  app.$registry.register('dataSync', new JiraIssuesDataSyncType(context))
  app.$registry.register('dataSync', new GitHubIssuesDataSyncType(context))
  app.$registry.register('dataSync', new GitLabIssuesDataSyncType(context))
  app.$registry.register('dataSync', new HubspotContactsDataSyncType(context))

  app.$registry.register(
    'groupedAggregation',
    new MinViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new MaxViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new SumViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new AverageViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new MedianViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new StdDevViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new VarianceViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new CountViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new EmptyCountViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new NotEmptyCountViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new CheckedCountViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new NotCheckedCountViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new EmptyPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new NotEmptyPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new CheckedPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new NotCheckedPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'groupedAggregation',
    new UniqueCountViewAggregationType(context)
  )

  app.$registry.register(
    'groupedAggregationGroupedBy',
    new TextFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new LongTextFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new NumberFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new URLFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new RatingFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new BooleanFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new EmailFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new SingleSelectFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new PhoneNumberFieldType(context)
  )
  app.$registry.register(
    'groupedAggregationGroupedBy',
    new AutonumberFieldType(context)
  )

  app.$registry.register(
    'notification',
    new PeriodicDataSyncDeactivatedNotificationType(context)
  )

  app.$registry.register(
    'configureDataSync',
    new PeriodicIntervalFieldsConfigureDataSyncType(context)
  )

  app.$registry.register(
    'webhookEvent',
    new RowsEnterViewWebhookEventType(context)
  )

  app.$registry.register('dashboardWidget', new ChartWidgetType(context))
  app.$registry.register(
    'chartFieldFormatting',
    new SingleSelectFormattingType(context)
  )
}
