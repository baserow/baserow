from django.apps import AppConfig
from django.conf import settings
from django.db.models import Q
from django.db.models.signals import post_migrate, pre_migrate

from health_check.storage.backends import DefaultFileStorageHealthCheck

from baserow.cachalot_patch import clear_cachalot_cache
from baserow.core.sentry import patch_user_model_str


class CoreConfig(AppConfig):
    name = "baserow.core"

    def ready(self):
        # Patch Django's DecimalField to have lenient conversion
        # regarding NaN values
        from django.db.models import DecimalField

        from baserow.core.fields import LenientDecimalField

        DecimalField.to_python = LenientDecimalField.to_python

        from baserow.core.action.registries import (
            action_scope_registry,
            action_type_registry,
        )
        from baserow.core.trash.registries import trash_item_type_registry
        from baserow.core.trash.trash_types import (
            ApplicationTrashableItemType,
            WorkspaceTrashableItemType,
        )

        trash_item_type_registry.register(WorkspaceTrashableItemType())
        trash_item_type_registry.register(ApplicationTrashableItemType())

        from baserow.core.formula.registries import formula_runtime_function_registry
        from baserow.core.formula.runtime_formula_types import (
            RuntimeAdd,
            RuntimeAnd,
            RuntimeAt,
            RuntimeAvg,
            RuntimeCapitalize,
            RuntimeConcat,
            RuntimeContains,
            RuntimeDateTimeFormat,
            RuntimeDay,
            RuntimeDivide,
            RuntimeEqual,
            RuntimeGenerateUUID,
            RuntimeGet,
            RuntimeGetProperty,
            RuntimeGreaterThan,
            RuntimeGreaterThanOrEqual,
            RuntimeHour,
            RuntimeIf,
            RuntimeIsEmpty,
            RuntimeIsEven,
            RuntimeIsOdd,
            RuntimeJoin,
            RuntimeLength,
            RuntimeLessThan,
            RuntimeLessThanOrEqual,
            RuntimeLower,
            RuntimeMinus,
            RuntimeMinute,
            RuntimeMonth,
            RuntimeMultiply,
            RuntimeNotEqual,
            RuntimeNow,
            RuntimeOr,
            RuntimeRandomBool,
            RuntimeRandomFloat,
            RuntimeRandomInt,
            RuntimeReplace,
            RuntimeReverse,
            RuntimeRound,
            RuntimeSecond,
            RuntimeSplit,
            RuntimeStrip,
            RuntimeSum,
            RuntimeToArray,
            RuntimeToday,
            RuntimeUpper,
            RuntimeYear,
        )

        formula_runtime_function_registry.register(RuntimeConcat())
        formula_runtime_function_registry.register(RuntimeGet())
        formula_runtime_function_registry.register(RuntimeAdd())
        formula_runtime_function_registry.register(RuntimeMinus())
        formula_runtime_function_registry.register(RuntimeMultiply())
        formula_runtime_function_registry.register(RuntimeDivide())
        formula_runtime_function_registry.register(RuntimeEqual())
        formula_runtime_function_registry.register(RuntimeNotEqual())
        formula_runtime_function_registry.register(RuntimeLessThan())
        formula_runtime_function_registry.register(RuntimeLessThanOrEqual())
        formula_runtime_function_registry.register(RuntimeGreaterThan())
        formula_runtime_function_registry.register(RuntimeGreaterThanOrEqual())
        formula_runtime_function_registry.register(RuntimeUpper())
        formula_runtime_function_registry.register(RuntimeLower())
        formula_runtime_function_registry.register(RuntimeCapitalize())
        formula_runtime_function_registry.register(RuntimeRound())
        formula_runtime_function_registry.register(RuntimeIsEven())
        formula_runtime_function_registry.register(RuntimeIsOdd())
        formula_runtime_function_registry.register(RuntimeDateTimeFormat())
        formula_runtime_function_registry.register(RuntimeDay())
        formula_runtime_function_registry.register(RuntimeMonth())
        formula_runtime_function_registry.register(RuntimeYear())
        formula_runtime_function_registry.register(RuntimeHour())
        formula_runtime_function_registry.register(RuntimeMinute())
        formula_runtime_function_registry.register(RuntimeSecond())
        formula_runtime_function_registry.register(RuntimeNow())
        formula_runtime_function_registry.register(RuntimeToday())
        formula_runtime_function_registry.register(RuntimeGetProperty())
        formula_runtime_function_registry.register(RuntimeRandomInt())
        formula_runtime_function_registry.register(RuntimeRandomFloat())
        formula_runtime_function_registry.register(RuntimeRandomBool())
        formula_runtime_function_registry.register(RuntimeGenerateUUID())
        formula_runtime_function_registry.register(RuntimeIf())
        formula_runtime_function_registry.register(RuntimeAnd())
        formula_runtime_function_registry.register(RuntimeOr())
        formula_runtime_function_registry.register(RuntimeReplace())
        formula_runtime_function_registry.register(RuntimeLength())
        formula_runtime_function_registry.register(RuntimeContains())
        formula_runtime_function_registry.register(RuntimeReverse())
        formula_runtime_function_registry.register(RuntimeJoin())
        formula_runtime_function_registry.register(RuntimeSplit())
        formula_runtime_function_registry.register(RuntimeIsEmpty())
        formula_runtime_function_registry.register(RuntimeStrip())
        formula_runtime_function_registry.register(RuntimeSum())
        formula_runtime_function_registry.register(RuntimeAvg())
        formula_runtime_function_registry.register(RuntimeAt())
        formula_runtime_function_registry.register(RuntimeToArray())

        from baserow.core.permission_manager import (
            AllowIfTemplatePermissionManagerType,
            BasicPermissionManagerType,
            CorePermissionManagerType,
            StaffOnlyPermissionManagerType,
            StaffOnlySettingOperationPermissionManagerType,
            WorkspaceMemberOnlyPermissionManagerType,
        )
        from baserow.core.registries import (
            email_context_registry,
            object_scope_type_registry,
            operation_type_registry,
            permission_manager_type_registry,
        )

        from .emails_context_types import CoreEmailContextType

        email_context_registry.register(CoreEmailContextType())

        permission_manager_type_registry.register(CorePermissionManagerType())
        permission_manager_type_registry.register(StaffOnlyPermissionManagerType())
        permission_manager_type_registry.register(BasicPermissionManagerType())
        permission_manager_type_registry.register(
            WorkspaceMemberOnlyPermissionManagerType()
        )
        permission_manager_type_registry.register(
            StaffOnlySettingOperationPermissionManagerType()
        )
        permission_manager_type_registry.register(
            AllowIfTemplatePermissionManagerType()
        )

        from .object_scopes import (
            ApplicationObjectScopeType,
            CoreObjectScopeType,
            WorkspaceInvitationObjectScopeType,
            WorkspaceObjectScopeType,
            WorkspaceUserObjectScopeType,
        )
        from .snapshots.object_scopes import SnapshotObjectScopeType

        object_scope_type_registry.register(CoreObjectScopeType())
        object_scope_type_registry.register(ApplicationObjectScopeType())
        object_scope_type_registry.register(WorkspaceObjectScopeType())
        object_scope_type_registry.register(WorkspaceInvitationObjectScopeType())
        object_scope_type_registry.register(SnapshotObjectScopeType())
        object_scope_type_registry.register(WorkspaceUserObjectScopeType())

        from baserow.core.registries import subject_type_registry

        from .subjects import AnonymousUserSubjectType, UserSubjectType
        from .user_sources.subjects import UserSourceUserSubjectType

        subject_type_registry.register(UserSubjectType())
        subject_type_registry.register(AnonymousUserSubjectType())
        subject_type_registry.register(UserSourceUserSubjectType())

        from .notifications.operations import (
            ClearNotificationsOperationType,
            ListNotificationsOperationType,
            MarkNotificationAsReadOperationType,
        )
        from .operations import (
            CreateApplicationsWorkspaceOperationType,
            CreateInvitationsWorkspaceOperationType,
            CreateWorkspaceOperationType,
            DeleteApplicationOperationType,
            DeleteWorkspaceInvitationOperationType,
            DeleteWorkspaceOperationType,
            DeleteWorkspaceUserOperationType,
            DuplicateApplicationOperationType,
            ListApplicationsWorkspaceOperationType,
            ListInvitationsWorkspaceOperationType,
            ListWorkspacesOperationType,
            ListWorkspaceUsersWorkspaceOperationType,
            OrderApplicationsOperationType,
            ReadApplicationOperationType,
            ReadInvitationWorkspaceOperationType,
            ReadWorkspaceOperationType,
            RestoreApplicationOperationType,
            RestoreWorkspaceOperationType,
            UpdateApplicationOperationType,
            UpdateSettingsOperationType,
            UpdateWorkspaceInvitationType,
            UpdateWorkspaceOperationType,
            UpdateWorkspaceUserOperationType,
        )
        from .snapshots.operations import (
            CreateSnapshotApplicationOperationType,
            DeleteApplicationSnapshotOperationType,
            ListSnapshotsApplicationOperationType,
            RestoreApplicationSnapshotOperationType,
        )
        from .trash.operations import (
            EmptyApplicationTrashOperationType,
            EmptyWorkspaceTrashOperationType,
            ReadApplicationTrashOperationType,
            ReadWorkspaceTrashOperationType,
        )

        operation_type_registry.register(ClearNotificationsOperationType())
        operation_type_registry.register(ListNotificationsOperationType())
        operation_type_registry.register(MarkNotificationAsReadOperationType())
        operation_type_registry.register(CreateApplicationsWorkspaceOperationType())
        operation_type_registry.register(CreateWorkspaceOperationType())
        operation_type_registry.register(CreateInvitationsWorkspaceOperationType())
        operation_type_registry.register(DeleteWorkspaceInvitationOperationType())
        operation_type_registry.register(DeleteWorkspaceOperationType())
        operation_type_registry.register(ListApplicationsWorkspaceOperationType())
        operation_type_registry.register(ListInvitationsWorkspaceOperationType())
        operation_type_registry.register(ReadInvitationWorkspaceOperationType())
        operation_type_registry.register(ListWorkspacesOperationType())
        operation_type_registry.register(UpdateWorkspaceInvitationType())
        operation_type_registry.register(ReadWorkspaceOperationType())
        operation_type_registry.register(UpdateWorkspaceOperationType())
        operation_type_registry.register(ListWorkspaceUsersWorkspaceOperationType())
        operation_type_registry.register(OrderApplicationsOperationType())
        operation_type_registry.register(UpdateWorkspaceUserOperationType())
        operation_type_registry.register(DeleteWorkspaceUserOperationType())
        operation_type_registry.register(UpdateApplicationOperationType())
        operation_type_registry.register(DuplicateApplicationOperationType())
        operation_type_registry.register(DeleteApplicationOperationType())
        operation_type_registry.register(UpdateSettingsOperationType())
        operation_type_registry.register(CreateSnapshotApplicationOperationType())
        operation_type_registry.register(DeleteApplicationSnapshotOperationType())
        operation_type_registry.register(ListSnapshotsApplicationOperationType())
        operation_type_registry.register(RestoreApplicationSnapshotOperationType())
        operation_type_registry.register(ReadWorkspaceTrashOperationType())
        operation_type_registry.register(ReadApplicationTrashOperationType())
        operation_type_registry.register(EmptyApplicationTrashOperationType())
        operation_type_registry.register(EmptyWorkspaceTrashOperationType())
        operation_type_registry.register(RestoreApplicationOperationType())
        operation_type_registry.register(RestoreWorkspaceOperationType())
        operation_type_registry.register(ReadApplicationOperationType())

        from baserow.core.actions import (
            AcceptWorkspaceInvitationActionType,
            CreateApplicationActionType,
            CreateInitialWorkspaceActionType,
            CreateWorkspaceActionType,
            CreateWorkspaceInvitationActionType,
            DeleteApplicationActionType,
            DeleteWorkspaceActionType,
            DeleteWorkspaceInvitationActionType,
            DuplicateApplicationActionType,
            ExportApplicationsActionType,
            ImportApplicationsActionType,
            InstallTemplateActionType,
            LeaveWorkspaceActionType,
            OrderApplicationsActionType,
            OrderWorkspacesActionType,
            RejectWorkspaceInvitationActionType,
            UpdateApplicationActionType,
            UpdateWorkspaceActionType,
            UpdateWorkspaceInvitationActionType,
        )

        action_type_registry.register(CreateWorkspaceActionType())
        action_type_registry.register(DeleteWorkspaceActionType())
        action_type_registry.register(UpdateWorkspaceActionType())
        action_type_registry.register(OrderWorkspacesActionType())
        action_type_registry.register(CreateApplicationActionType())
        action_type_registry.register(UpdateApplicationActionType())
        action_type_registry.register(DeleteApplicationActionType())
        action_type_registry.register(OrderApplicationsActionType())
        action_type_registry.register(DuplicateApplicationActionType())
        action_type_registry.register(InstallTemplateActionType())
        action_type_registry.register(CreateWorkspaceInvitationActionType())
        action_type_registry.register(DeleteWorkspaceInvitationActionType())
        action_type_registry.register(AcceptWorkspaceInvitationActionType())
        action_type_registry.register(RejectWorkspaceInvitationActionType())
        action_type_registry.register(UpdateWorkspaceInvitationActionType())
        action_type_registry.register(LeaveWorkspaceActionType())
        action_type_registry.register(CreateInitialWorkspaceActionType())
        action_type_registry.register(ExportApplicationsActionType())
        action_type_registry.register(ImportApplicationsActionType())

        from baserow.core.snapshots.actions import (
            CreateSnapshotActionType,
            DeleteSnapshotActionType,
            RestoreSnapshotActionType,
        )

        action_type_registry.register(CreateSnapshotActionType())
        action_type_registry.register(DeleteSnapshotActionType())
        action_type_registry.register(RestoreSnapshotActionType())

        from baserow.core.trash.actions import (
            EmptyTrashActionType,
            RestoreFromTrashActionType,
        )

        action_type_registry.register(EmptyTrashActionType())
        action_type_registry.register(RestoreFromTrashActionType())

        from baserow.core.trash.registries import (
            DefaultTrashOperationType,
            trash_operation_type_registry,
        )

        trash_operation_type_registry.register(DefaultTrashOperationType())

        from baserow.core.mcp.actions import (
            CreateMCPEndpointActionType,
            DeleteMCPEndpointActionType,
            UpdateMCPEndpointActionType,
        )

        action_type_registry.register(CreateMCPEndpointActionType())
        action_type_registry.register(UpdateMCPEndpointActionType())
        action_type_registry.register(DeleteMCPEndpointActionType())

        from baserow.core.user.actions import (
            CancelUserDeletionActionType,
            ChangeEmailActionType,
            ChangeUserPasswordActionType,
            CreateUserActionType,
            ResetUserPasswordActionType,
            ScheduleUserDeletionActionType,
            SendChangeEmailConfirmationActionType,
            SendResetUserPasswordActionType,
            SendVerifyEmailAddressActionType,
            SignInUserActionType,
            UpdateUserActionType,
            VerifyEmailAddressActionType,
        )

        action_type_registry.register(CreateUserActionType())
        action_type_registry.register(UpdateUserActionType())
        action_type_registry.register(ScheduleUserDeletionActionType())
        action_type_registry.register(CancelUserDeletionActionType())
        action_type_registry.register(SignInUserActionType())
        action_type_registry.register(ChangeUserPasswordActionType())
        action_type_registry.register(SendResetUserPasswordActionType())
        action_type_registry.register(ResetUserPasswordActionType())
        action_type_registry.register(SendVerifyEmailAddressActionType())
        action_type_registry.register(VerifyEmailAddressActionType())
        action_type_registry.register(SendChangeEmailConfirmationActionType())
        action_type_registry.register(ChangeEmailActionType())

        from baserow.core.action.scopes import (
            ApplicationActionScopeType,
            RootActionScopeType,
            WorkspaceActionScopeType,
        )

        action_scope_registry.register(RootActionScopeType())
        action_scope_registry.register(WorkspaceActionScopeType())
        action_scope_registry.register(ApplicationActionScopeType())

        from baserow.core.jobs.registries import job_type_registry

        from .job_types import (
            DuplicateApplicationJobType,
            ExportApplicationsJobType,
            ImportApplicationsJobType,
            InstallTemplateJobType,
        )
        from .snapshots.job_types import CreateSnapshotJobType, RestoreSnapshotJobType

        job_type_registry.register(DuplicateApplicationJobType())
        job_type_registry.register(InstallTemplateJobType())
        job_type_registry.register(CreateSnapshotJobType())
        job_type_registry.register(RestoreSnapshotJobType())
        job_type_registry.register(ExportApplicationsJobType())
        job_type_registry.register(ImportApplicationsJobType())

        from baserow.api.notifications.user_data_types import (
            UnreadUserNotificationsCountPermissionsDataType,
        )
        from baserow.api.user.registries import user_data_registry
        from baserow.api.user.user_data_types import GlobalPermissionsDataType

        user_data_registry.register(GlobalPermissionsDataType())
        user_data_registry.register(UnreadUserNotificationsCountPermissionsDataType())

        from baserow.core.auth_provider.auth_provider_types import (
            PasswordAuthProviderType,
        )
        from baserow.core.registries import auth_provider_type_registry

        auth_provider_type_registry.register(PasswordAuthProviderType())

        from baserow.core.two_factor_auth.registries import (
            TOTPAuthProviderType,
            two_factor_auth_type_registry,
        )

        two_factor_auth_type_registry.register(TOTPAuthProviderType())

        import baserow.core.notifications.receivers  # noqa: F401
        import baserow.core.notifications.tasks  # noqa: F401
        from baserow.core.notification_types import (
            BaserowVersionUpgradeNotificationType,
            WorkspaceInvitationAcceptedNotificationType,
            WorkspaceInvitationCreatedNotificationType,
            WorkspaceInvitationRejectedNotificationType,
        )
        from baserow.core.notifications.registries import notification_type_registry

        notification_type_registry.register(
            WorkspaceInvitationAcceptedNotificationType()
        )
        notification_type_registry.register(
            WorkspaceInvitationCreatedNotificationType()
        )
        notification_type_registry.register(
            WorkspaceInvitationRejectedNotificationType()
        )
        notification_type_registry.register(BaserowVersionUpgradeNotificationType())

        from baserow.core.generative_ai.generative_ai_model_types import (
            AnthropicGenerativeAIModelType,
            MistralGenerativeAIModelType,
            OllamaGenerativeAIModelType,
            OpenAIGenerativeAIModelType,
            OpenRouterGenerativeAIModelType,
        )
        from baserow.core.generative_ai.registries import (
            generative_ai_model_type_registry,
        )

        generative_ai_model_type_registry.register(OpenAIGenerativeAIModelType())
        generative_ai_model_type_registry.register(AnthropicGenerativeAIModelType())
        generative_ai_model_type_registry.register(MistralGenerativeAIModelType())
        generative_ai_model_type_registry.register(OllamaGenerativeAIModelType())
        generative_ai_model_type_registry.register(OpenRouterGenerativeAIModelType())

        # Must import the Posthog signal, otherwise it won't work.
        import baserow.core.posthog  # noqa: F403, F401

        self._setup_health_checks()

        # Clear the key after migration so we will trigger a new template sync.
        post_migrate.connect(start_sync_templates_task_after_migrate, sender=self)
        # Create all operations from registry
        post_migrate.connect(sync_operations_after_migrate, sender=self)

        if settings.CACHALOT_ENABLED:
            pre_migrate.connect(lambda *a, **kw: clear_cachalot_cache(), sender=self)

        if settings.SENTRY_DSN:
            patch_user_model_str()

    def _setup_health_checks(self):
        from health_check.plugins import plugin_dir

        from baserow.core.integrations.object_scopes import IntegrationObjectScopeType
        from baserow.core.registries import (
            object_scope_type_registry,
            operation_type_registry,
        )

        from .health.custom_health_checks import (
            DebugModeHealthCheck,
            HerokuExternalFileStorageConfiguredHealthCheck,
        )

        object_scope_type_registry.register(IntegrationObjectScopeType())

        from baserow.core.integrations.operations import (
            CreateIntegrationOperationType,
            DeleteIntegrationOperationType,
            ListIntegrationsApplicationOperationType,
            OrderIntegrationsOperationType,
            ReadIntegrationOperationType,
            UpdateIntegrationOperationType,
        )

        operation_type_registry.register(CreateIntegrationOperationType())
        operation_type_registry.register(UpdateIntegrationOperationType())
        operation_type_registry.register(DeleteIntegrationOperationType())
        operation_type_registry.register(ListIntegrationsApplicationOperationType())
        operation_type_registry.register(ReadIntegrationOperationType())
        operation_type_registry.register(OrderIntegrationsOperationType())

        from baserow.core.user_sources.object_scopes import UserSourceObjectScopeType

        object_scope_type_registry.register(UserSourceObjectScopeType())

        from baserow.core.user_sources.operations import (
            AuthenticateUserSourceOperationType,
            CreateUserSourceOperationType,
            DeleteUserSourceOperationType,
            ListUserSourcesApplicationOperationType,
            LoginUserSourceOperationType,
            OrderUserSourcesOperationType,
            ReadUserSourceOperationType,
            UpdateUserSourceOperationType,
        )

        operation_type_registry.register(CreateUserSourceOperationType())
        operation_type_registry.register(DeleteUserSourceOperationType())
        operation_type_registry.register(ListUserSourcesApplicationOperationType())
        operation_type_registry.register(OrderUserSourcesOperationType())
        operation_type_registry.register(ReadUserSourceOperationType())
        operation_type_registry.register(UpdateUserSourceOperationType())
        operation_type_registry.register(AuthenticateUserSourceOperationType())
        operation_type_registry.register(LoginUserSourceOperationType())

        from baserow.core.mcp.operations import (
            CreateMCPEndpointOperationType,
            DeleteMCPEndpointOperationType,
            ReadMCPEndpointOperationType,
            UpdateMCPEndpointOperationType,
        )

        operation_type_registry.register(CreateMCPEndpointOperationType())
        operation_type_registry.register(ReadMCPEndpointOperationType())
        operation_type_registry.register(UpdateMCPEndpointOperationType())
        operation_type_registry.register(DeleteMCPEndpointOperationType())

        from baserow.core.mcp.object_scopes import MCPEndpointObjectScopeType

        object_scope_type_registry.register(MCPEndpointObjectScopeType())

        plugin_dir.register(DebugModeHealthCheck)
        if getattr(settings, "HEROKU_ENABLED", False):
            plugin_dir.register(HerokuExternalFileStorageConfiguredHealthCheck)
        plugin_dir.register(DefaultFileStorageHealthCheck)

        import baserow.core.import_export.tasks  # noqa: F403, F401
        import baserow.core.integrations.receivers  # noqa: F403, F401

        # pgvector extension setup. Because the extension is optional, we must
        # dynamically check if it's available and adjust the models accordingly.
        from baserow.core.pgvector import try_migrate_vector_fields

        post_migrate.connect(
            try_migrate_vector_fields,
            sender=self,
            dispatch_uid="baserow_core_pgvector_post_migrate",
        )


