import { defineNuxtPlugin } from '#app'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import {
  DuplicateTableJobType,
  SyncDataSyncTableJobType,
  FileImportJobType,
  DuplicateFieldJobType,
  AirtableJobType,
} from '@baserow/modules/database/jobTypes'
import {
  GridViewType,
  GalleryViewType,
  FormViewType,
} from '@baserow/modules/database/viewTypes'
import {
  TextFieldType,
  LongTextFieldType,
  URLFieldType,
  EmailFieldType,
  LinkRowFieldType,
  NumberFieldType,
  RatingFieldType,
  BooleanFieldType,
  DateFieldType,
  LastModifiedFieldType,
  LastModifiedByFieldType,
  FileFieldType,
  SingleSelectFieldType,
  MultipleSelectFieldType,
  PhoneNumberFieldType,
  CreatedOnFieldType,
  CreatedByFieldType,
  DurationFieldType,
  FormulaFieldType,
  CountFieldType,
  RollupFieldType,
  LookupFieldType,
  MultipleCollaboratorsFieldType,
  UUIDFieldType,
  AutonumberFieldType,
  PasswordFieldType,
} from '@baserow/modules/database/fieldTypes'
import {
  EqualViewFilterType,
  NotEqualViewFilterType,
  ContainsViewFilterType,
  FilenameContainsViewFilterType,
  FilesLowerThanViewFilterType,
  HasFileTypeViewFilterType,
  ContainsNotViewFilterType,
  LengthIsLowerThanViewFilterType,
  HigherThanViewFilterType,
  HigherThanOrEqualViewFilterType,
  LowerThanViewFilterType,
  LowerThanOrEqualViewFilterType,
  IsEvenAndWholeViewFilterType,
  SingleSelectEqualViewFilterType,
  SingleSelectNotEqualViewFilterType,
  SingleSelectIsAnyOfViewFilterType,
  SingleSelectIsNoneOfViewFilterType,
  BooleanViewFilterType,
  EmptyViewFilterType,
  NotEmptyViewFilterType,
  LinkRowHasFilterType,
  LinkRowHasNotFilterType,
  MultipleSelectHasFilterType,
  MultipleSelectHasNotFilterType,
  MultipleCollaboratorsHasFilterType,
  MultipleCollaboratorsHasNotFilterType,
  LinkRowContainsFilterType,
  LinkRowNotContainsFilterType,
  ContainsWordViewFilterType,
  DoesntContainWordViewFilterType,
  UserIsFilterType,
  UserIsNotFilterType,
  DateIsEqualMultiStepViewFilterType,
  DateIsBeforeMultiStepViewFilterType,
  DateIsOnOrBeforeMultiStepViewFilterType,
  DateIsAfterMultiStepViewFilterType,
  DateIsOnOrAfterMultiStepViewFilterType,
  DateIsWithinMultiStepViewFilterType,
  DateIsNotEqualMultiStepViewFilterType,
  // Deprecated date filter types
  DateEqualViewFilterType,
  DateNotEqualViewFilterType,
  DateEqualsTodayViewFilterType,
  DateBeforeTodayViewFilterType,
  DateAfterTodayViewFilterType,
  DateWithinDaysViewFilterType,
  DateWithinWeeksViewFilterType,
  DateWithinMonthsViewFilterType,
  DateEqualsDaysAgoViewFilterType,
  DateEqualsMonthsAgoViewFilterType,
  DateEqualsYearsAgoViewFilterType,
  DateEqualsCurrentWeekViewFilterType,
  DateEqualsCurrentMonthViewFilterType,
  DateEqualsCurrentYearViewFilterType,
  DateBeforeViewFilterType,
  DateBeforeOrEqualViewFilterType,
  DateAfterDaysAgoViewFilterType,
  DateAfterViewFilterType,
  DateAfterOrEqualViewFilterType,
  DateEqualsDayOfMonthViewFilterType,
} from '@baserow/modules/database/viewFilters'
import {
  HasValueEqualViewFilterType,
  HasEmptyValueViewFilterType,
  HasNotEmptyValueViewFilterType,
  HasNotValueEqualViewFilterType,
  HasValueContainsViewFilterType,
  HasNotValueContainsViewFilterType,
  HasValueContainsWordViewFilterType,
  HasNotValueContainsWordViewFilterType,
  HasValueLengthIsLowerThanViewFilterType,
  HasAllValuesEqualViewFilterType,
  HasAnySelectOptionEqualViewFilterType,
  HasNoneSelectOptionEqualViewFilterType,
  HasValueLowerThanViewFilterType,
  HasValueLowerThanOrEqualViewFilterType,
  HasValueHigherThanViewFilterType,
  HasValueHigherThanOrEqualViewFilterType,
  HasNotValueLowerThanOrEqualViewFilterType,
  HasNotValueLowerThanViewFilterType,
  HasNotValueHigherThanOrEqualViewFilterType,
  HasNotValueHigherThanViewFilterType,
  HasDateEqualViewFilterType,
  HasNotDateEqualViewFilterType,
  HasDateBeforeViewFilterType,
  HasNotDateBeforeViewFilterType,
  HasDateOnOrBeforeViewFilterType,
  HasNotDateOnOrBeforeViewFilterType,
  HasDateAfterViewFilterType,
  HasNotDateAfterViewFilterType,
  HasDateOnOrAfterViewFilterType,
  HasNotDateOnOrAfterViewFilterType,
  HasDateWithinViewFilterType,
  HasNotDateWithinViewFilterType,
} from '@baserow/modules/database/arrayViewFilters'
import {
  CSVImporterType,
  PasteImporterType,
  XMLImporterType,
  JSONImporterType,
} from '@baserow/modules/database/importerTypes'
import {
  ICalCalendarDataSyncType,
  PostgreSQLDataSyncType,
} from '@baserow/modules/database/dataSyncTypes'
import {
  RowsCreatedWebhookEventType,
  RowsUpdatedWebhookEventType,
  RowsDeletedWebhookEventType,
  FieldCreatedWebhookEventType,
  FieldUpdatedWebhookEventType,
  FieldDeletedWebhookEventType,
  ViewCreatedWebhookEventType,
  ViewUpdatedWebhookEventType,
  ViewDeletedWebhookEventType,
} from '@baserow/modules/database/webhookEventTypes'
import {
  ImageFilePreview,
  AudioFilePreview,
  VideoFilePreview,
  PDFBrowserFilePreview,
  GoogleDocFilePreview,
} from '@baserow/modules/database/filePreviewTypes'

