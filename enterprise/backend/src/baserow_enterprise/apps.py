from django.apps import AppConfig
from django.db.models.signals import post_migrate

from tqdm import tqdm


class BaserowEnterpriseConfig(AppConfig):
    name = "baserow_enterprise"

    def ready(self):
        from baserow.core.jobs.registries import job_type_registry
        from baserow_enterprise.audit_log.job_types import AuditLogExportJobType
        from baserow_enterprise.audit_log.operations import (
            ListWorkspaceAuditLogEntriesOperationType,
        )

        job_type_registry.register(AuditLogExportJobType())

        from baserow.api.user.registries import member_data_registry
        from baserow.core.action.registries import (
            action_scope_registry,
            action_type_registry,
        )
        from baserow.core.registries import (
            email_context_registry,
            object_scope_type_registry,
            operation_type_registry,
            plugin_registry,
        )
        from baserow.core.trash.registries import trash_item_type_registry
        from baserow_enterprise.api.member_data_types import (
            EnterpriseMemberTeamsDataType,
        )
        from baserow_enterprise.assistant.operations import (
            ChatAssistantChatOperationType,
        )
        from baserow_enterprise.role.actions import BatchAssignRoleActionType
        from baserow_enterprise.scopes import TeamsActionScopeType
        from baserow_enterprise.teams.actions import (
            CreateTeamActionType,
            CreateTeamSubjectActionType,
            DeleteTeamActionType,
            DeleteTeamSubjectActionType,
            UpdateTeamActionType,
        )
        from baserow_enterprise.teams.object_scopes import (
            TeamObjectScopeType,
            TeamSubjectObjectScopeType,
        )
        from baserow_enterprise.teams.operations import (
            CreateTeamOperationType,
            CreateTeamSubjectOperationType,
            DeleteTeamOperationType,
            DeleteTeamSubjectOperationType,
            ListTeamsOperationType,
            ListTeamSubjectsOperationType,
            ReadTeamOperationType,
            ReadTeamSubjectOperationType,
            RestoreTeamOperationType,
            UpdateTeamOperationType,
        )
        from baserow_enterprise.trash_types import TeamTrashableItemType

        from .emails_context_types import EnterpriseEmailContextType
        from .field_permissions.actions import UpdateFieldPermissionsActionType
        from .field_permissions.operations import (
            ReadFieldPermissionsOperationType,
            UpdateFieldPermissionsOperationType,
        )
        from .plugins import EnterprisePlugin
        from .role.member_data_types import EnterpriseRolesDataType
        from .role.operations import (
            AssignRoleWorkspaceOperationType,
            ReadRoleApplicationOperationType,
            ReadRoleTableOperationType,
            ReadRoleViewOperationType,
            ReadRoleWorkspaceOperationType,
            UpdateRoleApplicationOperationType,
            UpdateRoleTableOperationType,
            UpdateRoleViewOperationType,
        )
        from .teams.subjects import TeamSubjectType

        plugin_registry.register(EnterprisePlugin())

        email_context_registry.register(EnterpriseEmailContextType())

        from baserow.core.registries import application_type_registry
        from baserow_enterprise.builder.application_types import (
            EnterpriseBuilderApplicationType,
        )

        # We replace the original application type with the enterprise one to
        # add the custom code serializers
        application_type_registry.unregister(EnterpriseBuilderApplicationType.type)
        application_type_registry.register(EnterpriseBuilderApplicationType())

        action_type_registry.register(CreateTeamActionType())
        action_type_registry.register(UpdateTeamActionType())
        action_type_registry.register(DeleteTeamActionType())
        action_type_registry.register(CreateTeamSubjectActionType())
        action_type_registry.register(DeleteTeamSubjectActionType())
        action_type_registry.register(BatchAssignRoleActionType())
        action_type_registry.register(UpdateFieldPermissionsActionType())

        trash_item_type_registry.register(TeamTrashableItemType())

        member_data_registry.register(EnterpriseMemberTeamsDataType())
        member_data_registry.register(EnterpriseRolesDataType())

        object_scope_type_registry.register(TeamObjectScopeType())
        object_scope_type_registry.register(TeamSubjectObjectScopeType())

        action_scope_registry.register(TeamsActionScopeType())

        operation_type_registry.register(CreateTeamOperationType())
        operation_type_registry.register(ReadTeamOperationType())
        operation_type_registry.register(ListTeamsOperationType())
        operation_type_registry.register(UpdateTeamOperationType())
        operation_type_registry.register(DeleteTeamOperationType())
        operation_type_registry.register(CreateTeamSubjectOperationType())
        operation_type_registry.register(ReadTeamSubjectOperationType())
        operation_type_registry.register(ListTeamSubjectsOperationType())
        operation_type_registry.register(DeleteTeamSubjectOperationType())
        operation_type_registry.register(AssignRoleWorkspaceOperationType())
        operation_type_registry.register(ReadRoleWorkspaceOperationType())
        operation_type_registry.register(RestoreTeamOperationType())
        operation_type_registry.register(ReadRoleApplicationOperationType())
        operation_type_registry.register(UpdateRoleApplicationOperationType())
        operation_type_registry.register(ReadRoleTableOperationType())
        operation_type_registry.register(UpdateRoleTableOperationType())
        operation_type_registry.register(ListWorkspaceAuditLogEntriesOperationType())
        operation_type_registry.register(UpdateFieldPermissionsOperationType())
        operation_type_registry.register(ReadFieldPermissionsOperationType())
        operation_type_registry.register(ChatAssistantChatOperationType())
        operation_type_registry.register(ReadRoleViewOperationType())
        operation_type_registry.register(UpdateRoleViewOperationType())

        from baserow.contrib.database.field_rules.registries import (
            field_rules_type_registry,
        )

        from .date_dependency.field_rule_types import DateDependencyFieldRuleType

        field_rules_type_registry.register(DateDependencyFieldRuleType())

        from baserow.core.registries import subject_type_registry

        subject_type_registry.register(TeamSubjectType())

        from baserow.core.registries import permission_manager_type_registry

        from .field_permissions.permission_manager import FieldPermissionManagerType
        from .role.permission_manager import RolePermissionManagerType

        permission_manager_type_registry.register(FieldPermissionManagerType())
        permission_manager_type_registry.register(RolePermissionManagerType())

        from baserow_premium.license.registries import license_type_registry

        from baserow_enterprise.license_types import (
            AdvancedLicenseType,
            EnterpriseLicenseType,
            EnterpriseWithoutSupportLicenseType,
        )

        license_type_registry.register(AdvancedLicenseType())
        license_type_registry.register(EnterpriseWithoutSupportLicenseType())
        license_type_registry.register(EnterpriseLicenseType())

        from baserow.core.registries import auth_provider_type_registry
        from baserow_enterprise.sso.oauth2.auth_provider_types import (
            FacebookAuthProviderType,
            GitHubAuthProviderType,
            GitLabAuthProviderType,
            GoogleAuthProviderType,
            OpenIdConnectAuthProviderType,
        )
        from baserow_enterprise.sso.saml.auth_provider_types import SamlAuthProviderType

        auth_provider_type_registry.register(SamlAuthProviderType())
        auth_provider_type_registry.register(GoogleAuthProviderType())
        auth_provider_type_registry.register(FacebookAuthProviderType())
        auth_provider_type_registry.register(GitHubAuthProviderType())
        auth_provider_type_registry.register(GitLabAuthProviderType())
        auth_provider_type_registry.register(OpenIdConnectAuthProviderType())

        from baserow.core.registries import serialization_processor_registry
        from baserow_enterprise.structure_types import (
            RoleAssignmentSerializationProcessorType,
        )

        serialization_processor_registry.register(
            RoleAssignmentSerializationProcessorType()
        )

        from baserow.core.user_sources.registries import user_source_type_registry
        from baserow_enterprise.integrations.local_baserow.user_source_types import (
            LocalBaserowUserSourceType,
        )

        user_source_type_registry.register(LocalBaserowUserSourceType())

        from baserow.core.app_auth_providers.registries import (
            app_auth_provider_type_registry,
        )
        from baserow_enterprise.integrations.local_baserow.auth_provider_types import (
            LocalBaserowPasswordAppAuthProviderType,
        )

        app_auth_provider_type_registry.register(
            LocalBaserowPasswordAppAuthProviderType()
        )

        from baserow_enterprise.integrations.common.sso.oauth2.app_auth_provider_types import (
            OpenIdConnectAppAuthProviderType,
        )
        from baserow_enterprise.integrations.common.sso.saml.app_auth_provider_types import (
            SamlAppAuthProviderType,
        )

        app_auth_provider_type_registry.register(SamlAppAuthProviderType())
        app_auth_provider_type_registry.register(OpenIdConnectAppAuthProviderType())

        from baserow.contrib.builder.elements.registries import element_type_registry
        from baserow_enterprise.builder.elements.element_types import (
            AuthFormElementType,
            FileInputElementType,
        )

        element_type_registry.register(AuthFormElementType())
        element_type_registry.register(FileInputElementType())

        from baserow.contrib.database.data_sync.registries import (
            two_way_sync_strategy_type_registry,
        )
        from baserow_enterprise.data_sync.two_way_sync_strategy_types import (
            RealtimePushTwoWaySyncStrategy,
        )

        two_way_sync_strategy_type_registry.register(RealtimePushTwoWaySyncStrategy())

        from baserow.contrib.database.data_sync.registries import (
            data_sync_type_registry,
        )
        from baserow_enterprise.data_sync.data_sync_types import (
            GitHubIssuesDataSyncType,
            GitLabIssuesDataSyncType,
            HubspotContactsDataSyncType,
            JiraIssuesDataSyncType,
            LocalBaserowTableDataSyncType,
            PostgreSQLDataSyncType,
        )

        data_sync_type_registry.register(LocalBaserowTableDataSyncType())
        data_sync_type_registry.register(JiraIssuesDataSyncType())
        data_sync_type_registry.register(GitHubIssuesDataSyncType())
        data_sync_type_registry.register(GitLabIssuesDataSyncType())
        data_sync_type_registry.register(HubspotContactsDataSyncType())

        data_sync_type_registry.unregister(PostgreSQLDataSyncType.type)
        data_sync_type_registry.register(PostgreSQLDataSyncType())

        from baserow_enterprise.data_sync.actions import (
            UpdatePeriodicDataSyncIntervalActionType,
        )

        action_type_registry.register(UpdatePeriodicDataSyncIntervalActionType())

        from baserow.contrib.database.webhooks.registries import (
            webhook_event_type_registry,
        )
        from baserow_enterprise.webhook_event_types import RowsEnterViewEventType

        webhook_event_type_registry.register(RowsEnterViewEventType())

        # Create default roles
        post_migrate.connect(
            sync_default_roles_after_migrate,
            sender=self,
            dispatch_uid="sync_default_roles_after_migrate",
        )

        # Make sure that the assistant knowledge base is up to date after running the
        # migrations.
        post_migrate.connect(
            sync_assistant_knowledge_base,
            sender=self,
            dispatch_uid="sync_assistant_knowledge_base",
        )

        from baserow_enterprise.teams.receivers import (
            connect_to_post_delete_signals_to_cascade_deletion_to_team_subjects,
        )

        connect_to_post_delete_signals_to_cascade_deletion_to_team_subjects()

        from baserow_enterprise.role.receivers import (
            connect_to_post_delete_signals_to_cascade_deletion_to_role_assignments,
        )

        connect_to_post_delete_signals_to_cascade_deletion_to_role_assignments()

        from baserow.core.notifications.registries import notification_type_registry
        from baserow_enterprise.data_sync.notification_types import (
            PeriodicDataSyncDeactivatedNotificationType,
            TwoWaySyncDeactivatedNotificationType,
            TwoWaySyncUpdateFailedNotificationType,
        )

        notification_type_registry.register(
            PeriodicDataSyncDeactivatedNotificationType()
        )
        notification_type_registry.register(TwoWaySyncUpdateFailedNotificationType())
        notification_type_registry.register(TwoWaySyncDeactivatedNotificationType())

        from baserow_enterprise.assistant.tools import (
            CreateBuildersToolType,
            GenerateDatabaseFormulaToolType,
            GetTablesSchemaToolType,
            ListBuildersToolType,
            ListRowsToolType,
            ListTablesToolType,
            ListViewsToolType,
            ListWorkflowsToolType,
            NavigationToolType,
            RowsToolFactoryToolType,
            SearchDocsToolType,
            TableAndFieldsToolFactoryToolType,
            ViewsToolFactoryToolType,
            WorkflowToolFactoryToolType,
        )
        from baserow_enterprise.assistant.tools.registries import (
            assistant_tool_registry,
        )

        assistant_tool_registry.register(SearchDocsToolType())
        assistant_tool_registry.register(NavigationToolType())

        assistant_tool_registry.register(ListBuildersToolType())
        assistant_tool_registry.register(CreateBuildersToolType())
        assistant_tool_registry.register(ListTablesToolType())
        assistant_tool_registry.register(GetTablesSchemaToolType())
        assistant_tool_registry.register(TableAndFieldsToolFactoryToolType())
        assistant_tool_registry.register(GenerateDatabaseFormulaToolType())
        assistant_tool_registry.register(ListRowsToolType())
        assistant_tool_registry.register(RowsToolFactoryToolType())
        assistant_tool_registry.register(ListViewsToolType())
        assistant_tool_registry.register(ViewsToolFactoryToolType())

        assistant_tool_registry.register(ListWorkflowsToolType())
        assistant_tool_registry.register(WorkflowToolFactoryToolType())

        from baserow_enterprise.views.operations import (
            ListenToAllRestrictedViewEventsOperationType,
        )

        operation_type_registry.register(ListenToAllRestrictedViewEventsOperationType())

        from baserow.contrib.database.views.registries import (
            view_ownership_type_registry,
        )
        from baserow.contrib.database.ws.views.rows.registries import (
            view_realtime_rows_registry,
        )
        from baserow.core.feature_flags import feature_flag_is_enabled
        from baserow.ws.registries import page_registry
        from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType
        from baserow_enterprise.ws.pages import RestrictedViewPageType
        from baserow_enterprise.ws.restricted_view.rows.view_realtime_rows import (
            RestrictedViewRealtimeRowsType,
        )

        if feature_flag_is_enabled("view_permissions"):
            view_ownership_type_registry.register(RestrictedViewOwnershipType())

        page_registry.register(RestrictedViewPageType())
        view_realtime_rows_registry.register(RestrictedViewRealtimeRowsType())

        # The signals must always be imported last because they use the registries
        # which need to be filled first.
        import baserow_enterprise.assistant.tasks  # noqa: F
        import baserow_enterprise.audit_log.signals  # noqa: F
        import baserow_enterprise.ws.signals  # noqa: F


