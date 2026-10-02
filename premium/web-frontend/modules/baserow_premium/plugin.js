import { PremiumPlugin } from '@baserow_premium/plugins'
import { LicensesAdminType } from '@baserow_premium/adminTypes'
import rowCommentsStore from '@baserow_premium/store/row_comments'
import kanbanStore from '@baserow_premium/store/view/kanban'
import calendarStore from '@baserow_premium/store/view/calendar'
import timelineStore from '@baserow_premium/store/view/timeline'
import impersonatingStore from '@baserow_premium/store/impersonating'
import { PremiumDatabaseApplicationType } from '@baserow_premium/applicationTypes'

import { LocalBaserowGroupedAggregateRowsServiceType } from '@baserow_premium/integrations/localBaserow/serviceTypes'
import { GenerateAIValuesJobType } from '@baserow_premium/jobTypes'
import { PremiumLicenseType } from '@baserow_premium/licenseTypes'
import { ViewOwnershipPermissionManagerType } from '@baserow_premium/permissionManagerTypes'
import {
  RowCommentMentionNotificationType,
  RowCommentNotificationType,
} from '@baserow_premium/notificationTypes'
import { AIFieldsAIProviderModelFeatureType } from '@baserow_premium/aiProviderModelFeatureTypes'
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

export default defineNuxtPlugin({
  name: 'premium',
  dependsOn: ['core', 'builder', 'database', 'client-handler'],
  setup(nuxtApp) {
    const { $registry, $store, $clientErrorMap, $i18n } = nuxtApp

    const context = { app: nuxtApp }

    $clientErrorMap.setError(
      'ERROR_FEATURE_NOT_AVAILABLE',
      'License required',
      'This functionality requires an active premium license. Please refresh the page.'
    )

    $clientErrorMap.setError(
      'ERROR_USER_NOT_COMMENT_AUTHOR',
      $i18n.t('rowComment.errorUserNotCommentAuthorTitle'),
      $i18n.t('rowComment.errorUserNotCommentAuthor')
    )
    $clientErrorMap.setError(
      'ERROR_INVALID_COMMENT_MENTION',
      $i18n.t('rowComment.errorInvalidCommentMentionTitle'),
      $i18n.t('rowComment.errorInvalidCommentMention')
    )

    // Allow locale file hot reloading
    /* if (isDev && $i18n) {
      const { i18n } = app
      i18n.mergeLocaleMessage('en', en)
      i18n.mergeLocaleMessage('fr', fr)
      i18n.mergeLocaleMessage('nl', nl)
      i18n.mergeLocaleMessage('de', de)
      i18n.mergeLocaleMessage('es', es)
      i18n.mergeLocaleMessage('it', it)
      i18n.mergeLocaleMessage('pl', pl)
      i18n.mergeLocaleMessage('ko', ko)
    }*/

    $store.registerModuleNuxtSafe('row_comments', rowCommentsStore)
    $store.registerModuleNuxtSafe('page/view/kanban', kanbanStore)
    $store.registerModuleNuxtSafe('page/view/calendar', calendarStore)
    $store.registerModuleNuxtSafe('page/view/timeline', timelineStore)
    $store.registerModuleNuxtSafe('template/view/kanban', kanbanStore)
    $store.registerModuleNuxtSafe('template/view/calendar', calendarStore)
    $store.registerModuleNuxtSafe('template/view/timeline', timelineStore)
    $store.registerModuleNuxtSafe('impersonating', impersonatingStore)

    $registry.registerNamespace('aiFieldOutputType')
    $registry.registerNamespace('paidFeature')
    $registry.registerNamespace('license')
    $registry.registerNamespace('groupedAggregation')
    $registry.registerNamespace('groupedAggregationGroupedBy')
    $registry.registerNamespace('chartFieldFormatting')

    $registry.register('plugin', new PremiumPlugin(context))
    $registry.register('admin', new LicensesAdminType(context))
    $registry.register(
      'aiProviderModelFeature',
      new AIFieldsAIProviderModelFeatureType(context)
    )

    $registry.register('license', new PremiumLicenseType(context))

    $registry.register(
      'permissionManager',
      new ViewOwnershipPermissionManagerType(context)
    )

    // Overwrite the existing database application type with the one customized for
    // premium use.
    $registry.register(
      'application',
      new PremiumDatabaseApplicationType(context)
    )
    $registry.register(
      'notification',
      new RowCommentMentionNotificationType(context)
    )
    $registry.register('notification', new RowCommentNotificationType(context))

    $registry.register('job', new GenerateAIValuesJobType(context))

    $registry.registerDomainLoader('database', async () => {
      const { default: register } =
        await import('@baserow_premium/databaseLazyRegistrations')
      register(nuxtApp)
    })

    $registry.register(
      'service',
      new LocalBaserowGroupedAggregateRowsServiceType(context)
    )

    $registry.registerDomainLoader('dashboard', async () => {
      const { default: register } =
        await import('@baserow_premium/dashboardLazyRegistrations')
      register(nuxtApp)
    })

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

    $registry.registerNamespace('timelineFieldRules')
  },
})