import {
  TextTypeUniqueWithEmptyConstraintType,
  RatingTypeUniqueWithEmptyConstraintType,
  GenericUniqueWithEmptyConstraintType,
} from '@baserow/modules/database/fieldConstraintTypes'

import { APITokenSettingsType } from '@baserow/modules/database/settingsTypes'

import { CSVTableExporterType } from '@baserow/modules/database/exporterTypes'
import {
  BaserowAdd,
  BaserowAnd,
  BaserowConcat,
  BaserowDateDiff,
  BaserowDateInterval,
  BaserowDatetimeFormat,
  BaserowDatetimeFormatTz,
  BaserowDay,
  BaserowDivide,
  BaserowEncodeUri,
  BaserowEncodeUriComponent,
  BaserowEqual,
  BaserowHasOption,
  BaserowField,
  BaserowSearch,
  BaserowGreaterThan,
  BaserowGreaterThanOrEqual,
  BaserowIf,
  BaserowIsBlank,
  BaserowIsNull,
  BaserowDurationToSeconds,
  BaserowSecondsToDuration,
  BaserowLessThan,
  BaserowLessThanOrEqual,
  BaserowLower,
  BaserowSplitPart,
  BaserowMinus,
  BaserowMultiply,
  BaserowNot,
  BaserowOr,
  BaserowReplace,
  BaserowRowId,
  BaserowT,
  BaserowNow,
  BaserowToday,
  BaserowToDateTz,
  BaserowToDate,
  BaserowToNumber,
  BaserowToText,
  BaserowUpper,
  BaserowReverse,
  BaserowLength,
  BaserowNotEqual,
  BaserowLookup,
  BaserowSum,
  BaserowAvg,
  BaserowVariancePop,
  BaserowVarianceSample,
  BaserowStddevSample,
  BaserowStddevPop,
  BaserowJoin,
  BaserowCount,
  BaserowMin,
  BaserowMax,
  BaserowEvery,
  BaserowAny,
  BaserowWhenEmpty,
  BaserowSecond,
  BaserowYear,
  BaserowMonth,
  BaserowLeast,
  BaserowGreatest,
  BaserowRegexReplace,
  BaserowLink,
  BaserowTrim,
  BaserowRight,
  BaserowLeft,
  BaserowContains,
  BaserowFilter,
  BaserowTrunc,
  BaserowIsNaN,
  BaserowWhenNaN,
  BaserowEven,
  BaserowOdd,
  BaserowCeil,
  BaserowFloor,
  BaserowAbs,
  BaserowExp,
  BaserowLn,
  BaserowSign,
  BaserowSqrt,
  BaserowRound,
  BaserowLog,
  BaserowPower,
  BaserowMod,
  BaserowButton,
  BaserowGetLinkUrl,
  BaserowGetLinkLabel,
  BaserowIsImage,
  BaserowGetImageHeight,
  BaserowGetImageWidth,
  BaserowGetFileSize,
  BaserowGetFileMimeType,
  BaserowGetFileVisibleName,
  BaserowIndex,
  BaserowGetFileCount,
  BaserowToUrl,
} from '@baserow/modules/database/formula/functions'
import {
  BaserowFormulaArrayType,
  BaserowFormulaBooleanType,
  BaserowFormulaButtonType,
  BaserowFormulaCharType,
  BaserowFormulaLinkType,
  BaserowFormulaDateIntervalType, // Deprecated
  BaserowFormulaDurationType,
  BaserowFormulaDateType,
  BaserowFormulaInvalidType,
  BaserowFormulaNumberType,
  BaserowFormulaSingleSelectType,
  BaserowFormulaMultipleSelectType,
  BaserowFormulaMultipleCollaboratorsType,
  BaserowFormulaSpecialType,
  BaserowFormulaTextType,
  BaserowFormulaFileType,
  BaserowFormulaURLType,
} from '@baserow/modules/database/formula/formulaTypes'
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
  EarliestDateViewAggregationType,
  LatestDateViewAggregationType,
  SumViewAggregationType,
  AverageViewAggregationType,
  StdDevViewAggregationType,
  VarianceViewAggregationType,
  MedianViewAggregationType,
  DistributionViewAggregationType,
} from '@baserow/modules/database/viewAggregationTypes'
import { FormViewFormModeType } from '@baserow/modules/database/formViewModeTypes'
import { CollaborativeViewOwnershipType } from '@baserow/modules/database/viewOwnershipTypes'
import { DatabasePlugin } from '@baserow/modules/database/plugins'
import {
  CollaboratorAddedToRowNotificationType,
  FormSubmittedNotificationType,
  UserMentionInRichTextFieldNotificationType,
  WebhookDeactivatedNotificationType,
  WebhookPayloadTooLargedNotificationType,
} from '@baserow/modules/database/notificationTypes'
import { HistoryRowModalSidebarType } from '@baserow/modules/database/rowModalSidebarTypes'
import { FieldsDataProviderType } from '@baserow/modules/database/dataProviderTypes'