def sync_default_roles_after_migrate(sender, **kwargs):
    from baserow.core.db import LockedAtomicTransaction

    from .role.default_roles import default_roles, hidden_roles

    apps = kwargs.get("apps", None)

    if apps is not None:
        try:
            Operation = apps.get_model("core", "Operation")
            Role = apps.get_model("baserow_enterprise", "Role")
        except LookupError:
            print("Skipping role creation as related models does not exist.")
        else:
            # Note: we used to migrate `NO_ROLE` to `NO_ACCESS` here.
            # This was moved to 0010_rename_no_role_to_no_access.
            with LockedAtomicTransaction(Role):
                all_old_roles = {
                    r.uid: r for r in Role.objects.all().prefetch_related("operations")
                }
                all_old_operations = {op.name: op for op in Operation.objects.all()}

                for role_name, role_operations in tqdm(
                    default_roles.items(), desc="Syncing default roles"
                ):
                    is_hidden = role_name in hidden_roles
                    # Create any missing role or update existing ones
                    role = all_old_roles.get(role_name, None)
                    if role is None:
                        role = Role.objects.create(
                            uid=role_name,
                            name=f"role.{role_name}",
                            default=True,
                            hidden=is_hidden,
                        )
                    elif (
                        not role.default
                        or role.name != f"role.{role_name}"
                        or role.hidden != is_hidden
                    ):
                        role.name = f"role.{role_name}"
                        role.default = True
                        role.hidden = is_hidden
                        role.save(update_fields=["name", "default", "hidden"])

                    # Create any missing operations for the role
                    new_ops = Operation.objects.bulk_create(
                        [
                            Operation(name=op.type)
                            for op in role_operations
                            if op.type not in all_old_operations
                        ],
                    )
                    all_old_operations.update({op.name: op for op in new_ops})

                    old_role_ops = set(op.name for op in role.operations.all())
                    new_role_ops = set(op.type for op in role_operations)

                    roles_to_add = new_role_ops - old_role_ops
                    if roles_to_add:
                        role.operations.add(
                            *[all_old_operations[op] for op in roles_to_add],
                        )

                    to_remove = old_role_ops - new_role_ops
                    if to_remove:
                        role.operations.remove(
                            *[all_old_operations[op] for op in to_remove],
                        )


def sync_assistant_knowledge_base(sender, **kwargs):
    from baserow_enterprise.assistant.tasks import (
        sync_assistant_knowledge_base as sync_assistant_knowledge_base_task,
    )
    from baserow_enterprise.assistant.tools.search_user_docs.handler import (
        KnowledgeBaseHandler,
    )

    if KnowledgeBaseHandler().can_have_knowledge_base():
        print(
            "Submitting the sync assistant knowledge base task to run asynchronously "
            "in celery after the migration..."
        )
        sync_assistant_knowledge_base_task.delay()
    else:
        print(
            "Skipping assistant knowledge base sync because this instance does not "
            "have the `BASEROW_EMBEDDINGS_API_URL` environment variable "
            "configured or the PostgreSQL server does not have the pgvector extension."
        )
