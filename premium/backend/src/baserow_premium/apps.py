from django.apps import AppConfig

from baserow.core.registries import operation_type_registry


class BaserowPremiumConfig(AppConfig):
    name = "baserow_premium"

    def ready(self):
        # noinspection PyUnresolvedReferences
        import baserow_premium.row_comments.receivers  # noqa: F401
        from baserow_premium.api.user.user_data_types import ActiveLicensesDataType
        from baserow_premium.builder.application_types import (
            PremiumBuilderApplicationType,
        )
        from baserow_premium.row_comments.row_metadata_types import (
            RowCommentCountMetadataType,
            RowCommentsNotificationModeMetadataType,
        )

        from baserow.core.registries import application_type_registry

        # We replace the original application type with the premium one to
        # add the licences to workspace serializer
        application_type_registry.unregister(PremiumBuilderApplicationType.type)
        application_type_registry.register(PremiumBuilderApplicationType())

        from baserow.api.user.registries import user_data_registry
        from baserow.contrib.database.export.registries import table_exporter_registry
        from baserow.contrib.database.fields.registries import (
            field_converter_registry,
            field_type_registry,
        )

        from .fields.actions import GenerateFormulaWithAIActionType
        from .fields.ai_field_output_types import (
            ChoiceAIFieldOutputType,
            TextAIFieldOutputType,
        )
        from .fields.field_converters import AIFieldConverter
        from .fields.field_types import AIFieldType
        from .fields.registries import ai_field_output_registry

        field_type_registry.register(AIFieldType())

        field_converter_registry.register(AIFieldConverter())

        ai_field_output_registry.register(TextAIFieldOutputType())
        ai_field_output_registry.register(ChoiceAIFieldOutputType())

        from baserow.core.jobs.registries import job_type_registry

        from .fields.job_types import GenerateAIValuesJobType

        job_type_registry.register(GenerateAIValuesJobType())

        from baserow.contrib.database.rows.registries import row_metadata_registry
        from baserow.contrib.database.views.registries import (
            decorator_type_registry,
            decorator_value_provider_type_registry,
            form_view_mode_registry,
            view_ownership_type_registry,
            view_type_registry,
        )
        from baserow.core.action.registries import action_type_registry
        from baserow.core.registries import plugin_registry

        action_type_registry.register(GenerateFormulaWithAIActionType())

        from .export.exporter_types import (
            ExcelTableExporter,
            FileTableExporter,
            JSONTableExporter,
            XMLTableExporter,
        )
        from .plugins import PremiumPlugin
        from .views.actions import RotateCalendarIcalSlugActionType
        from .views.decorator_types import (
            BackgroundColorDecoratorType,
            LeftBorderColorDecoratorType,
        )
        from .views.decorator_value_provider_types import (
            ConditionalColorValueProviderType,
            SelectColorValueProviderType,
        )
        from .views.form_view_mode_types import FormViewModeTypeSurvey
        from .views.view_types import CalendarViewType, KanbanViewType, TimelineViewType

        plugin_registry.register(PremiumPlugin())

        table_exporter_registry.register(JSONTableExporter())
        table_exporter_registry.register(XMLTableExporter())
        table_exporter_registry.register(ExcelTableExporter())
        table_exporter_registry.register(FileTableExporter())

        row_metadata_registry.register(RowCommentCountMetadataType())
        row_metadata_registry.register(RowCommentsNotificationModeMetadataType())

        user_data_registry.register(ActiveLicensesDataType())

        view_type_registry.register(KanbanViewType())
        view_type_registry.register(CalendarViewType())
        view_type_registry.register(TimelineViewType())

        form_view_mode_registry.register(FormViewModeTypeSurvey())

        decorator_type_registry.register(LeftBorderColorDecoratorType())
        decorator_type_registry.register(BackgroundColorDecoratorType())

        decorator_value_provider_type_registry.register(SelectColorValueProviderType())
        decorator_value_provider_type_registry.register(
            ConditionalColorValueProviderType()
        )

        from .views.view_ownership_types import PersonalViewOwnershipType

        view_ownership_type_registry.register(PersonalViewOwnershipType())

        from baserow_premium.license.license_types import PremiumLicenseType
        from baserow_premium.license.registries import license_type_registry

        license_type_registry.register(PremiumLicenseType())

        from baserow_premium.row_comments.actions import (
            CreateRowCommentActionType,
            DeleteRowCommentActionType,
            UpdateRowCommentActionType,
        )

        action_type_registry.register(CreateRowCommentActionType())
        action_type_registry.register(DeleteRowCommentActionType())
        action_type_registry.register(UpdateRowCommentActionType())
        action_type_registry.register(RotateCalendarIcalSlugActionType())

        from .row_comments.operations import (
            CreateRowCommentsOperationType,
            DeleteRowCommentsOperationType,
            ReadRowCommentsOperationType,
            RestoreRowCommentOperationType,
            UpdateRowCommentsOperationType,
        )

        operation_type_registry.register(ReadRowCommentsOperationType())
        operation_type_registry.register(DeleteRowCommentsOperationType())
        operation_type_registry.register(CreateRowCommentsOperationType())
        operation_type_registry.register(RestoreRowCommentOperationType())
        operation_type_registry.register(UpdateRowCommentsOperationType())

        from baserow.core.trash.registries import trash_item_type_registry

        from .row_comments.trash_types import RowCommentTrashableItemType

        trash_item_type_registry.register(RowCommentTrashableItemType())

        # The signals must always be imported last because they use the registries
        # which need to be filled first.
        import baserow_premium.views.signals as view_signals  # noqa: F403, F401
        import baserow_premium.ws.signals  # noqa: F403, F401

        view_signals.connect_to_user_pre_delete_signal()

        from baserow.core.registries import permission_manager_type_registry

        from .permission_manager import ViewOwnershipPermissionManagerType

        permission_manager_type_registry.register(ViewOwnershipPermissionManagerType())

        from baserow_premium.row_comments.notification_types import (
            RowCommentMentionNotificationType,
            RowCommentNotificationType,
        )

        from baserow.core.notifications.registries import notification_type_registry

        notification_type_registry.register(RowCommentMentionNotificationType())
        notification_type_registry.register(RowCommentNotificationType())

        from baserow_premium.api.settings.settings_types import (
            InstanceWideSettingsDataType,
        )

        from baserow.api.settings.registries import settings_data_registry

        settings_data_registry.register(InstanceWideSettingsDataType())

        from baserow_premium.integrations.registries import grouped_aggregation_registry

        from baserow.contrib.database.fields.field_aggregations import (
            AverageFieldAggregationType,
            CheckedFieldAggregationType,
            CheckedPercentageFieldAggregationType,
            CountFieldAggregationType,
            EmptyCountFieldAggregationType,
            EmptyPercentageFieldAggregationType,
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

        grouped_aggregation_registry.register(CountFieldAggregationType())
        grouped_aggregation_registry.register(EmptyCountFieldAggregationType())
        grouped_aggregation_registry.register(NotEmptyCountFieldAggregationType())
        grouped_aggregation_registry.register(CheckedFieldAggregationType())
        grouped_aggregation_registry.register(NotCheckedFieldAggregationType())
        grouped_aggregation_registry.register(EmptyPercentageFieldAggregationType())
        grouped_aggregation_registry.register(NotEmptyPercentageFieldAggregationType())
        grouped_aggregation_registry.register(CheckedPercentageFieldAggregationType())
        grouped_aggregation_registry.register(
            NotCheckedPercentageFieldAggregationType()
        )
        grouped_aggregation_registry.register(UniqueCountFieldAggregationType())
        grouped_aggregation_registry.register(MinFieldAggregationType())
        grouped_aggregation_registry.register(MaxFieldAggregationType())
        grouped_aggregation_registry.register(SumFieldAggregationType())
        grouped_aggregation_registry.register(AverageFieldAggregationType())
        grouped_aggregation_registry.register(StdDevFieldAggregationType())
        grouped_aggregation_registry.register(VarianceFieldAggregationType())
        grouped_aggregation_registry.register(MedianFieldAggregationType())

        from baserow_premium.integrations.registries import (
            grouped_aggregation_group_by_registry,
        )

        from baserow.contrib.database.fields.field_types import (
            AutonumberFieldType,
            BooleanFieldType,
            EmailFieldType,
            LongTextFieldType,
            NumberFieldType,
            PhoneNumberFieldType,
            RatingFieldType,
            SingleSelectFieldType,
            TextFieldType,
            URLFieldType,
        )

        grouped_aggregation_group_by_registry.register(TextFieldType())
        grouped_aggregation_group_by_registry.register(LongTextFieldType())
        grouped_aggregation_group_by_registry.register(URLFieldType())
        grouped_aggregation_group_by_registry.register(EmailFieldType())
        grouped_aggregation_group_by_registry.register(NumberFieldType())
        grouped_aggregation_group_by_registry.register(RatingFieldType())
        grouped_aggregation_group_by_registry.register(BooleanFieldType())
        grouped_aggregation_group_by_registry.register(PhoneNumberFieldType())
        grouped_aggregation_group_by_registry.register(AutonumberFieldType())
        grouped_aggregation_group_by_registry.register(SingleSelectFieldType())

        from baserow_premium.dashboard.widgets.widget_types import (
            ChartWidgetType,
            PieChartWidgetType,
        )
        from baserow_premium.integrations.local_baserow.service_types import (
            LocalBaserowGroupedAggregateRowsUserServiceType,
        )

        from baserow.contrib.dashboard.widgets.registries import widget_type_registry
        from baserow.core.services.registries import service_type_registry

        service_type_registry.register(
            LocalBaserowGroupedAggregateRowsUserServiceType()
        )
        widget_type_registry.register(ChartWidgetType())
        widget_type_registry.register(PieChartWidgetType())