import {
  DatabaseOnboardingType,
  DatabaseScratchTrackOnboardingType,
  DatabaseImportOnboardingType,
  DatabaseScratchTrackFieldsOnboardingType,
} from '@baserow/modules/database/onboardingTypes'

import {
  ScratchDatabaseOnboardingStepType,
  ImportDatabaseOnboardingStepType,
  AirtableDatabaseOnboardingStepType,
  TemplateDatabaseOnboardingStepType,
} from '@baserow/modules/database/databaseOnboardingStepTypes'

import {
  DatabaseScratchTrackCampaignFieldsOnboardingType,
  DatabaseScratchTrackCustomFieldsOnboardingType,
  DatabaseScratchTrackProjectFieldsOnboardingType,
  DatabaseScratchTrackTaskFieldsOnboardingType,
  DatabaseScratchTrackTeamFieldsOnboardingType,
} from '@baserow/modules/database/databaseScratchTrackFieldsStepType'
import {
  SyncedFieldsConfigureDataSyncType,
  SettingsConfigureDataSyncType,
} from '@baserow/modules/database/configureDataSyncTypes'
import { DatabaseGuidedTourType } from '@baserow/modules/database/guidedTourTypes'
import {
  DatabaseSearchType,
  DatabaseTableSearchType,
  DatabaseFieldSearchType,
  DatabaseRowSearchType,
} from '@baserow/modules/database/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

