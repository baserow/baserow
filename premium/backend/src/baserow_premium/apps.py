from django.apps import AppConfig

from baserow.core.registries import operation_type_registry


class BaserowPremiumConfig(AppConfig):
    name = "baserow_premium"

    def ready(self):
        # noinspection PyUnresolvedReferences
        import baserow_premium.row_comments.receivers  # noqa: F401
        from baserow_premium.api.user.user_data_types import ActiveLicensesDataType
        from baserow_premium.row_comments.row_metadata_types import (
            RowCommentCountMetadataType,
            RowCommentsNotificationModeMetadataType,
        )

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

        import baserow_premium.fields.tasks  # noqa: F401
