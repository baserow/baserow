import {
  JSONTableExporter,
  XMLTableExporter,
  ExcelTableExporterType,
  FileTableExporter,
} from '@baserow_premium/tableExporterTypes'
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

export default function registerPremiumDatabaseDomain(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }

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

  $registry.register('groupedAggregationGroupedBy', new TextFieldType(context))
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
  $registry.register('groupedAggregationGroupedBy', new EmailFieldType(context))
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
}
