from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import ProgrammingError
from django.db.models.signals import post_migrate, pre_migrate

from baserow.contrib.database.fields.utils.pg_datetime import pg_init
from baserow.contrib.database.table.cache import clear_generated_model_cache
from baserow.contrib.database.table.operations import RestoreDatabaseTableOperationType
from baserow.core.registries import (
    application_type_registry,
    object_scope_type_registry,
    operation_type_registry,
    plugin_registry,
)
from baserow.core.trash.registries import trash_item_type_registry
from baserow.core.usage.registries import workspace_storage_usage_item_registry
from baserow.ws.registries import page_registry


class DatabaseConfig(AppConfig):
    name = "baserow.contrib.database"

    def ready(self):
        from baserow.core.action.registries import (
            action_scope_registry,
            action_type_registry,
        )

        from .action.scopes import TableActionScopeType, ViewActionScopeType

        action_scope_registry.register(TableActionScopeType())
        action_scope_registry.register(ViewActionScopeType())

        from baserow.contrib.database.tokens.actions import (
            CreateDbTokenActionType,
            DeleteDbTokenActionType,
            RotateDbTokenKeyActionType,
            UpdateDbTokenNameActionType,
            UpdateDbTokenPermissionsActionType,
        )

        action_type_registry.register(CreateDbTokenActionType())
        action_type_registry.register(UpdateDbTokenNameActionType())
        action_type_registry.register(UpdateDbTokenPermissionsActionType())
        action_type_registry.register(RotateDbTokenKeyActionType())
        action_type_registry.register(DeleteDbTokenActionType())

        from baserow.contrib.database.webhooks.actions import (
            CreateWebhookActionType,
            DeleteWebhookActionType,
            UpdateWebhookActionType,
        )

        action_type_registry.register(CreateWebhookActionType())
        action_type_registry.register(DeleteWebhookActionType())
        action_type_registry.register(UpdateWebhookActionType())

        from .export.actions import ExportTableActionType

        action_type_registry.register(ExportTableActionType())

        from .airtable.actions import ImportDatabaseFromAirtableActionType

        action_type_registry.register(ImportDatabaseFromAirtableActionType())

        from .table.actions import (
            CreateTableActionType,
            DeleteTableActionType,
            DuplicateTableActionType,
            OrderTableActionType,
            UpdateTableActionType,
        )

        action_type_registry.register(CreateTableActionType())
        action_type_registry.register(DeleteTableActionType())
        action_type_registry.register(OrderTableActionType())
        action_type_registry.register(UpdateTableActionType())
        action_type_registry.register(DuplicateTableActionType())

        from .rows.actions import (
            CreateRowActionType,
            CreateRowsActionType,
            DeleteRowActionType,
            DeleteRowsActionType,
            ImportRowsActionType,
            MoveRowActionType,
            UpdateRowActionType,
            UpdateRowsActionType,
        )

        action_type_registry.register(CreateRowActionType())
        action_type_registry.register(CreateRowsActionType())
        action_type_registry.register(ImportRowsActionType())
        action_type_registry.register(DeleteRowActionType())
        action_type_registry.register(DeleteRowsActionType())
        action_type_registry.register(MoveRowActionType())
        action_type_registry.register(UpdateRowActionType())
        action_type_registry.register(UpdateRowsActionType())

        from baserow.contrib.database.views.actions import (
            CreateDecorationActionType,
            CreateViewActionType,
            CreateViewFilterActionType,
            CreateViewFilterGroupActionType,
            CreateViewGroupByActionType,
            CreateViewSortActionType,
            DeleteDecorationActionType,
            DeleteViewActionType,
            DeleteViewFilterActionType,
            DeleteViewFilterGroupActionType,
            DeleteViewGroupByActionType,
            DeleteViewSortActionType,
            DuplicateViewActionType,
            OrderViewsActionType,
            RotateViewSlugActionType,
            SubmitFormActionType,
            UpdateDecorationActionType,
            UpdateViewActionType,
            UpdateViewFieldOptionsActionType,
            UpdateViewFilterActionType,
            UpdateViewFilterGroupActionType,
            UpdateViewGroupByActionType,
            UpdateViewSortActionType,
        )

        action_type_registry.register(CreateViewActionType())
        action_type_registry.register(DuplicateViewActionType())
        action_type_registry.register(DeleteViewActionType())
        action_type_registry.register(OrderViewsActionType())
        action_type_registry.register(UpdateViewActionType())
        action_type_registry.register(CreateViewFilterActionType())
        action_type_registry.register(UpdateViewFilterActionType())
        action_type_registry.register(DeleteViewFilterActionType())
        action_type_registry.register(CreateViewSortActionType())
        action_type_registry.register(UpdateViewSortActionType())
        action_type_registry.register(DeleteViewSortActionType())
        action_type_registry.register(CreateViewGroupByActionType())
        action_type_registry.register(UpdateViewGroupByActionType())
        action_type_registry.register(DeleteViewGroupByActionType())
        action_type_registry.register(SubmitFormActionType())
        action_type_registry.register(RotateViewSlugActionType())
        action_type_registry.register(UpdateViewFieldOptionsActionType())
        action_type_registry.register(CreateDecorationActionType())
        action_type_registry.register(UpdateDecorationActionType())
        action_type_registry.register(DeleteDecorationActionType())
        action_type_registry.register(CreateViewFilterGroupActionType())
        action_type_registry.register(UpdateViewFilterGroupActionType())
        action_type_registry.register(DeleteViewFilterGroupActionType())

        from baserow.contrib.database.data_sync.actions import (
            CreateDataSyncTableActionType,
            SyncDataSyncTableActionType,
            UpdateDataSyncTableActionType,
        )

        action_type_registry.register(CreateDataSyncTableActionType())
        action_type_registry.register(UpdateDataSyncTableActionType())
        action_type_registry.register(SyncDataSyncTableActionType())

        from .airtable.registry import (
            airtable_column_type_registry,
            airtable_filter_operator_registry,
            airtable_view_type_registry,
        )
        from .data_sync.registries import data_sync_type_registry
        from .export.registries import table_exporter_registry
        from .fields.registries import (
            field_aggregation_registry,
            field_constraint_registry,
            field_converter_registry,
            field_type_registry,
        )
        from .formula.registries import formula_function_registry
        from .plugins import DatabasePlugin
        from .views.registries import (
            form_view_mode_registry,
            view_aggregation_type_registry,
            view_filter_type_registry,
            view_ownership_type_registry,
            view_type_registry,
        )
        from .webhooks.registries import webhook_event_type_registry

        plugin_registry.register(DatabasePlugin())

        from .fields.field_types import (
            AutonumberFieldType,
            BooleanFieldType,
            CountFieldType,
            CreatedByFieldType,
            CreatedOnFieldType,
            DateFieldType,
            DurationFieldType,
            EmailFieldType,
            FileFieldType,
            FormulaFieldType,
            LastModifiedByFieldType,
            LastModifiedFieldType,
            LinkRowFieldType,
            LongTextFieldType,
            LookupFieldType,
            MultipleCollaboratorsFieldType,
            MultipleSelectFieldType,
            NumberFieldType,
            PasswordFieldType,
            PhoneNumberFieldType,
            RatingFieldType,
            RollupFieldType,
            SingleSelectFieldType,
            TextFieldType,
            URLFieldType,
            UUIDFieldType,
        )

        field_type_registry.register(TextFieldType())
        field_type_registry.register(LongTextFieldType())
        field_type_registry.register(URLFieldType())
        field_type_registry.register(EmailFieldType())
        field_type_registry.register(NumberFieldType())
        field_type_registry.register(RatingFieldType())
        field_type_registry.register(BooleanFieldType())
        field_type_registry.register(DateFieldType())
        field_type_registry.register(LastModifiedFieldType())
        field_type_registry.register(LastModifiedByFieldType())
        field_type_registry.register(CreatedOnFieldType())
        field_type_registry.register(CreatedByFieldType())
        field_type_registry.register(DurationFieldType())
        field_type_registry.register(LinkRowFieldType())
        field_type_registry.register(FileFieldType())
        field_type_registry.register(SingleSelectFieldType())
        field_type_registry.register(MultipleSelectFieldType())
        field_type_registry.register(PhoneNumberFieldType())
        field_type_registry.register(FormulaFieldType())
        field_type_registry.register(CountFieldType())
        field_type_registry.register(RollupFieldType())
        field_type_registry.register(LookupFieldType())
        field_type_registry.register(MultipleCollaboratorsFieldType())
        field_type_registry.register(UUIDFieldType())
        field_type_registry.register(AutonumberFieldType())
        field_type_registry.register(PasswordFieldType())

        from .fields.field_aggregations import (
            AverageFieldAggregationType,
            CheckedFieldAggregationType,
            CheckedPercentageFieldAggregationType,
            CountFieldAggregationType,
            EarliestDateFieldAggregationType,
            EmptyCountFieldAggregationType,
            EmptyPercentageFieldAggregationType,
            LatestDateFieldAggregationType,
            MaxFieldAggregationType,
            MedianFieldAggregationType,
            MinFieldAggregationType,
            NotCheckedFieldAggregationType,
            NotCheckedPercentageFieldAggregationType,
            NotEmptyCountFieldAggregationType,
            NotEmptyPercentageFieldAggregationType,
            StdDevFieldAggregationType,
            SumFieldAggregationType,
            UniqueCountFieldAggregationType,
            VarianceFieldAggregationType,
        )

        field_aggregation_registry.register(CountFieldAggregationType())
        field_aggregation_registry.register(EmptyCountFieldAggregationType())
        field_aggregation_registry.register(NotEmptyCountFieldAggregationType())
        field_aggregation_registry.register(CheckedFieldAggregationType())
        field_aggregation_registry.register(NotCheckedFieldAggregationType())
        field_aggregation_registry.register(EmptyPercentageFieldAggregationType())
        field_aggregation_registry.register(NotEmptyPercentageFieldAggregationType())
        field_aggregation_registry.register(CheckedPercentageFieldAggregationType())
        field_aggregation_registry.register(NotCheckedPercentageFieldAggregationType())
        field_aggregation_registry.register(UniqueCountFieldAggregationType())
        field_aggregation_registry.register(MinFieldAggregationType())
        field_aggregation_registry.register(MaxFieldAggregationType())
        field_aggregation_registry.register(EarliestDateFieldAggregationType())
        field_aggregation_registry.register(LatestDateFieldAggregationType())
        field_aggregation_registry.register(SumFieldAggregationType())
        field_aggregation_registry.register(AverageFieldAggregationType())
        field_aggregation_registry.register(StdDevFieldAggregationType())
        field_aggregation_registry.register(VarianceFieldAggregationType())
        field_aggregation_registry.register(MedianFieldAggregationType())

        from .fields.field_converters import (
            AutonumberFieldConverter,
            FileFieldConverter,
            FormulaFieldConverter,
            LinkRowFieldConverter,
            MultipleCollaboratorsFieldConverter,
            MultipleSelectFieldToSingleSelectFieldConverter,
            MultipleSelectFieldToTextFieldConverter,
            PasswordFieldConverter,
            SingleSelectFieldToMultipleSelectFieldConverter,
            TextFieldToMultipleSelectFieldConverter,
        )

        field_converter_registry.register(MultipleCollaboratorsFieldConverter())
        field_converter_registry.register(LinkRowFieldConverter())
        field_converter_registry.register(FileFieldConverter())
        field_converter_registry.register(TextFieldToMultipleSelectFieldConverter())
        field_converter_registry.register(MultipleSelectFieldToTextFieldConverter())
        field_converter_registry.register(
            MultipleSelectFieldToSingleSelectFieldConverter()
        )
        field_converter_registry.register(
            SingleSelectFieldToMultipleSelectFieldConverter()
        )
        field_converter_registry.register(FormulaFieldConverter())
        field_converter_registry.register(AutonumberFieldConverter())
        field_converter_registry.register(PasswordFieldConverter())

        from .fields.actions import (
            ChangePrimaryFieldActionType,
            CreateFieldActionType,
            DeleteFieldActionType,
            DuplicateFieldActionType,
            UpdateFieldActionType,
        )

        action_type_registry.register(CreateFieldActionType())
        action_type_registry.register(DeleteFieldActionType())
        action_type_registry.register(UpdateFieldActionType())
        action_type_registry.register(DuplicateFieldActionType())
        action_type_registry.register(ChangePrimaryFieldActionType())

        from .views.view_types import FormViewType, GalleryViewType, GridViewType

        view_type_registry.register(GridViewType())
        view_type_registry.register(GalleryViewType())
        view_type_registry.register(FormViewType())

        from .views.view_filters import (
            BooleanViewFilterType,
            ContainsNotViewFilterType,
            ContainsViewFilterType,
            ContainsWordViewFilterType,
            DateAfterDaysAgoViewFilterType,
            DateAfterOrEqualViewFilterType,
            DateAfterTodayViewFilterType,
            DateAfterViewFilterType,
            DateBeforeOrEqualViewFilterType,
            DateBeforeTodayViewFilterType,
            DateBeforeViewFilterType,
            DateEqualsCurrentMonthViewFilterType,
            DateEqualsCurrentWeekViewFilterType,
            DateEqualsCurrentYearViewFilterType,
            DateEqualsDayOfMonthViewFilterType,
            DateEqualsDaysAgoViewFilterType,
            DateEqualsMonthsAgoViewFilterType,
            DateEqualsTodayViewFilterType,
            DateEqualsYearsAgoViewFilterType,
            DateEqualViewFilterType,
            DateIsAfterMultiStepFilterType,
            DateIsBeforeMultiStepFilterType,
            DateIsEqualMultiStepFilterType,
            DateIsNotEqualMultiStepFilterType,
            DateIsOnOrAfterMultiStepFilterType,
            DateIsOnOrBeforeMultiStepFilterType,
            DateIsWithinMultiStepFilterType,
            DateIsWithinXDaysViewFilterType,
            DateIsWithinXMonthsViewFilterType,
            DateIsWithinXWeeksViewFilterType,
            DateNotEqualViewFilterType,
            DoesntContainWordViewFilterType,
            EmptyViewFilterType,
            EqualViewFilterType,
            FilenameContainsViewFilterType,
            FilesLowerThanViewFilterType,
            HasFileTypeViewFilterType,
            HigherThanOrEqualViewFilterType,
            HigherThanViewFilterType,
            IsEvenAndWholeViewFilterType,
            LengthIsLowerThanViewFilterType,
            LinkRowContainsViewFilterType,
            LinkRowHasNotViewFilterType,
            LinkRowHasViewFilterType,
            LinkRowNotContainsViewFilterType,
            LowerThanOrEqualViewFilterType,
            LowerThanViewFilterType,
            MultipleCollaboratorsHasNotViewFilterType,
            MultipleCollaboratorsHasViewFilterType,
            MultipleSelectHasNotViewFilterType,
            MultipleSelectHasViewFilterType,
            NotEmptyViewFilterType,
            NotEqualViewFilterType,
            SingleSelectEqualViewFilterType,
            SingleSelectIsAnyOfViewFilterType,
            SingleSelectIsNoneOfViewFilterType,
            SingleSelectNotEqualViewFilterType,
            UserIsNotViewFilterType,
            UserIsViewFilterType,
        )

        view_filter_type_registry.register(EqualViewFilterType())
        view_filter_type_registry.register(NotEqualViewFilterType())
        view_filter_type_registry.register(FilenameContainsViewFilterType())
        view_filter_type_registry.register(FilesLowerThanViewFilterType()),
        view_filter_type_registry.register(HasFileTypeViewFilterType())
        view_filter_type_registry.register(ContainsViewFilterType())
        view_filter_type_registry.register(ContainsNotViewFilterType())
        view_filter_type_registry.register(ContainsWordViewFilterType())
        view_filter_type_registry.register(DoesntContainWordViewFilterType())
        view_filter_type_registry.register(LengthIsLowerThanViewFilterType())
        view_filter_type_registry.register(HigherThanViewFilterType())
        view_filter_type_registry.register(HigherThanOrEqualViewFilterType())
        view_filter_type_registry.register(LowerThanViewFilterType())
        view_filter_type_registry.register(LowerThanOrEqualViewFilterType())
        view_filter_type_registry.register(IsEvenAndWholeViewFilterType())
        view_filter_type_registry.register(DateEqualViewFilterType())
        view_filter_type_registry.register(DateBeforeViewFilterType())
        view_filter_type_registry.register(DateBeforeOrEqualViewFilterType())
        view_filter_type_registry.register(DateAfterDaysAgoViewFilterType())
        view_filter_type_registry.register(DateAfterViewFilterType())
        view_filter_type_registry.register(DateAfterOrEqualViewFilterType())
        view_filter_type_registry.register(DateNotEqualViewFilterType())
        view_filter_type_registry.register(DateEqualsTodayViewFilterType())
        view_filter_type_registry.register(DateBeforeTodayViewFilterType())
        view_filter_type_registry.register(DateAfterTodayViewFilterType())
        view_filter_type_registry.register(DateIsWithinXDaysViewFilterType())
        view_filter_type_registry.register(DateIsWithinXWeeksViewFilterType())
        view_filter_type_registry.register(DateIsWithinXMonthsViewFilterType())
        view_filter_type_registry.register(DateEqualsDaysAgoViewFilterType())
        view_filter_type_registry.register(DateEqualsMonthsAgoViewFilterType())
        view_filter_type_registry.register(DateEqualsYearsAgoViewFilterType())
        view_filter_type_registry.register(DateEqualsCurrentWeekViewFilterType())
        view_filter_type_registry.register(DateEqualsCurrentMonthViewFilterType())
        view_filter_type_registry.register(DateEqualsDayOfMonthViewFilterType())
        view_filter_type_registry.register(DateEqualsCurrentYearViewFilterType())
        view_filter_type_registry.register(DateIsEqualMultiStepFilterType())
        view_filter_type_registry.register(DateIsNotEqualMultiStepFilterType())
        view_filter_type_registry.register(DateIsBeforeMultiStepFilterType())
        view_filter_type_registry.register(DateIsOnOrBeforeMultiStepFilterType())
        view_filter_type_registry.register(DateIsAfterMultiStepFilterType())
        view_filter_type_registry.register(DateIsOnOrAfterMultiStepFilterType())
        view_filter_type_registry.register(DateIsWithinMultiStepFilterType())
        view_filter_type_registry.register(SingleSelectEqualViewFilterType())
        view_filter_type_registry.register(SingleSelectNotEqualViewFilterType())
        view_filter_type_registry.register(SingleSelectIsAnyOfViewFilterType())
        view_filter_type_registry.register(SingleSelectIsNoneOfViewFilterType())
        view_filter_type_registry.register(LinkRowHasViewFilterType())
        view_filter_type_registry.register(LinkRowHasNotViewFilterType())
        view_filter_type_registry.register(LinkRowContainsViewFilterType())
        view_filter_type_registry.register(LinkRowNotContainsViewFilterType())
        view_filter_type_registry.register(BooleanViewFilterType())
        view_filter_type_registry.register(EmptyViewFilterType())
        view_filter_type_registry.register(NotEmptyViewFilterType())
        view_filter_type_registry.register(MultipleSelectHasViewFilterType())
        view_filter_type_registry.register(MultipleSelectHasNotViewFilterType())
        view_filter_type_registry.register(MultipleCollaboratorsHasViewFilterType())
        view_filter_type_registry.register(MultipleCollaboratorsHasNotViewFilterType())
        view_filter_type_registry.register(UserIsViewFilterType())
        view_filter_type_registry.register(UserIsNotViewFilterType())

        from .views.array_view_filters import (
            HasAllValuesEqualViewFilterType,
            HasAnySelectOptionEqualViewFilterType,
            HasDateAfterViewFilterType,
            HasDateBeforeViewFilterType,
            HasDateEqualViewFilterType,
            HasDateOnOrAfterViewFilterType,
            HasDateOnOrBeforeViewFilterType,
            HasDateWithinViewFilterType,
            HasEmptyValueViewFilterType,
            HasNoneSelectOptionEqualViewFilterType,
            HasNotDateAfterViewFilterType,
            HasNotDateBeforeViewFilterType,
            HasNotDateEqualViewFilterType,
            HasNotDateOnOrAfterViewFilterType,
            HasNotDateOnOrBeforeViewFilterType,
            HasNotDateWithinViewFilterType,
            HasNotEmptyValueViewFilterType,
            HasNotValueContainsViewFilterType,
            HasNotValueContainsWordViewFilterType,
            HasNotValueEqualViewFilterType,
            HasNotValueHigherOrEqualTHanFilterType,
            HasNotValueHigherThanFilterType,
            HasNotValueLowerOrEqualTHanFilterType,
            HasNotValueLowerThanFilterType,
            HasValueComparableToFilter,
            HasValueContainsViewFilterType,
            HasValueContainsWordViewFilterType,
            HasValueEqualViewFilterType,
            HasValueHigherOrEqualThanFilter,
            HasValueLengthIsLowerThanViewFilterType,
            HasValueLowerOrEqualThanFilter,
            HasValueLowerThanFilter,
        )

        view_filter_type_registry.register(HasValueEqualViewFilterType())
        view_filter_type_registry.register(HasNotValueEqualViewFilterType())
        view_filter_type_registry.register(HasValueContainsViewFilterType())
        view_filter_type_registry.register(HasNotValueContainsViewFilterType())
        view_filter_type_registry.register(HasValueContainsWordViewFilterType())
        view_filter_type_registry.register(HasNotValueContainsWordViewFilterType())
        view_filter_type_registry.register(HasValueLengthIsLowerThanViewFilterType())
        view_filter_type_registry.register(HasAllValuesEqualViewFilterType())
        view_filter_type_registry.register(HasEmptyValueViewFilterType())
        view_filter_type_registry.register(HasNotEmptyValueViewFilterType())
        view_filter_type_registry.register(HasAnySelectOptionEqualViewFilterType())
        view_filter_type_registry.register(HasNoneSelectOptionEqualViewFilterType())
        view_filter_type_registry.register(HasValueLowerThanFilter())
        view_filter_type_registry.register(HasValueLowerOrEqualThanFilter())
        view_filter_type_registry.register(HasValueComparableToFilter())
        view_filter_type_registry.register(HasValueHigherOrEqualThanFilter())
        view_filter_type_registry.register(HasNotValueHigherOrEqualTHanFilterType())
        view_filter_type_registry.register(HasNotValueHigherThanFilterType())
        view_filter_type_registry.register(HasNotValueLowerOrEqualTHanFilterType())
        view_filter_type_registry.register(HasNotValueLowerThanFilterType())
        view_filter_type_registry.register(HasDateEqualViewFilterType())
        view_filter_type_registry.register(HasNotDateEqualViewFilterType())
        view_filter_type_registry.register(HasDateBeforeViewFilterType())
        view_filter_type_registry.register(HasNotDateBeforeViewFilterType())
        view_filter_type_registry.register(HasDateOnOrBeforeViewFilterType())
        view_filter_type_registry.register(HasNotDateOnOrBeforeViewFilterType())
        view_filter_type_registry.register(HasDateOnOrAfterViewFilterType())
        view_filter_type_registry.register(HasNotDateOnOrAfterViewFilterType())
        view_filter_type_registry.register(HasDateAfterViewFilterType())
        view_filter_type_registry.register(HasNotDateAfterViewFilterType())
        view_filter_type_registry.register(HasDateWithinViewFilterType())
        view_filter_type_registry.register(HasNotDateWithinViewFilterType())

        from .views.view_aggregations import (
            AverageViewAggregationType,
            CountViewAggregationType,
            DecileViewAggregationType,
            DistributionViewAggregationType,
            EmptyCountViewAggregationType,
            MaxViewAggregationType,
            MedianViewAggregationType,
            MinViewAggregationType,
            NotEmptyCountViewAggregationType,
            StdDevViewAggregationType,
            SumViewAggregationType,
            UniqueCountViewAggregationType,
            VarianceViewAggregationType,
        )

        view_aggregation_type_registry.register(CountViewAggregationType())
        view_aggregation_type_registry.register(EmptyCountViewAggregationType())
        view_aggregation_type_registry.register(NotEmptyCountViewAggregationType())
        view_aggregation_type_registry.register(UniqueCountViewAggregationType())
        view_aggregation_type_registry.register(MinViewAggregationType())
        view_aggregation_type_registry.register(MaxViewAggregationType())
        view_aggregation_type_registry.register(SumViewAggregationType())
        view_aggregation_type_registry.register(AverageViewAggregationType())
        view_aggregation_type_registry.register(MedianViewAggregationType())
        view_aggregation_type_registry.register(DecileViewAggregationType())
        view_aggregation_type_registry.register(VarianceViewAggregationType())
        view_aggregation_type_registry.register(StdDevViewAggregationType())
        view_aggregation_type_registry.register(DistributionViewAggregationType())

        from .views.form_view_mode_types import FormViewModeTypeForm

        form_view_mode_registry.register(FormViewModeTypeForm())

        from .views.view_ownership_types import CollaborativeViewOwnershipType

        view_ownership_type_registry.register(CollaborativeViewOwnershipType())

        from .application_types import DatabaseApplicationType

        application_type_registry.register(DatabaseApplicationType())

        from .ws.pages import PublicViewPageType, RowPageType, TablePageType

        page_registry.register(TablePageType())
        page_registry.register(PublicViewPageType())
        page_registry.register(RowPageType())

        from .export.table_exporters.csv_table_exporter import CsvTableExporter

        table_exporter_registry.register(CsvTableExporter())

        from .trash.trash_types import (
            FieldTrashableItemType,
            RowsTrashableItemType,
            RowTrashableItemType,
            TableTrashableItemType,
            ViewTrashableItemType,
        )

        trash_item_type_registry.register(TableTrashableItemType())
        trash_item_type_registry.register(FieldTrashableItemType())
        trash_item_type_registry.register(RowTrashableItemType())
        trash_item_type_registry.register(RowsTrashableItemType())
        trash_item_type_registry.register(ViewTrashableItemType())

        from .formula.ast.function_defs import register_formula_functions

        register_formula_functions(formula_function_registry)

        from .rows.webhook_event_types import (
            RowsCreatedEventType,
            RowsDeletedEventType,
            RowsUpdatedEventType,
        )

        webhook_event_type_registry.register(RowsCreatedEventType())
        webhook_event_type_registry.register(RowsUpdatedEventType())
        webhook_event_type_registry.register(RowsDeletedEventType())

        from .fields.webhook_event_types import (
            FieldCreatedEventType,
            FieldDeletedEventType,
            FieldUpdatedEventType,
        )

        webhook_event_type_registry.register(FieldCreatedEventType())
        webhook_event_type_registry.register(FieldUpdatedEventType())
        webhook_event_type_registry.register(FieldDeletedEventType())

        from .views.webhook_event_types import (
            ViewCreatedEventType,
            ViewDeletedEventType,
            ViewUpdatedEventType,
        )

        webhook_event_type_registry.register(ViewCreatedEventType())
        webhook_event_type_registry.register(ViewUpdatedEventType())
        webhook_event_type_registry.register(ViewDeletedEventType())

        from .airtable.airtable_column_types import (
            AutoNumberAirtableColumnType,
            CheckboxAirtableColumnType,
            CountAirtableColumnType,
            DateAirtableColumnType,
            ForeignKeyAirtableColumnType,
            FormulaAirtableColumnType,
            MultilineTextAirtableColumnType,
            MultipleAttachmentAirtableColumnType,
            MultiSelectAirtableColumnType,
            NumberAirtableColumnType,
            PhoneAirtableColumnType,
            RatingAirtableColumnType,
            RichTextTextAirtableColumnType,
            SelectAirtableColumnType,
            TextAirtableColumnType,
        )

        airtable_column_type_registry.register(TextAirtableColumnType())
        airtable_column_type_registry.register(DateAirtableColumnType())
        airtable_column_type_registry.register(NumberAirtableColumnType())
        airtable_column_type_registry.register(SelectAirtableColumnType())
        airtable_column_type_registry.register(MultiSelectAirtableColumnType())
        airtable_column_type_registry.register(RatingAirtableColumnType())
        airtable_column_type_registry.register(FormulaAirtableColumnType())
        airtable_column_type_registry.register(CheckboxAirtableColumnType())
        airtable_column_type_registry.register(PhoneAirtableColumnType())
        airtable_column_type_registry.register(ForeignKeyAirtableColumnType())
        airtable_column_type_registry.register(MultilineTextAirtableColumnType())
        airtable_column_type_registry.register(MultipleAttachmentAirtableColumnType())
        airtable_column_type_registry.register(RichTextTextAirtableColumnType())
        airtable_column_type_registry.register(CountAirtableColumnType())
        airtable_column_type_registry.register(AutoNumberAirtableColumnType())

        from .airtable.airtable_view_types import (
            GalleryAirtableViewType,
            GridAirtableViewType,
        )

        airtable_view_type_registry.register(GridAirtableViewType())
        airtable_view_type_registry.register(GalleryAirtableViewType())

        from .airtable.airtable_filter_operators import (
            AirtableContainsOperator,
            AirtableDoesNotContainOperator,
            AirtableEqualOperator,
            AirtableFilenameOperator,
            AirtableFiletypeOperator,
            AirtableHasAllOfOperator,
            AirtableHasAnyOfOperator,
            AirtableIsAnyOfOperator,
            AirtableIsEmptyOperator,
            AirtableIsNoneOfOperator,
            AirtableIsNotEmptyOperator,
            AirtableIsWithinOperator,
            AirtableLessThanOperator,
            AirtableLessThanOrEqualOperator,
            AirtableMoreThanOperator,
            AirtableMoreThanOrEqualOperator,
            AirtableNotEqualOperator,
        )

        airtable_filter_operator_registry.register(AirtableContainsOperator())
        airtable_filter_operator_registry.register(AirtableDoesNotContainOperator())
        airtable_filter_operator_registry.register(AirtableEqualOperator())
        airtable_filter_operator_registry.register(AirtableNotEqualOperator())
        airtable_filter_operator_registry.register(AirtableIsEmptyOperator())
        airtable_filter_operator_registry.register(AirtableIsNotEmptyOperator())
        airtable_filter_operator_registry.register(AirtableFilenameOperator())
        airtable_filter_operator_registry.register(AirtableFiletypeOperator())
        airtable_filter_operator_registry.register(AirtableIsAnyOfOperator())
        airtable_filter_operator_registry.register(AirtableIsNoneOfOperator())
        airtable_filter_operator_registry.register(AirtableHasAnyOfOperator())
        airtable_filter_operator_registry.register(AirtableHasAllOfOperator())
        airtable_filter_operator_registry.register(AirtableLessThanOperator())
        airtable_filter_operator_registry.register(AirtableMoreThanOperator())
        airtable_filter_operator_registry.register(AirtableLessThanOrEqualOperator())
        airtable_filter_operator_registry.register(AirtableMoreThanOrEqualOperator())
        airtable_filter_operator_registry.register(AirtableIsWithinOperator())

        from .data_sync.data_sync_types import (
            ICalCalendarDataSyncType,
            PostgreSQLDataSyncType,
        )

        data_sync_type_registry.register(ICalCalendarDataSyncType())
        data_sync_type_registry.register(PostgreSQLDataSyncType())

        from baserow.contrib.database.table.usage_types import (
            TableWorkspaceStorageUsageItemType,
        )

        workspace_storage_usage_item_registry.register(
            TableWorkspaceStorageUsageItemType()
        )

        from baserow.contrib.database.views.usage_types import (
            FormViewWorkspaceStorageUsageItem,
        )

        workspace_storage_usage_item_registry.register(
            FormViewWorkspaceStorageUsageItem()
        )

        from baserow.core.jobs.registries import job_type_registry

        from .airtable.job_types import AirtableImportJobType
        from .data_sync.job_types import SyncDataSyncTableJobType
        from .fields.job_types import DuplicateFieldJobType
        from .file_import.job_types import FileImportJobType
        from .table.job_types import DuplicateTableJobType

        job_type_registry.register(AirtableImportJobType())
        job_type_registry.register(FileImportJobType())
        job_type_registry.register(DuplicateTableJobType())
        job_type_registry.register(DuplicateFieldJobType())
        job_type_registry.register(SyncDataSyncTableJobType())

        post_migrate.connect(safely_update_formula_versions, sender=self)
        pre_migrate.connect(clear_generated_model_cache_receiver, sender=self)

        from .fields.object_scopes import FieldObjectScopeType
        from .object_scopes import DatabaseObjectScopeType
        from .table.object_scopes import DatabaseTableObjectScopeType
        from .tokens.object_scopes import TokenObjectScopeType
        from .views.object_scopes import (
            DatabaseViewDecorationObjectScopeType,
            DatabaseViewFilterGroupObjectScopeType,
            DatabaseViewFilterObjectScopeType,
            DatabaseViewGroupByObjectScopeType,
            DatabaseViewObjectScopeType,
            DatabaseViewSortObjectScopeType,
        )

        object_scope_type_registry.register(DatabaseObjectScopeType())
        object_scope_type_registry.register(DatabaseTableObjectScopeType())
        object_scope_type_registry.register(FieldObjectScopeType())
        object_scope_type_registry.register(DatabaseViewObjectScopeType())
        object_scope_type_registry.register(DatabaseViewDecorationObjectScopeType())
        object_scope_type_registry.register(DatabaseViewSortObjectScopeType())
        object_scope_type_registry.register(DatabaseViewGroupByObjectScopeType())
        object_scope_type_registry.register(DatabaseViewFilterObjectScopeType())
        object_scope_type_registry.register(DatabaseViewFilterGroupObjectScopeType())
        object_scope_type_registry.register(TokenObjectScopeType())

        from baserow.contrib.database.views.operations import (
            CanReceiveNotificationOnSubmitFormViewOperationType,
            UpdateViewFieldOptionsOperationType,
        )

        from .airtable.operations import RunAirtableImportJobOperationType
        from .data_sync.operations import (
            GetIncludingPublicValuesOperationType,
            ListPropertiesOperationType,
            SyncTableOperationType,
        )
        from .export.operations import ExportTableOperationType
        from .fields.operations import (
            CreateFieldOperationType,
            DeleteFieldOperationType,
            DeleteRelatedLinkRowFieldOperationType,
            DuplicateFieldOperationType,
            ListFieldsOperationType,
            ReadFieldOperationType,
            RestoreFieldOperationType,
            SubmitAnonymousFieldValuesOperationType,
            UpdateFieldOperationType,
            WriteFieldValuesOperationType,
        )
        from .formula import TypeFormulaOperationType
        from .operations import (
            CreateTableDatabaseTableOperationType,
            ListTablesDatabaseTableOperationType,
            OrderTablesDatabaseTableOperationType,
        )
        from .rows.operations import (
            DeleteDatabaseRowOperationType,
            MoveRowDatabaseRowOperationType,
            ReadAdjacentRowDatabaseRowOperationType,
            ReadDatabaseRowHistoryOperationType,
            ReadDatabaseRowOperationType,
            RestoreDatabaseRowOperationType,
            UpdateDatabaseRowOperationType,
        )
        from .table.operations import (
            CreateRowDatabaseTableOperationType,
            DeleteDatabaseTableOperationType,
            DuplicateDatabaseTableOperationType,
            ImportRowsDatabaseTableOperationType,
            ListenToAllDatabaseTableEventsOperationType,
            ListRowNamesDatabaseTableOperationType,
            ListRowsDatabaseTableOperationType,
            ReadDatabaseTableOperationType,
            UpdateDatabaseTableOperationType,
        )
        from .tokens.operations import (
            CreateTokenOperationType,
            ReadTokenOperationType,
            UpdateTokenOperationType,
            UseTokenOperationType,
        )
        from .views.operations import (
            CreateAndUsePersonalViewOperationType,
            CreatePublicViewOperationType,
            CreateViewDecorationOperationType,
            CreateViewFilterGroupOperationType,
            CreateViewFilterOperationType,
            CreateViewGroupByOperationType,
            CreateViewOperationType,
            CreateViewRowOperationType,
            CreateViewSortOperationType,
            DeleteViewDecorationOperationType,
            DeleteViewFilterGroupOperationType,
            DeleteViewFilterOperationType,
            DeleteViewGroupByOperationType,
            DeleteViewOperationType,
            DeleteViewRowOperationType,
            DeleteViewSortOperationType,
            DuplicateViewOperationType,
            ListAggregationsViewOperationType,
            ListViewDecorationOperationType,
            ListViewFilterOperationType,
            ListViewGroupByOperationType,
            ListViewsOperationType,
            ListViewSortOperationType,
            OrderViewsOperationType,
            ReadAggregationsViewOperationType,
            ReadViewDecorationOperationType,
            ReadViewFieldOptionsOperationType,
            ReadViewFilterGroupOperationType,
            ReadViewFilterOperationType,
            ReadViewGroupByOperationType,
            ReadViewOperationType,
            ReadViewRowOperationType,
            ReadViewsOrderOperationType,
            ReadViewSortOperationType,
            RestoreViewOperationType,
            UpdateViewDecorationOperationType,
            UpdateViewFilterGroupOperationType,
            UpdateViewFilterOperationType,
            UpdateViewGroupByOperationType,
            UpdateViewOperationType,
            UpdateViewPublicOperationType,
            UpdateViewRowOperationType,
            UpdateViewSlugOperationType,
            UpdateViewSortOperationType,
        )
        from .webhooks.operations import (
            CreateWebhookOperationType,
            DeleteWebhookOperationType,
            ListTableWebhooksOperationType,
            ReadWebhookOperationType,
            TestTriggerWebhookOperationType,
            UpdateWebhookOperationType,
        )

        operation_type_registry.register(ReadViewRowOperationType())
        operation_type_registry.register(CreateViewRowOperationType())
        operation_type_registry.register(UpdateViewRowOperationType())
        operation_type_registry.register(DeleteViewRowOperationType())
        operation_type_registry.register(CreateTableDatabaseTableOperationType())
        operation_type_registry.register(ListTablesDatabaseTableOperationType())
        operation_type_registry.register(OrderTablesDatabaseTableOperationType())
        operation_type_registry.register(CreateRowDatabaseTableOperationType())
        operation_type_registry.register(ImportRowsDatabaseTableOperationType())
        operation_type_registry.register(DeleteDatabaseTableOperationType())
        operation_type_registry.register(DuplicateDatabaseTableOperationType())
        operation_type_registry.register(ListRowsDatabaseTableOperationType())
        operation_type_registry.register(ReadDatabaseTableOperationType())
        operation_type_registry.register(UpdateDatabaseTableOperationType())
        operation_type_registry.register(ReadDatabaseRowOperationType())
        operation_type_registry.register(UpdateDatabaseRowOperationType())
        operation_type_registry.register(DeleteDatabaseRowOperationType())
        operation_type_registry.register(CreateViewSortOperationType())
        operation_type_registry.register(ReadViewSortOperationType())
        operation_type_registry.register(UpdateViewSortOperationType())
        operation_type_registry.register(CreateViewGroupByOperationType())
        operation_type_registry.register(ReadViewGroupByOperationType())
        operation_type_registry.register(UpdateViewGroupByOperationType())
        operation_type_registry.register(CreateFieldOperationType())
        operation_type_registry.register(ReadFieldOperationType())
        operation_type_registry.register(UpdateFieldOperationType())
        operation_type_registry.register(DeleteFieldOperationType())
        operation_type_registry.register(DeleteRelatedLinkRowFieldOperationType())
        operation_type_registry.register(DuplicateFieldOperationType())
        operation_type_registry.register(UpdateViewFieldOptionsOperationType())
        operation_type_registry.register(WriteFieldValuesOperationType())
        operation_type_registry.register(SubmitAnonymousFieldValuesOperationType())
        operation_type_registry.register(DeleteViewSortOperationType())
        operation_type_registry.register(DeleteViewGroupByOperationType())
        operation_type_registry.register(UpdateViewSlugOperationType())
        operation_type_registry.register(UpdateViewPublicOperationType())
        operation_type_registry.register(ReadViewsOrderOperationType())
        operation_type_registry.register(OrderViewsOperationType())
        operation_type_registry.register(CreateViewOperationType())
        operation_type_registry.register(CreatePublicViewOperationType())
        operation_type_registry.register(CreateAndUsePersonalViewOperationType())
        operation_type_registry.register(ReadViewOperationType())
        operation_type_registry.register(UpdateViewOperationType())
        operation_type_registry.register(
            CanReceiveNotificationOnSubmitFormViewOperationType()
        )
        operation_type_registry.register(DeleteViewOperationType())
        operation_type_registry.register(DuplicateViewOperationType())
        operation_type_registry.register(CreateViewFilterOperationType())
        operation_type_registry.register(ReadViewFilterOperationType())
        operation_type_registry.register(UpdateViewFilterOperationType())
        operation_type_registry.register(DeleteViewFilterOperationType())
        operation_type_registry.register(DeleteViewDecorationOperationType())
        operation_type_registry.register(CreateWebhookOperationType())
        operation_type_registry.register(DeleteWebhookOperationType())
        operation_type_registry.register(ReadWebhookOperationType())
        operation_type_registry.register(ListTableWebhooksOperationType())
        operation_type_registry.register(TestTriggerWebhookOperationType())
        operation_type_registry.register(UpdateWebhookOperationType())
        operation_type_registry.register(RestoreDatabaseTableOperationType())
        operation_type_registry.register(RestoreDatabaseRowOperationType())
        operation_type_registry.register(RestoreFieldOperationType())
        operation_type_registry.register(RestoreViewOperationType())
        operation_type_registry.register(RunAirtableImportJobOperationType())
        operation_type_registry.register(TypeFormulaOperationType())
        operation_type_registry.register(ListRowNamesDatabaseTableOperationType())
        operation_type_registry.register(ReadAdjacentRowDatabaseRowOperationType())
        operation_type_registry.register(ReadDatabaseRowHistoryOperationType())
        operation_type_registry.register(ReadAggregationsViewOperationType())
        operation_type_registry.register(ListAggregationsViewOperationType())
        operation_type_registry.register(ExportTableOperationType())
        operation_type_registry.register(ListFieldsOperationType())
        operation_type_registry.register(ListViewsOperationType())
        operation_type_registry.register(ListViewFilterOperationType())
        operation_type_registry.register(ListViewDecorationOperationType())
        operation_type_registry.register(CreateViewDecorationOperationType())
        operation_type_registry.register(ReadViewDecorationOperationType())
        operation_type_registry.register(UpdateViewDecorationOperationType())
        operation_type_registry.register(ListViewSortOperationType())
        operation_type_registry.register(ListViewGroupByOperationType())
        operation_type_registry.register(ReadViewFieldOptionsOperationType())
        operation_type_registry.register(MoveRowDatabaseRowOperationType())
        operation_type_registry.register(CreateTokenOperationType())
        operation_type_registry.register(ReadTokenOperationType())
        operation_type_registry.register(ListenToAllDatabaseTableEventsOperationType())
        operation_type_registry.register(UseTokenOperationType())
        operation_type_registry.register(UpdateTokenOperationType())
        operation_type_registry.register(CreateViewFilterGroupOperationType())
        operation_type_registry.register(UpdateViewFilterGroupOperationType())
        operation_type_registry.register(DeleteViewFilterGroupOperationType())
        operation_type_registry.register(ReadViewFilterGroupOperationType())
        operation_type_registry.register(SyncTableOperationType())
        operation_type_registry.register(ListPropertiesOperationType())
        operation_type_registry.register(GetIncludingPublicValuesOperationType())

        from baserow.core.registries import permission_manager_type_registry

        from .permission_manager import AllowIfTemplatePermissionManagerType
        from .tokens.permission_manager import TokenPermissionManagerType

        permission_manager_type_registry.register(TokenPermissionManagerType())

        prev_manager = permission_manager_type_registry.get(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.unregister(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.register(
            AllowIfTemplatePermissionManagerType(prev_manager)
        )

        from baserow.core.registries import subject_type_registry

        from .tokens.subjects import TokenSubjectType

        subject_type_registry.register(TokenSubjectType())

        from baserow.contrib.database.data_providers.registries import (
            database_data_provider_type_registry,
        )

        from .rows.data_providers import HumanReadableFieldsDataProviderType

        database_data_provider_type_registry.register(
            HumanReadableFieldsDataProviderType()
        )

        # notification_types
        from baserow.contrib.database.fields.notification_types import (
            CollaboratorAddedToRowNotificationType,
            UserMentionInRichTextFieldNotificationType,
        )
        from baserow.contrib.database.views.notification_types import (
            FormSubmittedNotificationType,
        )
        from baserow.contrib.database.webhooks.notification_types import (
            WebhookDeactivatedNotificationType,
            WebhookPayloadTooLargeNotificationType,
        )
        from baserow.core.notifications.registries import notification_type_registry

        notification_type_registry.register(CollaboratorAddedToRowNotificationType())
        notification_type_registry.register(
            UserMentionInRichTextFieldNotificationType()
        )
        notification_type_registry.register(FormSubmittedNotificationType())
        notification_type_registry.register(WebhookDeactivatedNotificationType())
        notification_type_registry.register(WebhookPayloadTooLargeNotificationType())

        from baserow.contrib.database.mcp.rows.tools import (
            CreateRowMcpTool,
            DeleteRowMcpTool,
            ListRowsMcpTool,
            UpdateRowMcpTool,
        )
        from baserow.contrib.database.mcp.table.tools import ListTablesMcpTool
        from baserow.core.mcp.registries import mcp_tool_registry

        mcp_tool_registry.register(ListTablesMcpTool())
        mcp_tool_registry.register(ListRowsMcpTool())
        mcp_tool_registry.register(CreateRowMcpTool())
        mcp_tool_registry.register(UpdateRowMcpTool())
        mcp_tool_registry.register(DeleteRowMcpTool())

        from baserow.contrib.database.rows.history_providers import (
            CreateRowHistoryProvider,
            CreateRowsHistoryProvider,
            DeleteRowHistoryProvider,
            DeleteRowsHistoryProvider,
            RestoreFromTrashHistoryProvider,
            UpdateRowsHistoryProvider,
        )
        from baserow.contrib.database.rows.registries import (
            row_history_provider_registry,
        )

        row_history_provider_registry.register(CreateRowHistoryProvider())
        row_history_provider_registry.register(CreateRowsHistoryProvider())
        row_history_provider_registry.register(DeleteRowsHistoryProvider())
        row_history_provider_registry.register(DeleteRowHistoryProvider())
        row_history_provider_registry.register(UpdateRowsHistoryProvider())
        row_history_provider_registry.register(RestoreFromTrashHistoryProvider())

        from baserow.core.search.registries import workspace_search_registry

        from .search_types import (
            DatabaseSearchType,
            FieldDefinitionSearchType,
            RowSearchType,
            TableSearchType,
        )

        workspace_search_registry.register(DatabaseSearchType())
        workspace_search_registry.register(FieldDefinitionSearchType())
        workspace_search_registry.register(RowSearchType())
        workspace_search_registry.register(TableSearchType())

        from baserow.contrib.database.fields.field_constraints import (
            RatingTypeUniqueWithEmptyConstraint,
            TextTypeUniqueWithEmptyConstraint,
            UniqueWithEmptyConstraint,
        )

        field_constraint_registry.register(TextTypeUniqueWithEmptyConstraint())
        field_constraint_registry.register(RatingTypeUniqueWithEmptyConstraint())
        field_constraint_registry.register(UniqueWithEmptyConstraint())

        from baserow.contrib.database.field_rules.actions import (
            CreateFieldRuleActionType,
            DeleteFieldRuleActionType,
            UpdateFieldRuleActionType,
        )
        from baserow.contrib.database.field_rules.operations import (
            ReadFieldRuleOperationType,
            SetFieldRuleOperationType,
        )

        operation_type_registry.register(SetFieldRuleOperationType())
        operation_type_registry.register(ReadFieldRuleOperationType())

        action_type_registry.register(CreateFieldRuleActionType())
        action_type_registry.register(UpdateFieldRuleActionType())
        action_type_registry.register(DeleteFieldRuleActionType())

        from baserow.contrib.database.ws.public.rows.view_realtime_rows import (
            PublicViewRealtimeRowsType,
        )
        from baserow.contrib.database.ws.views.rows.registries import (
            view_realtime_rows_registry,
        )

        if not settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS:
            view_realtime_rows_registry.register(PublicViewRealtimeRowsType())

        # The signals must always be imported last because they use the registries
        # which need to be filled first.
        import baserow.contrib.database.data_sync.signals  # noqa: F403, F401
        import baserow.contrib.database.ws.signals  # noqa: F403, F401

        post_migrate.connect(safely_update_formula_versions, sender=self)
        pre_migrate.connect(clear_generated_model_cache_receiver, sender=self)

        import baserow.contrib.database.field_rules.receivers  # noqa: F401
        import baserow.contrib.database.field_rules.signals  # noqa: F401
        import baserow.contrib.database.fields.receivers  # noqa: F401
        import baserow.contrib.database.fields.tasks  # noqa: F401
        import baserow.contrib.database.rows.history  # noqa: F401
        import baserow.contrib.database.rows.tasks  # noqa: F401
        import baserow.contrib.database.search.receivers  # noqa: F403, F401
        import baserow.contrib.database.search.tasks  # noqa: F401
        import baserow.contrib.database.table.receivers  # noqa: F401
        import baserow.contrib.database.views.receivers  # noqa: F401
        import baserow.contrib.database.views.tasks  # noqa: F401
        from baserow.contrib.database.fields.models import SelectOption

        # Make sure that from now on, no model can make the User cache to expire,
        # because that can be a problem if some other thread tries to access the related
        # profile while the cache is being cleared.
        # NOTE: Make sure all FK or M2M fields to User are created with
        # `related_name="+"` because the relation won't be created on the user side.
        get_user_model()._meta._expire_cache = lambda *a, **kw: None
        SelectOption._meta._expire_cache = lambda *a, **kw: None

        # date/datetime min/max year handling - replace overflowed date with None
        pg_init()


# noinspection PyPep8Naming
def clear_generated_model_cache_receiver(sender, **kwargs):
    clear_generated_model_cache()


# noinspection PyPep8Naming
def safely_update_formula_versions(sender, **kwargs):
    if settings.TESTS:
        return

    apps = kwargs.get("apps", None)
    # app.ready will be called for management commands also, we only want to
    # execute the following hook when we are starting the django server as
    # otherwise backwards migrations etc will crash because of this.
    if apps is not None and not settings.DONT_UPDATE_FORMULAS_AFTER_MIGRATION:
        try:
            FormulaField = apps.get_model("database", "FormulaField")
            # noinspection PyProtectedMember
            FormulaField._meta.get_field("version")
        except (LookupError, FieldDoesNotExist):
            print(
                "Skipping formula update as FormulaField does not exist or have "
                "version column."
            )
            # We are starting up a version of baserow before formulas with versions
            # existed, there is nothing to do.
            return

        try:
            FormulaField.objects.exists()
        except ProgrammingError:
            print("Skipping formula update as formula field table doesnt exist yet.")
            # The migrations to create FormulaField and FormulaField.version
            # exist but they have not yet been applied.
            return

        print("Checking to see if formulas need updating...")
        from baserow.contrib.database.formula.migrations.handler import (
            FormulaMigrationHandler,
        )

        FormulaMigrationHandler.migrate_formulas_to_latest_version()
