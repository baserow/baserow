import { RuntimeGetEditor } from '@baserow/modules/core/formula/runtimeFormulaEditorTypes'
import {
  CreateSnapshotJobType,
  CreateUserTemplateJobType,
  DownloadUserTemplateJobType,
  DuplicateApplicationJobType,
  ExportApplicationsJobType,
  ImportApplicationsJobType,
  InstallTemplateJobType,
  RestoreSnapshotJobType,
} from '@baserow/modules/core/jobTypes'
import {
  AccountSettingsType,
  PasswordSettingsType,
  EmailSettingsType,
  EmailNotificationsSettingsType,
  MCPEndpointSettingsType,
  DeleteAccountSettingsType,
  TwoFactorAuthSettingsType,
} from '@baserow/modules/core/settingsTypes'
import { GenerativeAIWorkspaceSettingsType } from '@baserow/modules/core/workspaceSettingsTypes'
import {
  OpenAIModelType,
  OllamaModelType,
  AnthropicModelType,
  BedrockModelType,
  MistralModelType,
  OpenRouterModelType,
  GoogleModelType,
  GroqModelType,
  XaiModelType,
  ZaiModelType,
} from '@baserow/modules/core/generativeAIModelTypes'
import {
  AIProvidersAdminType,
  DashboardAdminType,
  UsersAdminType,
  WorkspacesAdminType,
  HealthCheckAdminType,
  SettingsAdminType,
} from '@baserow/modules/core/adminTypes'
import {
  MembersWorkspaceSettingsPageType,
  AgentsWorkspaceSettingsPageType,
} from '@baserow/modules/core/workspaceSettingsPageTypes'
import {
  WorkspaceInvitationCreatedNotificationType,
  WorkspaceInvitationAcceptedNotificationType,
  WorkspaceInvitationRejectedNotificationType,
  BaserowVersionUpgradeNotificationType,
  AbuseReportCreatedNotificationType,
} from '@baserow/modules/core/notificationTypes'
import { MoreOnboardingType } from '@baserow/modules/core/onboardingTypes'
import { SidebarGuidedTourType } from '@baserow/modules/core/guidedTourTypes'
import { TOTPAuthType } from '@baserow/modules/core/twoFactorAuthTypes'
import {
  GeneralAgentSettingsType,
  McpServerAgentSettingsType,
} from '@baserow/modules/core/agentSettingsTypes'
import {
  AgentSubjectType,
  AnonymousUserSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes.jsx'
import {
  EmailInvitationRouteType,
  LinkInvitationRouteType,
} from '@baserow/modules/core/invitationRouteTypes'
import { WorkspaceInvitationTargetType } from '@baserow/modules/core/invitationTargetTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const registry = nuxtApp.$registry
  const context = { app: nuxtApp }
  registry.unregister('runtimeFormulaFunction', 'get')
  registry.register('runtimeFormulaFunction', new RuntimeGetEditor(context))

  registry.register('subject', new UserSubjectType(context))
  registry.register('subject', new AnonymousUserSubjectType(context))
  registry.register('subject', new AgentSubjectType(context))
  registry.register('invitationRoute', new EmailInvitationRouteType(context))
  registry.register('invitationRoute', new LinkInvitationRouteType(context))
  registry.register(
    'invitationTarget',
    new WorkspaceInvitationTargetType(context)
  )
  registry.register('agentSettings', new GeneralAgentSettingsType(context))
  registry.register('agentSettings', new McpServerAgentSettingsType(context))
  registry.register('settings', new AccountSettingsType(context))
  registry.register('settings', new PasswordSettingsType(context))
  registry.register('settings', new EmailSettingsType(context))
  registry.register('settings', new EmailNotificationsSettingsType(context))
  registry.register('settings', new MCPEndpointSettingsType(context))
  registry.register('settings', new DeleteAccountSettingsType(context))
  registry.register('settings', new TwoFactorAuthSettingsType(context))
  registry.register(
    'workspaceSettings',
    new GenerativeAIWorkspaceSettingsType(context)
  )
  registry.register('generativeAIModel', new OpenAIModelType(context))
  registry.register('generativeAIModel', new AnthropicModelType(context))
  registry.register('generativeAIModel', new BedrockModelType(context))
  registry.register('generativeAIModel', new GoogleModelType(context))
  registry.register('generativeAIModel', new GroqModelType(context))
  registry.register('generativeAIModel', new XaiModelType(context))
  registry.register('generativeAIModel', new ZaiModelType(context))
  registry.register('generativeAIModel', new MistralModelType(context))
  registry.register('generativeAIModel', new OllamaModelType(context))
  registry.register('generativeAIModel', new OpenRouterModelType(context))
  registry.register('admin', new DashboardAdminType(context))
  registry.register('admin', new UsersAdminType(context))
  registry.register('admin', new WorkspacesAdminType(context))
  registry.register('admin', new AIProvidersAdminType(context))
  registry.register('admin', new SettingsAdminType(context))
  registry.register('admin', new HealthCheckAdminType(context))
  registry.register('job', new DuplicateApplicationJobType(context))
  registry.register('job', new InstallTemplateJobType(context))
  registry.register('job', new CreateUserTemplateJobType(context))
  registry.register('job', new DownloadUserTemplateJobType(context))
  registry.register('job', new CreateSnapshotJobType(context))
  registry.register('job', new RestoreSnapshotJobType(context))
  registry.register('job', new ExportApplicationsJobType(context))
  registry.register('job', new ImportApplicationsJobType(context))
  registry.register(
    'workspaceSettingsPage',
    new MembersWorkspaceSettingsPageType(context)
  )
  registry.register(
    'workspaceSettingsPage',
    new AgentsWorkspaceSettingsPageType(context)
  )
  registry.register(
    'notification',
    new WorkspaceInvitationCreatedNotificationType(context)
  )
  registry.register(
    'notification',
    new WorkspaceInvitationAcceptedNotificationType(context)
  )
  registry.register(
    'notification',
    new WorkspaceInvitationRejectedNotificationType(context)
  )
  registry.register(
    'notification',
    new BaserowVersionUpgradeNotificationType(context)
  )
  registry.register(
    'notification',
    new AbuseReportCreatedNotificationType(context)
  )
  registry.register('twoFactorAuth', new TOTPAuthType(context))
  registry.register('onboarding', new MoreOnboardingType(context))
  registry.register('guidedTour', new SidebarGuidedTourType(context))
}
