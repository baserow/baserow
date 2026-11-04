import {
  UploadFileUserFileUploadType,
  UploadViaURLUserFileUploadType,
} from '@baserow/modules/core/userFileUploadTypes'
import {
  BasicPermissionManagerType,
  CorePermissionManagerType,
  StaffPermissionManagerType,
  WorkspaceMemberPermissionManagerType,
  StaffOnlySettingOperationPermissionManagerType,
  AllowIfTemplateOperationPermissionManagerType,
} from '@baserow/modules/core/permissionManagerTypes'
import { CloudflareTurnstileCaptchaProviderType } from '@baserow/modules/core/captchaProviderTypes'
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
  RuntimeAbs,
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
  RuntimeNull,
  RuntimeNumberFormat,
  RuntimeToDuration,
  RuntimeDurationFormat,
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
  RuntimeEncodeUri,
  RuntimeEncodeUriComponent,
  RuntimeMarkdownToHtml,
  RuntimeSum,
  RuntimeAvg,
  RuntimeAt,
  RuntimeRange,
  RuntimeToArray,
  RuntimeToJson,
  RuntimeFromJson,
  RuntimeToDatetime,
} from '@baserow/modules/core/runtimeFormulaTypes'
import { AdminRoleType, MemberRoleType } from '@baserow/modules/core/roleTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const registry = nuxtApp.$registry
  registry.registerNamespace('plugin')
  registry.registerNamespace('chatRunType')
  registry.registerNamespace('permissionManager')
  registry.registerNamespace('application')
  registry.registerNamespace('authProvider')
  registry.registerNamespace('job')
  registry.registerNamespace('view')
  registry.registerNamespace('lastViewedItem')
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
  registry.registerNamespace('aiProviderModelFeature')
  registry.registerNamespace('onboarding')
  registry.registerNamespace('guidedTour')
  registry.registerNamespace('admin')
  registry.registerNamespace('workspaceSettingsPage')
  registry.registerNamespace('agentExtension')
  registry.registerNamespace('agentSettings')
  registry.registerNamespace('subject')
  registry.registerNamespace('errorPage')
  registry.registerNamespace('twoFactorAuth')
  registry.registerNamespace('captchaProvider')
  registry.registerNamespace('invitationRoute')
  registry.registerNamespace('invitationTarget')
  const context = { app: nuxtApp }
  registry.register('permissionManager', new CorePermissionManagerType(context))
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
  registry.register('userFileUpload', new UploadFileUserFileUploadType(context))
  registry.register(
    'userFileUpload',
    new UploadViaURLUserFileUploadType(context)
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
  registry.register('runtimeFormulaFunction', new RuntimeAbs(context))
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
  registry.register('runtimeFormulaFunction', new RuntimeGenerateUUID(context))
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
  registry.register('runtimeFormulaFunction', new RuntimeEncodeUri(context))
  registry.register(
    'runtimeFormulaFunction',
    new RuntimeEncodeUriComponent(context)
  )
  registry.register(
    'runtimeFormulaFunction',
    new RuntimeMarkdownToHtml(context)
  )
  registry.register('runtimeFormulaFunction', new RuntimeSum(context))
  registry.register('runtimeFormulaFunction', new RuntimeAvg(context))
  registry.register('runtimeFormulaFunction', new RuntimeAt(context))
  registry.register('runtimeFormulaFunction', new RuntimeToArray(context))
  registry.register('runtimeFormulaFunction', new RuntimeRange(context))
  registry.register('runtimeFormulaFunction', new RuntimeToJson(context))
  registry.register('runtimeFormulaFunction', new RuntimeFromJson(context))
  registry.register('runtimeFormulaFunction', new RuntimeNull(context))
  registry.register('runtimeFormulaFunction', new RuntimeNumberFormat(context))
  registry.register('runtimeFormulaFunction', new RuntimeToDuration(context))
  registry.register(
    'runtimeFormulaFunction',
    new RuntimeDurationFormat(context)
  )
  registry.register('runtimeFormulaFunction', new RuntimeToDatetime(context))
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
    'captchaProvider',
    new CloudflareTurnstileCaptchaProviderType(context)
  )
}
