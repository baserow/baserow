// plugins/baserow.js
import { defineNuxtPlugin } from '#app'

import { Registry } from '@baserow/modules/core/registry'
import { PasswordAuthProviderType } from '@baserow/modules/core/authProviderTypes'
import {
  CreateSnapshotJobType,
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
  MistralModelType,
  OpenRouterModelType,
} from '@baserow/modules/core/generativeAIModelTypes'
import {
  UploadFileUserFileUploadType,
  UploadViaURLUserFileUploadType,
} from '@baserow/modules/core/userFileUploadTypes'
import {
  DashboardAdminType,
  UsersAdminType,
  WorkspacesAdminType,
  HealthCheckAdminType,
  SettingsAdminType,
} from '@baserow/modules/core/adminTypes'

import {
  BasicPermissionManagerType,
  CorePermissionManagerType,
  StaffPermissionManagerType,
  WorkspaceMemberPermissionManagerType,
  StaffOnlySettingOperationPermissionManagerType,
  AllowIfTemplateOperationPermissionManagerType,
} from '@baserow/modules/core/permissionManagerTypes'

import {
  MembersWorkspaceSettingsPageType,
  InvitesWorkspaceSettingsPageType,
} from '@baserow/modules/core/workspaceSettingsPageTypes'
import {
  WorkspaceInvitationCreatedNotificationType,
  WorkspaceInvitationAcceptedNotificationType,
  WorkspaceInvitationRejectedNotificationType,
  BaserowVersionUpgradeNotificationType,
} from '@baserow/modules/core/notificationTypes'
import { MoreOnboardingType } from '@baserow/modules/core/onboardingTypes'
import { SidebarGuidedTourType } from '@baserow/modules/core/guidedTourTypes'
import { TOTPAuthType } from '@baserow/modules/core/twoFactorAuthTypes'

import { DefaultErrorPageType } from '@baserow/modules/core/errorPageTypes'

import {
  RuntimeAdd,
  RuntimeMinus,
  RuntimeMultiply,
  RuntimeDivide,
  RuntimeGreaterThan,
  RuntimeGreaterThanOrEqual,
  RuntimeLessThan,
  RuntimeLessThanOrEqual,
  RuntimeConcat,
  RuntimeGet,
  RuntimeEqual,
  RuntimeNotEqual,
  RuntimeUpper,
  RuntimeLower,
  RuntimeCapitalize,
  RuntimeRound,
  RuntimeIsEven,
  RuntimeIsOdd,
  RuntimeDateTimeFormat,
  RuntimeDay,
  RuntimeMonth,
  RuntimeYear,
  RuntimeHour,
  RuntimeMinute,
  RuntimeSecond,
  RuntimeNow,
  RuntimeToday,
  RuntimeGetProperty,
  RuntimeRandomInt,
  RuntimeRandomFloat,
  RuntimeRandomBool,
  RuntimeGenerateUUID,
  RuntimeIf,
  RuntimeAnd,
  RuntimeOr,
  RuntimeReplace,
  RuntimeLength,
  RuntimeContains,
  RuntimeReverse,
  RuntimeJoin,
  RuntimeSplit,
  RuntimeIsEmpty,
  RuntimeStrip,
  RuntimeSum,
  RuntimeAvg,
  RuntimeAt,
  RuntimeToArray,
} from '@baserow/modules/core/runtimeFormulaTypes'

import {
  AdminRoleType,
  MemberRoleType,
} from '@baserow/modules/database/roleTypes'