export default defineNuxtPlugin({
  name: 'database',
  dependsOn: ['core'],
  setup(nuxtApp) {
    const { $registry } = nuxtApp

    const context = { app: nuxtApp }

    $registry.registerNamespace('viewDecorator')
    $registry.registerNamespace('decoratorValueProvider')
    $registry.registerNamespace('twoWaySyncStrategy')
    $registry.registerNamespace('viewFilter')
    $registry.registerNamespace('viewOwnershipType')
    $registry.registerNamespace('fieldConstraint')
    $registry.registerNamespace('importer')
    $registry.registerNamespace('exporter')
    $registry.registerNamespace('dataSync')
    $registry.registerNamespace('webhookEvent')
    $registry.registerNamespace('formula_function')
    $registry.registerNamespace('formula_type')
    $registry.registerNamespace('preview')
    $registry.registerNamespace('viewAggregation')
    $registry.registerNamespace('formViewMode')
    $registry.registerNamespace('databaseDataProvider')
    $registry.registerNamespace('rowModalSidebar')
    $registry.registerNamespace('onboardingTrackFields')
    $registry.registerNamespace('configureDataSync')
    $registry.registerNamespace('databaseOnboardingStep')

    $registry.register('plugin', new DatabasePlugin(context))
    $registry.register('application', new DatabaseApplicationType(context))

    $registry.register('job', new DuplicateTableJobType(context))
    $registry.register('job', new SyncDataSyncTableJobType(context))
    $registry.register('job', new FileImportJobType(context))
    $registry.register('job', new DuplicateFieldJobType(context))
    $registry.register('job', new AirtableJobType(context))

    $registry.register('view', new GridViewType(context))
    $registry.register('view', new GalleryViewType(context))
    $registry.register('view', new FormViewType(context))
    $registry.register('viewFilter', new EqualViewFilterType(context))
    $registry.register('viewFilter', new NotEqualViewFilterType(context))
    $registry.register(
      'viewFilter',
      new DateIsEqualMultiStepViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateIsNotEqualMultiStepViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateIsBeforeMultiStepViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateIsOnOrBeforeMultiStepViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateIsAfterMultiStepViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateIsOnOrAfterMultiStepViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateIsWithinMultiStepViewFilterType(context)
    )
    // DEPRECATED
    $registry.register('viewFilter', new DateEqualViewFilterType(context))
    $registry.register('viewFilter', new DateNotEqualViewFilterType(context))
    $registry.register('viewFilter', new DateEqualsTodayViewFilterType(context))
    $registry.register('viewFilter', new DateBeforeTodayViewFilterType(context))
    $registry.register('viewFilter', new DateAfterTodayViewFilterType(context))
    $registry.register('viewFilter', new DateWithinDaysViewFilterType(context))
    $registry.register('viewFilter', new DateWithinWeeksViewFilterType(context))
    $registry.register(
      'viewFilter',
      new DateWithinMonthsViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateEqualsDaysAgoViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateEqualsMonthsAgoViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateEqualsYearsAgoViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateEqualsCurrentWeekViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateEqualsCurrentMonthViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateEqualsCurrentYearViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateEqualsDayOfMonthViewFilterType(context)
    )
    $registry.register('viewFilter', new DateBeforeViewFilterType(context))
    $registry.register(
      'viewFilter',
      new DateBeforeOrEqualViewFilterType(context)
    )
    $registry.register('viewFilter', new DateAfterViewFilterType(context))
    $registry.register(
      'viewFilter',
      new DateAfterOrEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new DateAfterDaysAgoViewFilterType(context)
    )
    // END
    $registry.register('viewFilter', new HasEmptyValueViewFilterType(context))
    $registry.register(
      'viewFilter',
      new HasNotEmptyValueViewFilterType(context)
    )
    $registry.register('viewFilter', new HasValueEqualViewFilterType(context))
    $registry.register(
      'viewFilter',
      new HasNotValueEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasValueContainsViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotValueContainsViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasValueContainsWordViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotValueContainsWordViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasValueLengthIsLowerThanViewFilterType(context)
    )
    $registry.register(
      'viewFilter',

      new HasAllValuesEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasAnySelectOptionEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNoneSelectOptionEqualViewFilterType(context)
    )
    $registry.register('viewFilter', new ContainsViewFilterType(context))
    $registry.register('viewFilter', new ContainsNotViewFilterType(context))
    $registry.register('viewFilter', new ContainsWordViewFilterType(context))
    $registry.register(
      'viewFilter',
      new DoesntContainWordViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new FilenameContainsViewFilterType(context)
    )
    $registry.register('viewFilter', new HasFileTypeViewFilterType(context))
    $registry.register('viewFilter', new FilesLowerThanViewFilterType(context))
    $registry.register(
      'viewFilter',
      new LengthIsLowerThanViewFilterType(context)
    )
    $registry.register('viewFilter', new HigherThanViewFilterType(context))
    $registry.register(
      'viewFilter',
      new HigherThanOrEqualViewFilterType(context)
    )
    $registry.register('viewFilter', new LowerThanViewFilterType(context))
    $registry.register(
      'viewFilter',
      new LowerThanOrEqualViewFilterType(context)
    )
    $registry.register('viewFilter', new IsEvenAndWholeViewFilterType(context))
    $registry.register(
      'viewFilter',
      new SingleSelectEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new SingleSelectNotEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new SingleSelectIsAnyOfViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new SingleSelectIsNoneOfViewFilterType(context)
    )

    $registry.register('viewFilter', new BooleanViewFilterType(context))
    $registry.register('viewFilter', new LinkRowHasFilterType(context))
    $registry.register('viewFilter', new LinkRowHasNotFilterType(context))
    $registry.register('viewFilter', new LinkRowContainsFilterType(context))
    $registry.register('viewFilter', new LinkRowNotContainsFilterType(context))
    $registry.register('viewFilter', new MultipleSelectHasFilterType(context))
    $registry.register(
      'viewFilter',
      new MultipleSelectHasNotFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new MultipleCollaboratorsHasFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new MultipleCollaboratorsHasNotFilterType(context)
    )
    $registry.register('viewFilter', new EmptyViewFilterType(context))
    $registry.register('viewFilter', new NotEmptyViewFilterType(context))
    $registry.register('viewFilter', new UserIsFilterType(context))
    $registry.register('viewFilter', new UserIsNotFilterType(context))
    $registry.register(
      'viewFilter',
      new HasValueHigherThanViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotValueHigherThanViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasValueHigherThanOrEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotValueHigherThanOrEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasValueLowerThanViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotValueLowerThanViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasValueLowerThanOrEqualViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotValueLowerThanOrEqualViewFilterType(context)
    )
    $registry.register('viewFilter', new HasDateEqualViewFilterType(context))
    $registry.register('viewFilter', new HasNotDateEqualViewFilterType(context))
    $registry.register('viewFilter', new HasDateBeforeViewFilterType(context))
    $registry.register(
      'viewFilter',
      new HasNotDateBeforeViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasDateOnOrBeforeViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotDateOnOrBeforeViewFilterType(context)
    )
    $registry.register('viewFilter', new HasDateAfterViewFilterType(context))
    $registry.register('viewFilter', new HasNotDateAfterViewFilterType(context))
    $registry.register(
      'viewFilter',
      new HasDateOnOrAfterViewFilterType(context)
    )
    $registry.register(
      'viewFilter',
      new HasNotDateOnOrAfterViewFilterType(context)
    )
    $registry.register('viewFilter', new HasDateWithinViewFilterType(context))
    $registry.register(
      'viewFilter',
      new HasNotDateWithinViewFilterType(context)
    )

    $registry.register(
      'viewOwnershipType',
      new CollaborativeViewOwnershipType(context)
    )

    $registry.register('field', new TextFieldType(context))
    $registry.register('field', new LongTextFieldType(context))
    $registry.register('field', new LinkRowFieldType(context))
    $registry.register('field', new NumberFieldType(context))
    $registry.register('field', new RatingFieldType(context))
    $registry.register('field', new BooleanFieldType(context))
    $registry.register('field', new DateFieldType(context))
    $registry.register('field', new LastModifiedFieldType(context))
    $registry.register('field', new LastModifiedByFieldType(context))
    $registry.register('field', new CreatedOnFieldType(context))
    $registry.register('field', new CreatedByFieldType(context))
    $registry.register('field', new DurationFieldType(context))
    $registry.register('field', new URLFieldType(context))
    $registry.register('field', new EmailFieldType(context))
    $registry.register('field', new FileFieldType(context))
    $registry.register('field', new SingleSelectFieldType(context))
    $registry.register('field', new MultipleSelectFieldType(context))
    $registry.register('field', new PhoneNumberFieldType(context))
    $registry.register('field', new FormulaFieldType(context))
    $registry.register('field', new CountFieldType(context))
    $registry.register('field', new RollupFieldType(context))
    $registry.register('field', new LookupFieldType(context))
    $registry.register('field', new MultipleCollaboratorsFieldType(context))
    $registry.register('field', new UUIDFieldType(context))
    $registry.register('field', new AutonumberFieldType(context))
    $registry.register('field', new PasswordFieldType(context))

    $registry.register(
      'fieldConstraint',
      new TextTypeUniqueWithEmptyConstraintType(context)
    )
    $registry.register(
      'fieldConstraint',
      new RatingTypeUniqueWithEmptyConstraintType(context)
    )
    $registry.register(
      'fieldConstraint',
      new GenericUniqueWithEmptyConstraintType(context)
    )

    $registry.register('importer', new CSVImporterType(context))
    $registry.register('importer', new PasteImporterType(context))
    $registry.register('importer', new XMLImporterType(context))
    $registry.register('importer', new JSONImporterType(context))
    $registry.register('dataSync', new ICalCalendarDataSyncType(context))
    $registry.register('dataSync', new PostgreSQLDataSyncType(context))
    $registry.register('settings', new APITokenSettingsType(context))
    $registry.register('exporter', new CSVTableExporterType(context))
    $registry.register('webhookEvent', new RowsCreatedWebhookEventType(context))
    $registry.register('webhookEvent', new RowsUpdatedWebhookEventType(context))
    $registry.register('webhookEvent', new RowsDeletedWebhookEventType(context))
    $registry.register(
      'webhookEvent',
      new FieldCreatedWebhookEventType(context)
    )
    $registry.register(
      'webhookEvent',
      new FieldUpdatedWebhookEventType(context)
    )
    $registry.register(
      'webhookEvent',
      new FieldDeletedWebhookEventType(context)
    )
    $registry.register('webhookEvent', new ViewCreatedWebhookEventType(context))
    $registry.register('webhookEvent', new ViewUpdatedWebhookEventType(context))
    $registry.register('webhookEvent', new ViewDeletedWebhookEventType(context))

    // Text functions
    $registry.register('formula_function', new BaserowUpper(context))
    $registry.register('formula_function', new BaserowLower(context))
    $registry.register('formula_function', new BaserowConcat(context))
    $registry.register('formula_function', new BaserowToText(context))
    $registry.register('formula_function', new BaserowT(context))
    $registry.register('formula_function', new BaserowReplace(context))
    $registry.register('formula_function', new BaserowSearch(context))
    $registry.register('formula_function', new BaserowLength(context))
    $registry.register('formula_function', new BaserowReverse(context))
    $registry.register('formula_function', new BaserowEncodeUri(context))
    $registry.register(
      'formula_function',
      new BaserowEncodeUriComponent(context)
    )
    $registry.register('formula_function', new BaserowSplitPart(context))
    // Number functions
    $registry.register('formula_function', new BaserowMultiply(context))
    $registry.register('formula_function', new BaserowDivide(context))
    $registry.register('formula_function', new BaserowToNumber(context))
    // Boolean functions
    $registry.register('formula_function', new BaserowIf(context))
    $registry.register('formula_function', new BaserowEqual(context))
    $registry.register('formula_function', new BaserowHasOption(context))
    $registry.register('formula_function', new BaserowIsBlank(context))
    $registry.register('formula_function', new BaserowIsNull(context))
    $registry.register('formula_function', new BaserowNot(context))
    $registry.register('formula_function', new BaserowNotEqual(context))
    $registry.register('formula_function', new BaserowGreaterThan(context))
    $registry.register(
      'formula_function',
      new BaserowGreaterThanOrEqual(context)
    )
    $registry.register('formula_function', new BaserowLessThan(context))
    $registry.register('formula_function', new BaserowLessThanOrEqual(context))
    $registry.register('formula_function', new BaserowAnd(context))
    $registry.register('formula_function', new BaserowOr(context))
    // Date functions
    $registry.register('formula_function', new BaserowDatetimeFormat(context))
    $registry.register('formula_function', new BaserowDatetimeFormatTz(context))
    $registry.register('formula_function', new BaserowDay(context))
    $registry.register('formula_function', new BaserowNow(context))
    $registry.register('formula_function', new BaserowToday(context))
    $registry.register('formula_function', new BaserowToDateTz(context))
    $registry.register('formula_function', new BaserowToDate(context))
    $registry.register('formula_function', new BaserowDateDiff(context))
    // Date interval functions
    $registry.register('formula_function', new BaserowDateInterval(context))
    $registry.register(
      'formula_function',
      new BaserowDurationToSeconds(context)
    )
    $registry.register(
      'formula_function',
      new BaserowSecondsToDuration(context)
    )
    // Special functions. NOTE: rollup compatible functions are shown field sub-form in
    // the same order as they are listed here.
    $registry.register('formula_function', new BaserowAdd(context))
    $registry.register('formula_function', new BaserowMinus(context))
    $registry.register('formula_function', new BaserowField(context))
    $registry.register('formula_function', new BaserowLookup(context))
    $registry.register('formula_function', new BaserowRowId(context))
    $registry.register('formula_function', new BaserowContains(context))
    $registry.register('formula_function', new BaserowLeft(context))
    $registry.register('formula_function', new BaserowRight(context))
    $registry.register('formula_function', new BaserowTrim(context))
    $registry.register('formula_function', new BaserowRegexReplace(context))
    $registry.register('formula_function', new BaserowGreatest(context))
    $registry.register('formula_function', new BaserowLeast(context))
    $registry.register('formula_function', new BaserowMonth(context))
    $registry.register('formula_function', new BaserowYear(context))
    $registry.register('formula_function', new BaserowSecond(context))
    $registry.register('formula_function', new BaserowWhenEmpty(context))
    $registry.register('formula_function', new BaserowAny(context))
    $registry.register('formula_function', new BaserowEvery(context))
    $registry.register('formula_function', new BaserowMin(context))
    $registry.register('formula_function', new BaserowMax(context))
    $registry.register('formula_function', new BaserowCount(context))
    $registry.register('formula_function', new BaserowSum(context))
    $registry.register('formula_function', new BaserowAvg(context))
    $registry.register('formula_function', new BaserowJoin(context))
    $registry.register('formula_function', new BaserowStddevPop(context))
    $registry.register('formula_function', new BaserowStddevSample(context))
    $registry.register('formula_function', new BaserowVarianceSample(context))
    $registry.register('formula_function', new BaserowVariancePop(context))
    $registry.register('formula_function', new BaserowFilter(context))
    $registry.register('formula_function', new BaserowTrunc(context))
    $registry.register('formula_function', new BaserowIsNaN(context))
    $registry.register('formula_function', new BaserowWhenNaN(context))
    $registry.register('formula_function', new BaserowEven(context))
    $registry.register('formula_function', new BaserowOdd(context))
    $registry.register('formula_function', new BaserowAbs(context))
    $registry.register('formula_function', new BaserowCeil(context))
    $registry.register('formula_function', new BaserowFloor(context))
    $registry.register('formula_function', new BaserowSign(context))
    $registry.register('formula_function', new BaserowLog(context))
    $registry.register('formula_function', new BaserowExp(context))
    $registry.register('formula_function', new BaserowLn(context))
    $registry.register('formula_function', new BaserowPower(context))
    $registry.register('formula_function', new BaserowSqrt(context))
    $registry.register('formula_function', new BaserowRound(context))
    $registry.register('formula_function', new BaserowMod(context))
    // Link functions
    $registry.register('formula_function', new BaserowLink(context))
    $registry.register('formula_function', new BaserowButton(context))
    $registry.register('formula_function', new BaserowGetLinkUrl(context))
    $registry.register('formula_function', new BaserowGetLinkLabel(context))
    // File functions
    $registry.register(
      'formula_function',
      new BaserowGetFileVisibleName(context)
    )
    $registry.register('formula_function', new BaserowGetFileMimeType(context))
    $registry.register('formula_function', new BaserowGetFileSize(context))
    $registry.register('formula_function', new BaserowGetImageWidth(context))
    $registry.register('formula_function', new BaserowGetImageHeight(context))
    $registry.register('formula_function', new BaserowIsImage(context))

    $registry.register('formula_function', new BaserowGetFileCount(context))
    $registry.register('formula_function', new BaserowIndex(context))
    $registry.register('formula_function', new BaserowToUrl(context))

    // Formula Types
    $registry.register('formula_type', new BaserowFormulaTextType(context))
    $registry.register('formula_type', new BaserowFormulaCharType(context))
    $registry.register('formula_type', new BaserowFormulaBooleanType(context))
    $registry.register('formula_type', new BaserowFormulaDateType(context))
    $registry.register(
      'formula_type',
      new BaserowFormulaDateIntervalType(context)
    )
    $registry.register('formula_type', new BaserowFormulaDurationType(context))
    $registry.register('formula_type', new BaserowFormulaNumberType(context))
    $registry.register('formula_type', new BaserowFormulaArrayType(context))
    $registry.register('formula_type', new BaserowFormulaSpecialType(context))
    $registry.register('formula_type', new BaserowFormulaInvalidType(context))
    $registry.register(
      'formula_type',
      new BaserowFormulaSingleSelectType(context)
    )
    $registry.register('formula_type', new BaserowFormulaURLType(context))
    $registry.register(
      'formula_type',
      new BaserowFormulaMultipleSelectType(context)
    )
    $registry.register('formula_type', new BaserowFormulaButtonType(context))
    $registry.register('formula_type', new BaserowFormulaLinkType(context))
    $registry.register('formula_type', new BaserowFormulaFileType(context))
    $registry.register(
      'formula_type',
      new BaserowFormulaMultipleCollaboratorsType(context)
    )

    // File preview types
    $registry.register('preview', new ImageFilePreview(context))
    $registry.register('preview', new AudioFilePreview(context))
    $registry.register('preview', new VideoFilePreview(context))
    $registry.register('preview', new PDFBrowserFilePreview(context))
    $registry.register('preview', new GoogleDocFilePreview(context))

    $registry.register('viewAggregation', new MinViewAggregationType(context))
    $registry.register('viewAggregation', new MaxViewAggregationType(context))
    $registry.register('viewAggregation', new SumViewAggregationType(context))
    $registry.register(
      'viewAggregation',
      new AverageViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new MedianViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new StdDevViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new VarianceViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new EarliestDateViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new LatestDateViewAggregationType(context)
    )
    $registry.register('viewAggregation', new CountViewAggregationType(context))
    $registry.register(
      'viewAggregation',
      new EmptyCountViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new NotEmptyCountViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new CheckedCountViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new NotCheckedCountViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new EmptyPercentageViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new NotEmptyPercentageViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new CheckedPercentageViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new NotCheckedPercentageViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new UniqueCountViewAggregationType(context)
    )
    $registry.register(
      'viewAggregation',
      new DistributionViewAggregationType(context)
    )

    $registry.register('formViewMode', new FormViewFormModeType(context))

    $registry.register(
      'databaseDataProvider',
      new FieldsDataProviderType(context)
    )

    // notifications
    $registry.register(
      'notification',
      new CollaboratorAddedToRowNotificationType(context)
    )
    $registry.register(
      'notification',
      new FormSubmittedNotificationType(context)
    )
    $registry.register(
      'notification',
      new UserMentionInRichTextFieldNotificationType(context)
    )
    $registry.register(
      'notification',
      new WebhookDeactivatedNotificationType(context)
    )
    $registry.register(
      'notification',
      new WebhookPayloadTooLargedNotificationType(context)
    )

    $registry.register(
      'rowModalSidebar',
      new HistoryRowModalSidebarType(context)
    )

    $registry.register('onboarding', new DatabaseOnboardingType(context))
    $registry.register(
      'onboarding',
      new DatabaseScratchTrackOnboardingType(context)
    )
    $registry.register(
      'onboarding',
      new DatabaseScratchTrackFieldsOnboardingType(context)
    )
    $registry.register('onboarding', new DatabaseImportOnboardingType(context))

    $registry.register(
      'databaseOnboardingStep',
      new ScratchDatabaseOnboardingStepType(context)
    )
    $registry.register(
      'databaseOnboardingStep',
      new ImportDatabaseOnboardingStepType(context)
    )
    $registry.register(
      'databaseOnboardingStep',
      new AirtableDatabaseOnboardingStepType(context)
    )
    $registry.register(
      'databaseOnboardingStep',
      new TemplateDatabaseOnboardingStepType(context)
    )

    $registry.register(
      'onboardingTrackFields',
      new DatabaseScratchTrackProjectFieldsOnboardingType(context)
    )
    $registry.register(
      'onboardingTrackFields',
      new DatabaseScratchTrackTeamFieldsOnboardingType(context)
    )
    $registry.register(
      'onboardingTrackFields',
      new DatabaseScratchTrackTaskFieldsOnboardingType(context)
    )
    $registry.register(
      'onboardingTrackFields',
      new DatabaseScratchTrackCampaignFieldsOnboardingType(context)
    )
    $registry.register(
      'onboardingTrackFields',
      new DatabaseScratchTrackCustomFieldsOnboardingType(context)
    )

    $registry.register(
      'configureDataSync',
      new SyncedFieldsConfigureDataSyncType(context)
    )
    $registry.register(
      'configureDataSync',
      new SettingsConfigureDataSyncType(context)
    )

    $registry.register('guidedTour', new DatabaseGuidedTourType(context))

    $registry.registerNamespace('fieldContextItem')

    searchTypeRegistry.register(new DatabaseSearchType(context))
    searchTypeRegistry.register(new DatabaseTableSearchType(context))
    searchTypeRegistry.register(new DatabaseFieldSearchType(context))
    searchTypeRegistry.register(new DatabaseRowSearchType(context))
  },
})
