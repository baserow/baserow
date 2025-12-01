import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import {
  DuplicateTableJobType,
  SyncDataSyncTableJobType,
  FileImportJobType,
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

import tableStore from '@baserow/modules/database/store/table'
import viewStore from '@baserow/modules/database/store/view'
import fieldStore from '@baserow/modules/database/store/field'
import gridStore from '@baserow/modules/database/store/view/grid'
import galleryStore from '@baserow/modules/database/store/view/gallery'
import formStore from '@baserow/modules/database/store/view/form'
import rowModal from '@baserow/modules/database/store/rowModal'
import publicStore from '@baserow/modules/database/store/view/public'
import rowModalNavigationStore from '@baserow/modules/database/store/rowModalNavigation'
import rowHistoryStore from '@baserow/modules/database/store/rowHistory'
import fieldRulesStore from '@baserow/modules/database/store/fieldRules'

import { registerRealtimeEvents } from '@baserow/modules/database/realtime'
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

import en from '@baserow/modules/database/locales/en.json'
import fr from '@baserow/modules/database/locales/fr.json'
import nl from '@baserow/modules/database/locales/nl.json'
import de from '@baserow/modules/database/locales/de.json'
import es from '@baserow/modules/database/locales/es.json'
import it from '@baserow/modules/database/locales/it.json'
import pl from '@baserow/modules/database/locales/pl.json'
import ko from '@baserow/modules/database/locales/ko.json'
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

export default (context) => {
  const { store, app, isDev } = context

  // Allow locale file hot reloading in dev
  if (isDev && app.i18n) {
    const { i18n } = app
    i18n.mergeLocaleMessage('en', en)
    i18n.mergeLocaleMessage('fr', fr)
    i18n.mergeLocaleMessage('nl', nl)
    i18n.mergeLocaleMessage('de', de)
    i18n.mergeLocaleMessage('es', es)
    i18n.mergeLocaleMessage('it', it)
    i18n.mergeLocaleMessage('pl', pl)
    i18n.mergeLocaleMessage('ko', ko)
  }

  store.registerModule('table', tableStore)
  store.registerModule('view', viewStore)
  store.registerModule('field', fieldStore)
  store.registerModule('rowModal', rowModal)
  store.registerModule('rowModalNavigation', rowModalNavigationStore)
  store.registerModule('rowHistory', rowHistoryStore)
  store.registerModule('fieldRules', fieldRulesStore)
  store.registerModule('page/view/grid', gridStore)
  store.registerModule('page/view/gallery', galleryStore)
  store.registerModule('page/view/form', formStore)
  store.registerModule('page/view/public', publicStore)
  store.registerModule('template/view/grid', gridStore)
  store.registerModule('template/view/gallery', galleryStore)
  store.registerModule('template/view/form', formStore)

  app.$registry.registerNamespace('viewDecorator')
  app.$registry.registerNamespace('decoratorValueProvider')
  app.$registry.registerNamespace('twoWaySyncStrategy')

  app.$registry.register('plugin', new DatabasePlugin(context))
  app.$registry.register('application', new DatabaseApplicationType(context))

  app.$registry.register('job', new DuplicateTableJobType(context))
  app.$registry.register('job', new SyncDataSyncTableJobType(context))
  app.$registry.register('job', new FileImportJobType(context))

  app.$registry.register('view', new GridViewType(context))
  app.$registry.register('view', new GalleryViewType(context))
  app.$registry.register('view', new FormViewType(context))
  app.$registry.register('viewFilter', new EqualViewFilterType(context))
  app.$registry.register('viewFilter', new NotEqualViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new DateIsEqualMultiStepViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateIsNotEqualMultiStepViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateIsBeforeMultiStepViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateIsOnOrBeforeMultiStepViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateIsAfterMultiStepViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateIsOnOrAfterMultiStepViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateIsWithinMultiStepViewFilterType(context)
  )
  // DEPRECATED
  app.$registry.register('viewFilter', new DateEqualViewFilterType(context))
  app.$registry.register('viewFilter', new DateNotEqualViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new DateEqualsTodayViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateBeforeTodayViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateAfterTodayViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateWithinDaysViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateWithinWeeksViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateWithinMonthsViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateEqualsDaysAgoViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateEqualsMonthsAgoViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateEqualsYearsAgoViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateEqualsCurrentWeekViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateEqualsCurrentMonthViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateEqualsCurrentYearViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateEqualsDayOfMonthViewFilterType(context)
  )
  app.$registry.register('viewFilter', new DateBeforeViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new DateBeforeOrEqualViewFilterType(context)
  )
  app.$registry.register('viewFilter', new DateAfterViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new DateAfterOrEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new DateAfterDaysAgoViewFilterType(context)
  )
  // END
  app.$registry.register('viewFilter', new HasEmptyValueViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HasNotEmptyValueViewFilterType(context)
  )
  app.$registry.register('viewFilter', new HasValueEqualViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HasNotValueEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasValueContainsViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotValueContainsViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasValueContainsWordViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotValueContainsWordViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasValueLengthIsLowerThanViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',

    new HasAllValuesEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasAnySelectOptionEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNoneSelectOptionEqualViewFilterType(context)
  )
  app.$registry.register('viewFilter', new ContainsViewFilterType(context))
  app.$registry.register('viewFilter', new ContainsNotViewFilterType(context))
  app.$registry.register('viewFilter', new ContainsWordViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new DoesntContainWordViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new FilenameContainsViewFilterType(context)
  )
  app.$registry.register('viewFilter', new HasFileTypeViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new FilesLowerThanViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new LengthIsLowerThanViewFilterType(context)
  )
  app.$registry.register('viewFilter', new HigherThanViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HigherThanOrEqualViewFilterType(context)
  )
  app.$registry.register('viewFilter', new LowerThanViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new LowerThanOrEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new IsEvenAndWholeViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new SingleSelectEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new SingleSelectNotEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new SingleSelectIsAnyOfViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new SingleSelectIsNoneOfViewFilterType(context)
  )

  app.$registry.register('viewFilter', new BooleanViewFilterType(context))
  app.$registry.register('viewFilter', new LinkRowHasFilterType(context))
  app.$registry.register('viewFilter', new LinkRowHasNotFilterType(context))
  app.$registry.register('viewFilter', new LinkRowContainsFilterType(context))
  app.$registry.register(
    'viewFilter',
    new LinkRowNotContainsFilterType(context)
  )
  app.$registry.register('viewFilter', new MultipleSelectHasFilterType(context))
  app.$registry.register(
    'viewFilter',
    new MultipleSelectHasNotFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new MultipleCollaboratorsHasFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new MultipleCollaboratorsHasNotFilterType(context)
  )
  app.$registry.register('viewFilter', new EmptyViewFilterType(context))
  app.$registry.register('viewFilter', new NotEmptyViewFilterType(context))
  app.$registry.register('viewFilter', new UserIsFilterType(context))
  app.$registry.register('viewFilter', new UserIsNotFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HasValueHigherThanViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotValueHigherThanViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasValueHigherThanOrEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotValueHigherThanOrEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasValueLowerThanViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotValueLowerThanViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasValueLowerThanOrEqualViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotValueLowerThanOrEqualViewFilterType(context)
  )
  app.$registry.register('viewFilter', new HasDateEqualViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HasNotDateEqualViewFilterType(context)
  )
  app.$registry.register('viewFilter', new HasDateBeforeViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HasNotDateBeforeViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasDateOnOrBeforeViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotDateOnOrBeforeViewFilterType(context)
  )
  app.$registry.register('viewFilter', new HasDateAfterViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HasNotDateAfterViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasDateOnOrAfterViewFilterType(context)
  )
  app.$registry.register(
    'viewFilter',
    new HasNotDateOnOrAfterViewFilterType(context)
  )
  app.$registry.register('viewFilter', new HasDateWithinViewFilterType(context))
  app.$registry.register(
    'viewFilter',
    new HasNotDateWithinViewFilterType(context)
  )

  app.$registry.register(
    'viewOwnershipType',
    new CollaborativeViewOwnershipType(context)
  )

  app.$registry.register('field', new TextFieldType(context))
  app.$registry.register('field', new LongTextFieldType(context))
  app.$registry.register('field', new LinkRowFieldType(context))
  app.$registry.register('field', new NumberFieldType(context))
  app.$registry.register('field', new RatingFieldType(context))
  app.$registry.register('field', new BooleanFieldType(context))
  app.$registry.register('field', new DateFieldType(context))
  app.$registry.register('field', new LastModifiedFieldType(context))
  app.$registry.register('field', new LastModifiedByFieldType(context))
  app.$registry.register('field', new CreatedOnFieldType(context))
  app.$registry.register('field', new CreatedByFieldType(context))
  app.$registry.register('field', new DurationFieldType(context))
  app.$registry.register('field', new URLFieldType(context))
  app.$registry.register('field', new EmailFieldType(context))
  app.$registry.register('field', new FileFieldType(context))
  app.$registry.register('field', new SingleSelectFieldType(context))
  app.$registry.register('field', new MultipleSelectFieldType(context))
  app.$registry.register('field', new PhoneNumberFieldType(context))
  app.$registry.register('field', new FormulaFieldType(context))
  app.$registry.register('field', new CountFieldType(context))
  app.$registry.register('field', new RollupFieldType(context))
  app.$registry.register('field', new LookupFieldType(context))
  app.$registry.register('field', new MultipleCollaboratorsFieldType(context))
  app.$registry.register('field', new UUIDFieldType(context))
  app.$registry.register('field', new AutonumberFieldType(context))
  app.$registry.register('field', new PasswordFieldType(context))

  app.$registry.register(
    'fieldConstraint',
    new TextTypeUniqueWithEmptyConstraintType(context)
  )
  app.$registry.register(
    'fieldConstraint',
    new RatingTypeUniqueWithEmptyConstraintType(context)
  )
  app.$registry.register(
    'fieldConstraint',
    new GenericUniqueWithEmptyConstraintType(context)
  )

  app.$registry.register('importer', new CSVImporterType(context))
  app.$registry.register('importer', new PasteImporterType(context))
  app.$registry.register('importer', new XMLImporterType(context))
  app.$registry.register('importer', new JSONImporterType(context))
  app.$registry.register('dataSync', new ICalCalendarDataSyncType(context))
  app.$registry.register('dataSync', new PostgreSQLDataSyncType(context))
  app.$registry.register('settings', new APITokenSettingsType(context))
  app.$registry.register('exporter', new CSVTableExporterType(context))
  app.$registry.register(
    'webhookEvent',
    new RowsCreatedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new RowsUpdatedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new RowsDeletedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new FieldCreatedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new FieldUpdatedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new FieldDeletedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new ViewCreatedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new ViewUpdatedWebhookEventType(context)
  )
  app.$registry.register(
    'webhookEvent',
    new ViewDeletedWebhookEventType(context)
  )

  // Text functions
  app.$registry.register('formula_function', new BaserowUpper(context))
  app.$registry.register('formula_function', new BaserowLower(context))
  app.$registry.register('formula_function', new BaserowConcat(context))
  app.$registry.register('formula_function', new BaserowToText(context))
  app.$registry.register('formula_function', new BaserowT(context))
  app.$registry.register('formula_function', new BaserowReplace(context))
  app.$registry.register('formula_function', new BaserowSearch(context))
  app.$registry.register('formula_function', new BaserowLength(context))
  app.$registry.register('formula_function', new BaserowReverse(context))
  app.$registry.register('formula_function', new BaserowEncodeUri(context))
  app.$registry.register(
    'formula_function',
    new BaserowEncodeUriComponent(context)
  )
  app.$registry.register('formula_function', new BaserowSplitPart(context))
  // Number functions
  app.$registry.register('formula_function', new BaserowMultiply(context))
  app.$registry.register('formula_function', new BaserowDivide(context))
  app.$registry.register('formula_function', new BaserowToNumber(context))
  // Boolean functions
  app.$registry.register('formula_function', new BaserowIf(context))
  app.$registry.register('formula_function', new BaserowEqual(context))
  app.$registry.register('formula_function', new BaserowHasOption(context))
  app.$registry.register('formula_function', new BaserowIsBlank(context))
  app.$registry.register('formula_function', new BaserowIsNull(context))
  app.$registry.register('formula_function', new BaserowNot(context))
  app.$registry.register('formula_function', new BaserowNotEqual(context))
  app.$registry.register('formula_function', new BaserowGreaterThan(context))
  app.$registry.register(
    'formula_function',
    new BaserowGreaterThanOrEqual(context)
  )
  app.$registry.register('formula_function', new BaserowLessThan(context))
  app.$registry.register(
    'formula_function',
    new BaserowLessThanOrEqual(context)
  )
  app.$registry.register('formula_function', new BaserowAnd(context))
  app.$registry.register('formula_function', new BaserowOr(context))
  // Date functions
  app.$registry.register('formula_function', new BaserowDatetimeFormat(context))
  app.$registry.register(
    'formula_function',
    new BaserowDatetimeFormatTz(context)
  )
  app.$registry.register('formula_function', new BaserowDay(context))
  app.$registry.register('formula_function', new BaserowNow(context))
  app.$registry.register('formula_function', new BaserowToday(context))
  app.$registry.register('formula_function', new BaserowToDateTz(context))
  app.$registry.register('formula_function', new BaserowToDate(context))
  app.$registry.register('formula_function', new BaserowDateDiff(context))
  // Date interval functions
  app.$registry.register('formula_function', new BaserowDateInterval(context))
  app.$registry.register(
    'formula_function',
    new BaserowDurationToSeconds(context)
  )
  app.$registry.register(
    'formula_function',
    new BaserowSecondsToDuration(context)
  )
  // Special functions. NOTE: rollup compatible functions are shown field sub-form in
  // the same order as they are listed here.
  app.$registry.register('formula_function', new BaserowAdd(context))
  app.$registry.register('formula_function', new BaserowMinus(context))
  app.$registry.register('formula_function', new BaserowField(context))
  app.$registry.register('formula_function', new BaserowLookup(context))
  app.$registry.register('formula_function', new BaserowRowId(context))
  app.$registry.register('formula_function', new BaserowContains(context))
  app.$registry.register('formula_function', new BaserowLeft(context))
  app.$registry.register('formula_function', new BaserowRight(context))
  app.$registry.register('formula_function', new BaserowTrim(context))
  app.$registry.register('formula_function', new BaserowRegexReplace(context))
  app.$registry.register('formula_function', new BaserowGreatest(context))
  app.$registry.register('formula_function', new BaserowLeast(context))
  app.$registry.register('formula_function', new BaserowMonth(context))
  app.$registry.register('formula_function', new BaserowYear(context))
  app.$registry.register('formula_function', new BaserowSecond(context))
  app.$registry.register('formula_function', new BaserowWhenEmpty(context))
  app.$registry.register('formula_function', new BaserowAny(context))
  app.$registry.register('formula_function', new BaserowEvery(context))
  app.$registry.register('formula_function', new BaserowMin(context))
  app.$registry.register('formula_function', new BaserowMax(context))
  app.$registry.register('formula_function', new BaserowCount(context))
  app.$registry.register('formula_function', new BaserowSum(context))
  app.$registry.register('formula_function', new BaserowAvg(context))
  app.$registry.register('formula_function', new BaserowJoin(context))
  app.$registry.register('formula_function', new BaserowStddevPop(context))
  app.$registry.register('formula_function', new BaserowStddevSample(context))
  app.$registry.register('formula_function', new BaserowVarianceSample(context))
  app.$registry.register('formula_function', new BaserowVariancePop(context))
  app.$registry.register('formula_function', new BaserowFilter(context))
  app.$registry.register('formula_function', new BaserowTrunc(context))
  app.$registry.register('formula_function', new BaserowIsNaN(context))
  app.$registry.register('formula_function', new BaserowWhenNaN(context))
  app.$registry.register('formula_function', new BaserowEven(context))
  app.$registry.register('formula_function', new BaserowOdd(context))
  app.$registry.register('formula_function', new BaserowAbs(context))
  app.$registry.register('formula_function', new BaserowCeil(context))
  app.$registry.register('formula_function', new BaserowFloor(context))
  app.$registry.register('formula_function', new BaserowSign(context))
  app.$registry.register('formula_function', new BaserowLog(context))
  app.$registry.register('formula_function', new BaserowExp(context))
  app.$registry.register('formula_function', new BaserowLn(context))
  app.$registry.register('formula_function', new BaserowPower(context))
  app.$registry.register('formula_function', new BaserowSqrt(context))
  app.$registry.register('formula_function', new BaserowRound(context))
  app.$registry.register('formula_function', new BaserowMod(context))
  // Link functions
  app.$registry.register('formula_function', new BaserowLink(context))
  app.$registry.register('formula_function', new BaserowButton(context))
  app.$registry.register('formula_function', new BaserowGetLinkUrl(context))
  app.$registry.register('formula_function', new BaserowGetLinkLabel(context))
  // File functions
  app.$registry.register(
    'formula_function',
    new BaserowGetFileVisibleName(context)
  )
  app.$registry.register(
    'formula_function',
    new BaserowGetFileMimeType(context)
  )
  app.$registry.register('formula_function', new BaserowGetFileSize(context))
  app.$registry.register('formula_function', new BaserowGetImageWidth(context))
  app.$registry.register('formula_function', new BaserowGetImageHeight(context))
  app.$registry.register('formula_function', new BaserowIsImage(context))

  app.$registry.register('formula_function', new BaserowGetFileCount(context))
  app.$registry.register('formula_function', new BaserowIndex(context))
  app.$registry.register('formula_function', new BaserowToUrl(context))

  // Formula Types
  app.$registry.register('formula_type', new BaserowFormulaTextType(context))
  app.$registry.register('formula_type', new BaserowFormulaCharType(context))
  app.$registry.register('formula_type', new BaserowFormulaBooleanType(context))
  app.$registry.register('formula_type', new BaserowFormulaDateType(context))
  app.$registry.register(
    'formula_type',
    new BaserowFormulaDateIntervalType(context)
  )
  app.$registry.register(
    'formula_type',
    new BaserowFormulaDurationType(context)
  )
  app.$registry.register('formula_type', new BaserowFormulaNumberType(context))
  app.$registry.register('formula_type', new BaserowFormulaArrayType(context))
  app.$registry.register('formula_type', new BaserowFormulaSpecialType(context))
  app.$registry.register('formula_type', new BaserowFormulaInvalidType(context))
  app.$registry.register(
    'formula_type',
    new BaserowFormulaSingleSelectType(context)
  )
  app.$registry.register('formula_type', new BaserowFormulaURLType(context))
  app.$registry.register(
    'formula_type',
    new BaserowFormulaMultipleSelectType(context)
  )
  app.$registry.register('formula_type', new BaserowFormulaButtonType(context))
  app.$registry.register('formula_type', new BaserowFormulaLinkType(context))
  app.$registry.register('formula_type', new BaserowFormulaFileType(context))
  app.$registry.register(
    'formula_type',
    new BaserowFormulaMultipleCollaboratorsType(context)
  )

  // File preview types
  app.$registry.register('preview', new ImageFilePreview(context))
  app.$registry.register('preview', new AudioFilePreview(context))
  app.$registry.register('preview', new VideoFilePreview(context))
  app.$registry.register('preview', new PDFBrowserFilePreview(context))
  app.$registry.register('preview', new GoogleDocFilePreview(context))

  app.$registry.register('viewAggregation', new MinViewAggregationType(context))
  app.$registry.register('viewAggregation', new MaxViewAggregationType(context))
  app.$registry.register('viewAggregation', new SumViewAggregationType(context))
  app.$registry.register(
    'viewAggregation',
    new AverageViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new MedianViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new StdDevViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new VarianceViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new EarliestDateViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new LatestDateViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new CountViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new EmptyCountViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new NotEmptyCountViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new CheckedCountViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new NotCheckedCountViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new EmptyPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new NotEmptyPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new CheckedPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new NotCheckedPercentageViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new UniqueCountViewAggregationType(context)
  )
  app.$registry.register(
    'viewAggregation',
    new DistributionViewAggregationType(context)
  )

  app.$registry.register('formViewMode', new FormViewFormModeType(context))

  app.$registry.register(
    'databaseDataProvider',
    new FieldsDataProviderType(context)
  )

  // notifications
  app.$registry.register(
    'notification',
    new CollaboratorAddedToRowNotificationType(context)
  )
  app.$registry.register(
    'notification',
    new FormSubmittedNotificationType(context)
  )
  app.$registry.register(
    'notification',
    new UserMentionInRichTextFieldNotificationType(context)
  )
  app.$registry.register(
    'notification',
    new WebhookDeactivatedNotificationType(context)
  )
  app.$registry.register(
    'notification',
    new WebhookPayloadTooLargedNotificationType(context)
  )

  app.$registry.register(
    'rowModalSidebar',
    new HistoryRowModalSidebarType(context)
  )

  app.$registry.register('onboarding', new DatabaseOnboardingType(context))
  app.$registry.register(
    'onboarding',
    new DatabaseScratchTrackOnboardingType(context)
  )
  app.$registry.register(
    'onboarding',
    new DatabaseScratchTrackFieldsOnboardingType(context)
  )
  app.$registry.register(
    'onboarding',
    new DatabaseImportOnboardingType(context)
  )

  app.$registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackProjectFieldsOnboardingType(context)
  )
  app.$registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackTeamFieldsOnboardingType(context)
  )
  app.$registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackTaskFieldsOnboardingType(context)
  )
  app.$registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackCampaignFieldsOnboardingType(context)
  )
  app.$registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackCustomFieldsOnboardingType(context)
  )

  app.$registry.register(
    'configureDataSync',
    new SyncedFieldsConfigureDataSyncType(context)
  )
  app.$registry.register(
    'configureDataSync',
    new SettingsConfigureDataSyncType(context)
  )

  app.$registry.register('guidedTour', new DatabaseGuidedTourType(context))

  registerRealtimeEvents(app.$realtime)

  app.$registry.registerNamespace('fieldContextItem')

  searchTypeRegistry.register(new DatabaseSearchType())
  searchTypeRegistry.register(new DatabaseTableSearchType())
  searchTypeRegistry.register(new DatabaseFieldSearchType())
  searchTypeRegistry.register(new DatabaseRowSearchType())
}
