import { PremiumDatabaseApplicationType } from '@baserow_premium/applicationTypes'
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
  JSONTableExporter,
  XMLTableExporter,
  ExcelTableExporterType,
  FileTableExporter,
} from '@baserow_premium/tableExporterTypes'
import rowCommentsStore from '@baserow_premium/store/row_comments'
import kanbanStore from '@baserow_premium/store/view/kanban'
import calendarStore from '@baserow_premium/store/view/calendar'
import timelineStore from '@baserow_premium/store/view/timeline'
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
import { GenerateAIValuesContextItemType } from '@baserow_premium/fieldContextItemTypes'
import { PersonalViewOwnershipType } from '@baserow_premium/viewOwnershipTypes'
import { CommentsRowModalSidebarType } from '@baserow_premium/rowModalSidebarTypes'
import {
  AIFieldType,
  PremiumFormulaFieldType,
} from '@baserow_premium/fieldTypes'
import {
  ChoiceAIFieldOutputType,
  TextAIFieldOutputType,
} from '@baserow_premium/aiFieldOutputTypes'

import GridViewRowExpandButtonWithCommentCount from '@baserow_premium/components/row_comments/GridViewRowExpandButtonWithCommentCount'
import PremiumViewOptions from '@baserow_premium/components/views/PremiumViewOptions'
import PublicViewExportMenuItem from '@baserow_premium/components/views/PublicViewExportMenuItem'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $registry, $store, $clientErrorMap, $i18n } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register('application', new PremiumDatabaseApplicationType(context))
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
  $store.registerModuleNuxtSafe('row_comments', rowCommentsStore)
  $store.registerModuleNuxtSafe('page/view/kanban', kanbanStore)
  $store.registerModuleNuxtSafe('page/view/calendar', calendarStore)
  $store.registerModuleNuxtSafe('page/view/timeline', timelineStore)
  $store.registerModuleNuxtSafe('template/view/kanban', kanbanStore)
  $store.registerModuleNuxtSafe('template/view/calendar', calendarStore)
  $store.registerModuleNuxtSafe('template/view/timeline', timelineStore)
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
  $registry.register(
    'rowModalSidebar',
    new CommentsRowModalSidebarType(context)
  )
  $registry.register('aiFieldOutputType', new TextAIFieldOutputType(context))
  $registry.register('aiFieldOutputType', new ChoiceAIFieldOutputType(context))
  $registry.register(
    'fieldContextItem',
    new GenerateAIValuesContextItemType(context)
  )
  $registry.register('groupedAggregation', new MinViewAggregationType(context))
  $registry.register('groupedAggregation', new MaxViewAggregationType(context))
  $registry.register('groupedAggregation', new SumViewAggregationType(context))
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
}

/** Read component bindings after Nitro has initialized the combined server chunk. */
export function getComponents() {
  return {
    GridViewRowExpandButtonWithCommentCount,
    PremiumViewOptions,
    PublicViewExportMenuItem,
  }
}
