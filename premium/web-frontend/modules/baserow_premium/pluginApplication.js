import { AIFieldsAIProviderModelFeatureType } from '@baserow_premium/aiProviderModelFeatureTypes'
import { registerViewMetadata } from '@baserow/modules/database/viewMetadata'
import { PREMIUM_VIEW_METADATA } from '@baserow_premium/viewMetadata'
import { PremiumPlugin } from '@baserow_premium/plugins'
import { LicensesAdminType } from '@baserow_premium/adminTypes'
import impersonatingStore from '@baserow_premium/store/impersonating'
import { PremiumDatabaseApplicationType } from '@baserow_premium/applicationTypes'
import { GenerateAIValuesJobType } from '@baserow_premium/jobTypes'
import { ViewOwnershipPermissionManagerType } from '@baserow_premium/permissionManagerTypes'
import {
  RowCommentMentionNotificationType,
  RowCommentNotificationType,
} from '@baserow_premium/notificationTypes'
import {
  AIPaidFeature,
  CalendarViewPaidFeature,
  ExportsPaidFeature,
  FormSurveyModePaidFeature,
  GroupedAggregateRowsDataSourcePaidFeature,
  KanbanViewPaidFeature,
  PersonalViewsPaidFeature,
  PublicLogoRemovalPaidFeature,
  RowColoringPaidFeature,
  RowCommentsPaidFeature,
  RowNotificationsPaidFeature,
  TimelineViewPaidFeature,
  ChartPaidFeature,
} from '@baserow_premium/paidFeatures'

/** Register shared shell features; application-specific UI is initialized separately. */
export default async function register(nuxtApp) {
  const { $registry, $store, $clientErrorMap } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register(
    'aiProviderModelFeature',
    new AIFieldsAIProviderModelFeatureType(context)
  )
  registerViewMetadata(nuxtApp, PREMIUM_VIEW_METADATA)
  $clientErrorMap.setError(
    'ERROR_FEATURE_NOT_AVAILABLE',
    'License required',
    'This functionality requires an active premium license. Please refresh the page.'
  )
  $store.registerModuleNuxtSafe('impersonating', impersonatingStore)
  $registry.register('plugin', new PremiumPlugin(context))
  $registry.register('admin', new LicensesAdminType(context))
  $registry.register(
    'permissionManager',
    new ViewOwnershipPermissionManagerType(context)
  )
  $registry.register('application', new PremiumDatabaseApplicationType(context))
  $registry.register(
    'notification',
    new RowCommentMentionNotificationType(context)
  )
  $registry.register('notification', new RowCommentNotificationType(context))
  $registry.register('job', new GenerateAIValuesJobType(context))
  $registry.register('paidFeature', new KanbanViewPaidFeature(context))
  $registry.register('paidFeature', new CalendarViewPaidFeature(context))
  $registry.register('paidFeature', new TimelineViewPaidFeature(context))
  $registry.register('paidFeature', new RowColoringPaidFeature(context))
  $registry.register('paidFeature', new RowCommentsPaidFeature(context))
  $registry.register('paidFeature', new RowNotificationsPaidFeature(context))
  $registry.register('paidFeature', new AIPaidFeature(context))
  $registry.register(
    'paidFeature',
    new GroupedAggregateRowsDataSourcePaidFeature(context)
  )
  $registry.register('paidFeature', new PersonalViewsPaidFeature(context))
  $registry.register('paidFeature', new ExportsPaidFeature(context))
  $registry.register('paidFeature', new FormSurveyModePaidFeature(context))
  $registry.register('paidFeature', new PublicLogoRemovalPaidFeature(context))
  $registry.register('paidFeature', new ChartPaidFeature(context))
}