# noinspection PyPep8Naming
def start_sync_templates_task_after_migrate(sender, **kwargs):
    from baserow.core.tasks import sync_templates_task

    if settings.BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION and not settings.TESTS:
        print(
            "Submitting the sync templates task to run asynchronously in "
            "celery after the migration..."
        )
        sync_templates_task.delay()


def sync_operations_after_migrate(sender, **kwargs):
    apps = kwargs.get("apps", None)

    if apps is not None:
        try:
            Operation = apps.get_model("core", "Operation")
        except LookupError:
            print("Skipping operation creation as Operation model does not exist.")
        else:
            # Pluck out the `type` from each registered operation type.
            from baserow.core.registries import operation_type_registry

            all_operation_types = [o.type for o in operation_type_registry.get_all()]

            # Create all the operations that are registered in the registry.
            operations = [Operation(name=optype) for optype in all_operation_types]
            inserted_count = Operation.objects.bulk_create(
                operations, ignore_conflicts=True
            )
            print(f"Created {len(inserted_count)} operations...")

            # Delete any existing operations which aren't in the registry.
            _, deletions = Operation.objects.filter(
                ~Q(name__in=all_operation_types)
            ).delete()
            ops_deleted = deletions.get("core.Operation", 0)
            print(f"Deleted {ops_deleted} un-registered operations...")
