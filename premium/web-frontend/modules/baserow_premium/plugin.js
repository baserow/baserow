import { PremiumPlugin } from '@baserow_premium/plugins'
import {
  JSONTableExporter,
  XMLTableExporter,
  ExcelTableExporterType,
  FileTableExporter,
} from '@baserow_premium/tableExporterTypes'
import { LicensesAdminType } from '@baserow_premium/adminTypes'
import rowCommentsStore from '@baserow_premium/store/row_comments'
import kanbanStore from '@baserow_premium/store/view/kanban'
import calendarStore from '@baserow_premium/store/view/calendar'
import timelineStore from '@baserow_premium/store/view/timeline'
import impersonatingStore from '@baserow_premium/store/impersonating'
import { PremiumDatabaseApplicationType } from '@baserow_premium/applicationTypes'

import {
  KanbanViewType,
  CalendarViewType,
  TimelineViewType,
} from '@baserow_premium/viewTypes'

import {
  LeftBorderColorViewDecoratorType,
  BackgroundColorViewDecoratorType,
} from '@baserow_premium/viewDecorators'

import {
  SingleSelectColorValueProviderType,
  ConditionalColorValueProviderType,
} from '@baserow_premium/decoratorValueProviders'
import { FormViewSurveyModeType } from '@baserow_premium/formViewModeTypes'
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
import {
  ChartWidgetType,
  PieChartWidgetType,
} from '@baserow_premium/dashboard/widgetTypes'
import { SingleSelectFormattingType } from '@baserow_premium/dashboard/chartFieldFormatting'
import { GenerateAIValuesJobType } from '@baserow_premium/jobTypes'
import { GenerateAIValuesContextItemType } from '@baserow_premium/fieldContextItemTypes'
import { PremiumLicenseType } from '@baserow_premium/licenseTypes'
import { PersonalViewOwnershipType } from '@baserow_premium/viewOwnershipTypes'
import { ViewOwnershipPermissionManagerType } from '@baserow_premium/permissionManagerTypes'
import {
  RowCommentMentionNotificationType,
  RowCommentNotificationType,
} from '@baserow_premium/notificationTypes'
import { CommentsRowModalSidebarType } from '@baserow_premium/rowModalSidebarTypes'
import {
  AIFieldType,
  PremiumFormulaFieldType,
} from '@baserow_premium/fieldTypes'
import {
  ChoiceAIFieldOutputType,
  TextAIFieldOutputType,
} from '@baserow_premium/aiFieldOutputTypes'
import {
  AIPaidFeature,
  CalendarViewPaidFeature,
  ExportsPaidFeature,
  FormSurveyModePaidFeature,
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
    $registry.register('exporter', new JSONTableExporter(context))
    $registry.register('exporter', new XMLTableExporter(context))
    $registry.register('exporter', new ExcelTableExporterType(context))
    $registry.register('exporter', new FileTableExporter(context))
    $registry.register('field', new AIFieldType(context))
    $registry.register('field', new PremiumFormulaFieldType(context))
    $registry.register('view', new KanbanViewType(context))
    $registry.register('view', new CalendarViewType(context))
    $registry.register('view', new TimelineViewType(context))

    $registry.register(
      'viewDecorator',
      new LeftBorderColorViewDecoratorType(context)
    )
    $registry.register(
      'viewDecorator',
      new BackgroundColorViewDecoratorType(context)
    )

    $registry.register(
      'decoratorValueProvider',
      new SingleSelectColorValueProviderType(context)
    )
    $registry.register(
      'decoratorValueProvider',
      new ConditionalColorValueProviderType(context)
    )

    $registry.register(
      'viewOwnershipType',
      new PersonalViewOwnershipType(context)
    )

    $registry.register('formViewMode', new FormViewSurveyModeType(context))

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

    $registry.register(
      'rowModalSidebar',
      new CommentsRowModalSidebarType(context)
    )

    $registry.register('aiFieldOutputType', new TextAIFieldOutputType(context))
    $registry.register(
      'aiFieldOutputType',
      new ChoiceAIFieldOutputType(context)
    )

    $registry.register('job', new GenerateAIValuesJobType(context))

    $registry.register(
      'fieldContextItem',
      new GenerateAIValuesContextItemType(context)
    )

    $registry.register(
      'groupedAggregation',
      new MinViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new MaxViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new SumViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new AverageViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new MedianViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new StdDevViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new VarianceViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new CountViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new EmptyCountViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new NotEmptyCountViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new CheckedCountViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new NotCheckedCountViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new EmptyPercentageViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new NotEmptyPercentageViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new CheckedPercentageViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new NotCheckedPercentageViewAggregationType(context)
    )
    $registry.register(
      'groupedAggregation',
      new UniqueCountViewAggregationType(context)
    )

    $registry.register(
      'groupedAggregationGroupedBy',
      new TextFieldType(context)
    )
    $registry.register(
      'groupedAggregationGroupedBy',
      new LongTextFieldType(context)
    )
    $registry.register(
      'groupedAggregationGroupedBy',
      new NumberFieldType(context)
    )
    $registry.register('groupedAggregationGroupedBy', new URLFieldType(context))
    $registry.register(
      'groupedAggregationGroupedBy',
      new RatingFieldType(context)
    )
    $registry.register(
      'groupedAggregationGroupedBy',
      new BooleanFieldType(context)
    )
    $registry.register(
      'groupedAggregationGroupedBy',
      new EmailFieldType(context)
    )
    $registry.register(
      'groupedAggregationGroupedBy',
      new SingleSelectFieldType(context)
    )
    $registry.register(
      'groupedAggregationGroupedBy',
      new PhoneNumberFieldType(context)
    )
    $registry.register(
      'groupedAggregationGroupedBy',
      new AutonumberFieldType(context)
    )

    $registry.register('dashboardWidget', new ChartWidgetType(context))
    $registry.register('dashboardWidget', new PieChartWidgetType(context))
    $registry.register(
      'chartFieldFormatting',
      new SingleSelectFormattingType(context)
    )

    $registry.register('paidFeature', new KanbanViewPaidFeature(context))
    $registry.register('paidFeature', new CalendarViewPaidFeature(context))
    $registry.register('paidFeature', new TimelineViewPaidFeature(context))
    $registry.register('paidFeature', new RowColoringPaidFeature(context))
    $registry.register('paidFeature', new RowCommentsPaidFeature(context))
    $registry.register('paidFeature', new RowNotificationsPaidFeature(context))
    $registry.register('paidFeature', new AIPaidFeature(context))
    $registry.register('paidFeature', new PersonalViewsPaidFeature(context))
    $registry.register('paidFeature', new ExportsPaidFeature(context))
    $registry.register('paidFeature', new FormSurveyModePaidFeature(context))
    $registry.register('paidFeature', new PublicLogoRemovalPaidFeature(context))
    $registry.register('paidFeature', new ChartPaidFeature(context))

    $registry.registerNamespace('timelineFieldRules')
  },
})