export default defineNuxtPlugin({
  name: 'core',
  dependsOn: ['priorityBus', 'registry', 'i18n'],
  setup(nuxtApp) {
    const registry = nuxtApp.$registry

    registry.registerNamespace('plugin')
    registry.registerNamespace('permissionManager')
    registry.registerNamespace('application')
    registry.registerNamespace('authProvider')
    registry.registerNamespace('job')
    registry.registerNamespace('view')
    registry.registerNamespace('field')
    registry.registerNamespace('settings')
    registry.registerNamespace('workspaceSettings')
    registry.registerNamespace('userFileUpload')
    registry.registerNamespace('membersPagePlugins')
    registry.registerNamespace('runtimeFormulaFunction')
    registry.registerNamespace('notification')
    registry.registerNamespace('workflowAction')
    registry.registerNamespace('integration')
    registry.registerNamespace('service')
    registry.registerNamespace('userSource')
    registry.registerNamespace('appAuthProvider')
    registry.registerNamespace('roles')
    registry.registerNamespace('generativeAIModel')
    registry.registerNamespace('onboarding')
    registry.registerNamespace('guidedTour')
    registry.registerNamespace('admin')
    registry.registerNamespace('workspaceSettingsPage')
    registry.registerNamespace('errorPage')
    registry.registerNamespace('twoFactorAuth')

    const context = { app: nuxtApp }

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
    registry.register('generativeAIModel', new MistralModelType(context))
    registry.register('generativeAIModel', new OllamaModelType(context))
    registry.register('generativeAIModel', new OpenRouterModelType(context))

    registry.register(
      'permissionManager',
      new CorePermissionManagerType(context)
    )
    registry.register(
      'permissionManager',
      new StaffPermissionManagerType(context)
    )
    registry.register(
      'permissionManager',
      new WorkspaceMemberPermissionManagerType(context)
    )
    registry.register(
      'permissionManager',
      new BasicPermissionManagerType(context)
    )
    registry.register(
      'permissionManager',
      new StaffOnlySettingOperationPermissionManagerType(context)
    )
    registry.register(
      'permissionManager',
      new AllowIfTemplateOperationPermissionManagerType(context)
    )

    registry.register(
      'userFileUpload',
      new UploadFileUserFileUploadType(context)
    )
    registry.register(
      'userFileUpload',
      new UploadViaURLUserFileUploadType(context)
    )

    registry.register('admin', new DashboardAdminType(context))
    registry.register('admin', new UsersAdminType(context))
    registry.register('admin', new WorkspacesAdminType(context))
    registry.register('admin', new SettingsAdminType(context))
    registry.register('admin', new HealthCheckAdminType(context))

    registry.register('authProvider', new PasswordAuthProviderType(context))

    registry.register('job', new DuplicateApplicationJobType(context))
    registry.register('job', new InstallTemplateJobType(context))
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
      new InvitesWorkspaceSettingsPageType(context)
    )

    registry.register('runtimeFormulaFunction', new RuntimeConcat(context))
    registry.register('runtimeFormulaFunction', new RuntimeGet(context))
    registry.register('runtimeFormulaFunction', new RuntimeAdd(context))
    registry.register('runtimeFormulaFunction', new RuntimeMinus(context))
    registry.register('runtimeFormulaFunction', new RuntimeMultiply(context))
    registry.register('runtimeFormulaFunction', new RuntimeDivide(context))
    registry.register('runtimeFormulaFunction', new RuntimeGreaterThan(context))
    registry.register(
      'runtimeFormulaFunction',
      new RuntimeGreaterThanOrEqual(context)
    )
    registry.register('runtimeFormulaFunction', new RuntimeLessThan(context))
    registry.register(
      'runtimeFormulaFunction',
      new RuntimeLessThanOrEqual(context)
    )
    registry.register('runtimeFormulaFunction', new RuntimeEqual(context))
    registry.register('runtimeFormulaFunction', new RuntimeNotEqual(context))
    registry.register('runtimeFormulaFunction', new RuntimeUpper(context))
    registry.register('runtimeFormulaFunction', new RuntimeLower(context))
    registry.register('runtimeFormulaFunction', new RuntimeCapitalize(context))
    registry.register('runtimeFormulaFunction', new RuntimeRound(context))
    registry.register('runtimeFormulaFunction', new RuntimeIsEven(context))
    registry.register('runtimeFormulaFunction', new RuntimeIsOdd(context))
    registry.register(
      'runtimeFormulaFunction',
      new RuntimeDateTimeFormat(context)
    )
    registry.register('runtimeFormulaFunction', new RuntimeDay(context))
    registry.register('runtimeFormulaFunction', new RuntimeMonth(context))
    registry.register('runtimeFormulaFunction', new RuntimeYear(context))
    registry.register('runtimeFormulaFunction', new RuntimeHour(context))
    registry.register('runtimeFormulaFunction', new RuntimeMinute(context))
    registry.register('runtimeFormulaFunction', new RuntimeSecond(context))
    registry.register('runtimeFormulaFunction', new RuntimeNow(context))
    registry.register('runtimeFormulaFunction', new RuntimeToday(context))
    registry.register('runtimeFormulaFunction', new RuntimeGetProperty(context))
    registry.register('runtimeFormulaFunction', new RuntimeRandomInt(context))
    registry.register('runtimeFormulaFunction', new RuntimeRandomFloat(context))
    registry.register('runtimeFormulaFunction', new RuntimeRandomBool(context))
    registry.register(
      'runtimeFormulaFunction',
      new RuntimeGenerateUUID(context)
    )
    registry.register('runtimeFormulaFunction', new RuntimeIf(context))
    registry.register('runtimeFormulaFunction', new RuntimeAnd(context))
    registry.register('runtimeFormulaFunction', new RuntimeOr(context))
    registry.register('runtimeFormulaFunction', new RuntimeReplace(context))
    registry.register('runtimeFormulaFunction', new RuntimeLength(context))
    registry.register('runtimeFormulaFunction', new RuntimeContains(context))
    registry.register('runtimeFormulaFunction', new RuntimeReverse(context))
    registry.register('runtimeFormulaFunction', new RuntimeJoin(context))
    registry.register('runtimeFormulaFunction', new RuntimeSplit(context))
    registry.register('runtimeFormulaFunction', new RuntimeIsEmpty(context))
    registry.register('runtimeFormulaFunction', new RuntimeStrip(context))
    registry.register('runtimeFormulaFunction', new RuntimeSum(context))
    registry.register('runtimeFormulaFunction', new RuntimeAvg(context))
    registry.register('runtimeFormulaFunction', new RuntimeAt(context))
    registry.register('runtimeFormulaFunction', new RuntimeToArray(context))
    registry.register('errorPage', new DefaultErrorPageType(context))

    const fns = [
      RuntimeConcat,
      RuntimeGet,
      RuntimeAdd,
      RuntimeMinus,
      RuntimeMultiply,
      RuntimeDivide,
      RuntimeGreaterThan,
      RuntimeGreaterThanOrEqual,
      RuntimeLessThan,
      RuntimeLessThanOrEqual,
      RuntimeEqual,
      RuntimeNotEqual,
      RuntimeUpper,
      RuntimeLower,
      RuntimeCapitalize,
      RuntimeRound,
      RuntimeIsEven,
      RuntimeIsOdd,
      RuntimeDateTimeFormat,
      RuntimeDay,
      RuntimeMonth,
      RuntimeYear,
      RuntimeHour,
      RuntimeMinute,
      RuntimeSecond,
      RuntimeNow,
      RuntimeToday,
      RuntimeGetProperty,
      RuntimeRandomInt,
      RuntimeRandomFloat,
      RuntimeRandomBool,
      RuntimeGenerateUUID,
      RuntimeIf,
      RuntimeAnd,
      RuntimeOr,
    ]

    fns.forEach((Fn) =>
      registry.register('runtimeFormulaFunction', new Fn(context))
    )

    registry.register('roles', new AdminRoleType(context))
    registry.register('roles', new MemberRoleType(context))

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

    registry.register('twoFactorAuth', new TOTPAuthType(context))

    registry.register('onboarding', new MoreOnboardingType(context))

    registry.register('guidedTour', new SidebarGuidedTourType(context))
  },
})
