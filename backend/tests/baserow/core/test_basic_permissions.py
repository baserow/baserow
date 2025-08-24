import inspect

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.db.models import Q, QuerySet
from django.test.utils import CaptureQueriesContext, override_settings

import pytest

from baserow.contrib.database.models import Database
from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.core.cache import local_cache
from baserow.core.exceptions import (
    PermissionDenied,
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import (
    ListIntegrationsApplicationOperationType,
    UpdateIntegrationOperationType,
)
from baserow.core.operations import (
    CreateApplicationsWorkspaceOperationType,
    ListApplicationsWorkspaceOperationType,
    ListWorkspacesOperationType,
    UpdateApplicationOperationType,
    UpdateSettingsOperationType,
    UpdateWorkspaceOperationType,
)
from baserow.core.permission_manager import (
    BasicPermissionManagerType,
    CorePermissionManagerType,
    StaffOnlyPermissionManagerType,
    WorkspaceMemberOnlyPermissionManagerType,
)
from baserow.core.registries import (
    ObjectScopeType,
    OperationType,
    object_scope_type_registry,
    operation_type_registry,
    permission_manager_type_registry,
)
from baserow.core.types import PermissionCheck
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.operations import (
    ListUserSourcesApplicationOperationType,
    LoginUserSourceOperationType,
    UpdateUserSourceOperationType,
)


@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=[
        "core",
        "setting_operation",
        "staff",
        "allow_if_template",
        "member",
        "token",
        "basic",
    ]
)
def test_check_permissions(data_fixture):
    user = data_fixture.create_user()
    user_workspace = data_fixture.create_user_workspace(permissions="ADMIN")
    user_workspace_2 = data_fixture.create_user_workspace(permissions="MEMBER")
    user_workspace_3 = data_fixture.create_user_workspace()
    data_fixture.create_template(workspace=user_workspace_3.workspace)

    # An external user shouldn't be allowed
    with pytest.raises(UserNotInWorkspace):
        CoreHandler().check_permissions(
            user,
            ListApplicationsWorkspaceOperationType.type,
            workspace=user_workspace.workspace,
            context=user_workspace.workspace,
        )

    with pytest.raises(UserNotInWorkspace):
        CoreHandler().check_permissions(
            user,
            UpdateWorkspaceOperationType.type,
            workspace=user_workspace.workspace,
            context=user_workspace.workspace,
        )

    assert (
        CoreHandler().check_permissions(
            user,
            ListApplicationsWorkspaceOperationType.type,
            workspace=user_workspace.workspace,
            context=user_workspace.workspace,
            raise_permission_exceptions=False,
        )
        is False
    )

    assert CoreHandler().check_permissions(
        user_workspace.user,
        ListApplicationsWorkspaceOperationType.type,
        workspace=user_workspace.workspace,
        context=user_workspace.workspace,
    )
    assert CoreHandler().check_permissions(
        user_workspace.user,
        UpdateWorkspaceOperationType.type,
        workspace=user_workspace.workspace,
        context=user_workspace.workspace,
    )

    assert CoreHandler().check_permissions(
        user_workspace_2.user,
        ListApplicationsWorkspaceOperationType.type,
        workspace=user_workspace_2.workspace,
        context=user_workspace.workspace,
    )

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        assert CoreHandler().check_permissions(
            user_workspace_2.user,
            UpdateWorkspaceOperationType.type,
            workspace=user_workspace_2.workspace,
            context=user_workspace_2.workspace,
        )

    with pytest.raises(PermissionDenied):
        assert CoreHandler().check_permissions(
            AnonymousUser(),
            ListApplicationsWorkspaceOperationType.type,
            workspace=user_workspace.workspace,
            context=user_workspace.workspace,
        )

    basic_permission_manager = permission_manager_type_registry.get("basic")
    original_check = basic_permission_manager.check_multiple_permissions
    basic_permission_manager.check_multiple_permissions = lambda *args, **kwargs: {}

    # should be refused by default if the basic permission manager doesn't answer.
    with pytest.raises(PermissionDenied):
        CoreHandler().check_permissions(
            user_workspace.user,
            ListApplicationsWorkspaceOperationType.type,
            workspace=user_workspace.workspace,
            context=user_workspace.workspace,
        )

    basic_permission_manager.check_multiple_permissions = original_check

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        assert CoreHandler().check_permissions(
            user_workspace_2.user,
            UpdateWorkspaceOperationType.type,
            workspace=user_workspace_2.workspace,
            context=user_workspace_2.workspace,
        )

    assert CoreHandler().check_permissions(
        user_workspace_3.user,
        UpdateWorkspaceOperationType.type,
        workspace=user_workspace_3.workspace,
        context=user_workspace_3.workspace,
    )

    with pytest.raises(PermissionDenied):
        assert CoreHandler().check_permissions(
            AnonymousUser(),
            ListApplicationsWorkspaceOperationType.type,
            workspace=user_workspace.workspace,
            context=user_workspace.workspace,
        )


@pytest.mark.django_db(transaction=True)
def test_workspace_member_permission_manager(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    database_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    database_2 = data_fixture.create_database_application(
        workspace=workspace_2, order=1
    )

    perm_manager = WorkspaceMemberOnlyPermissionManagerType()

    checks = [
        PermissionCheck(user, UpdateApplicationOperationType.type, database_1),
        PermissionCheck(user, ListApplicationsWorkspaceOperationType.type, workspace_1),
    ]

    result = perm_manager.check_multiple_permissions(checks, workspace_1)

    list_result = [
        (
            c.actor.username,
            c.operation_name,
            (
                result.get(c, None)
                if not isinstance(result.get(c, None), Exception)
                else False
            ),
        )
        for c in checks
    ]

    assert list_result == [
        ("test@test.nl", "application.update", None),
        ("test@test.nl", "workspace.list_applications", None),
    ]

    checks = [
        PermissionCheck(user, UpdateApplicationOperationType.type, database_2),
        PermissionCheck(user, ListApplicationsWorkspaceOperationType.type, workspace_2),
    ]

    result = perm_manager.check_multiple_permissions(checks, workspace_2)

    list_result = [
        (
            c.actor.username,
            c.operation_name,
            (
                result.get(c, None)
                if not isinstance(result.get(c, None), Exception)
                else False
            ),
        )
        for c in checks
    ]

    assert list_result == [
        ("test@test.nl", "application.update", False),
        ("test@test.nl", "workspace.list_applications", False),
    ]

    try:
        perm_manager.check_permissions(
            user, ListApplicationsWorkspaceOperationType.type, workspace_2, workspace_2
        )
    except Exception:  # noqa:W0718
        ...

    with django_assert_num_queries(0):
        filtered = perm_manager.filter_queryset(
            user,
            ListApplicationsWorkspaceOperationType.type,
            Database.objects.all(),
            workspace_2,
        )

    assert isinstance(filtered, tuple)
    assert len(filtered[0]) == 0


@pytest.mark.django_db
def test_check_multiple_permissions(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    user_4 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[(user_2, "MEMBER"), (user_3, "MEMBER")],
    )
    database = data_fixture.create_database_application(user=admin, workspace=workspace)

    checks = []
    result = CoreHandler().check_multiple_permissions(checks, workspace)

    assert result == {}

    checks = []
    for user in [admin, user_2, user_3, user_4, AnonymousUser()]:
        for type, scope in [
            (UpdateSettingsOperationType.type, None),
            (ListWorkspacesOperationType.type, workspace),
            (UpdateWorkspaceOperationType.type, workspace),
            (ListApplicationsWorkspaceOperationType.type, workspace),
            (ListTablesDatabaseTableOperationType.type, database),
        ]:
            checks.append(PermissionCheck(user, type, scope))

    perm_manager = CorePermissionManagerType()

    result = perm_manager.check_multiple_permissions(
        [c for c in checks if perm_manager.actor_is_supported(c.actor)], workspace
    )

    assert [result[c] if c in result else None for c in checks] == [
        None,
        True,
        None,
        None,
        None,
        None,
        True,
        None,
        None,
        None,
        None,
        True,
        None,
        None,
        None,
        None,
        True,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ]

    perm_manager = StaffOnlyPermissionManagerType()
    result = perm_manager.check_multiple_permissions(
        [c for c in checks if perm_manager.actor_is_supported(c.actor)], workspace
    )
    assert [
        (result[c] if result[c] is True else False) if c in result else None
        for c in checks
    ] == [
        True,
        None,
        None,
        None,
        None,
        False,
        None,
        None,
        None,
        None,
        False,
        None,
        None,
        None,
        None,
        False,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ]

    perm_manager = WorkspaceMemberOnlyPermissionManagerType()
    result = perm_manager.check_multiple_permissions(
        [c for c in checks if perm_manager.actor_is_supported(c.actor)], workspace
    )
    assert [
        (result[c] if result[c] is True else False) if c in result else None
        for c in checks
    ] == [
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        False,
        False,
        False,
        False,
        False,
        None,
        None,
        None,
        None,
        None,
    ]

    perm_manager = BasicPermissionManagerType()
    result = perm_manager.check_multiple_permissions(
        [c for c in checks if perm_manager.actor_is_supported(c.actor)], workspace
    )
    assert [
        (result[c] if result[c] is True else False) if c in result else None
        for c in checks
    ] == [
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        True,
        True,
        True,
        True,
        False,
        True,
        True,
        True,
        True,
        False,
        True,
        True,
        None,
        None,
        None,
        None,
        None,
    ]

    # All together
    result = CoreHandler().check_multiple_permissions(checks, workspace)

    permission_result = [result[check] for check in checks]

    assert permission_result == [
        True,
        True,
        True,
        True,
        True,
        False,
        True,
        False,
        True,
        True,
        False,
        True,
        False,
        True,
        True,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]


@pytest.mark.django_db
def test_get_permissions(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    user_4 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[(user_2, "ADMIN"), (user_3, "MEMBER")],
    )

    result = CoreHandler().get_permissions(admin)

    assert result == [
        {"name": "view_ownership", "permissions": {}},
        {"name": "core", "permissions": ["list_workspaces"]},
        {
            "name": "setting_operation",
            "permissions": {
                "staff_only_operations": [],
                "always_allowed_operations": ["create_workspace"],
            },
        },
        {
            "name": "staff",
            "permissions": {
                "staff_only_operations": ["settings.update"],
                "is_staff": True,
            },
        },
        {
            "name": "allow_if_template",
            "permissions": {
                "allowed_operations_on_templates": [
                    "workspace.read",
                    "workspace.list_applications",
                    "application.list_integrations",
                    "application.list_user_sources",
                    "application.user_source.login",
                    "database.table.field_rules.read_field_rules",
                    "database.list_tables",
                    "database.table.list_fields",
                    "database.table.list_rows",
                    "database.table.list_views",
                    "database.table.read_row",
                    "database.table.view.read",
                    "database.table.view.read_field_options",
                    "database.table.view.list_decoration",
                    "database.table.view.list_aggregations",
                    "database.table.view.read_aggregation",
                    "builder.list_pages",
                    "builder.page.list_elements",
                    "builder.page.list_workflow_actions",
                    "builder.page.data_source.dispatch",
                    "builder.page.list_data_sources",
                    "dashboard.widget.read",
                    "dashboard.list_widgets",
                    "dashboard.data_source.read",
                    "dashboard.list_data_sources",
                    "dashboard.data_source.dispatch",
                ],
                "workspace_template_ids": [],
            },
        },
        {"name": "member", "permissions": False},
    ]

    result = CoreHandler().get_permissions(admin, workspace)

    assert result == [
        {"name": "view_ownership", "permissions": {}},
        {"name": "core", "permissions": ["list_workspaces"]},
        {
            "name": "setting_operation",
            "permissions": {
                "staff_only_operations": [],
                "always_allowed_operations": ["create_workspace"],
            },
        },
        {
            "name": "staff",
            "permissions": {
                "staff_only_operations": ["settings.update"],
                "is_staff": True,
            },
        },
        {
            "name": "allow_if_template",
            "permissions": {
                "allowed_operations_on_templates": [
                    "workspace.read",
                    "workspace.list_applications",
                    "application.list_integrations",
                    "application.list_user_sources",
                    "application.user_source.login",
                    "database.table.field_rules.read_field_rules",
                    "database.list_tables",
                    "database.table.list_fields",
                    "database.table.list_rows",
                    "database.table.list_views",
                    "database.table.read_row",
                    "database.table.view.read",
                    "database.table.view.read_field_options",
                    "database.table.view.list_decoration",
                    "database.table.view.list_aggregations",
                    "database.table.view.read_aggregation",
                    "builder.list_pages",
                    "builder.page.list_elements",
                    "builder.page.list_workflow_actions",
                    "builder.page.data_source.dispatch",
                    "builder.page.list_data_sources",
                    "dashboard.widget.read",
                    "dashboard.list_widgets",
                    "dashboard.data_source.read",
                    "dashboard.list_data_sources",
                    "dashboard.data_source.dispatch",
                ],
                "workspace_template_ids": [],
            },
        },
        {
            "name": "basic",
            "permissions": {
                "admin_only_operations": [
                    "workspace.list_invitations",
                    "workspace.create_invitation",
                    "invitation.read",
                    "invitation.update",
                    "invitation.delete",
                    "workspace.list_workspace_users",
                    "workspace.update",
                    "workspace.delete",
                    "workspace_user.update",
                    "workspace_user.delete",
                ],
                "is_admin": True,
            },
        },
    ]

    result = CoreHandler().get_permissions(user_2)

    assert result == [
        {"name": "view_ownership", "permissions": {}},
        {"name": "core", "permissions": ["list_workspaces"]},
        {
            "name": "setting_operation",
            "permissions": {
                "staff_only_operations": [],
                "always_allowed_operations": ["create_workspace"],
            },
        },
        {
            "name": "staff",
            "permissions": {
                "staff_only_operations": ["settings.update"],
                "is_staff": False,
            },
        },
        {
            "name": "allow_if_template",
            "permissions": {
                "allowed_operations_on_templates": [
                    "workspace.read",
                    "workspace.list_applications",
                    "application.list_integrations",
                    "application.list_user_sources",
                    "application.user_source.login",
                    "database.table.field_rules.read_field_rules",
                    "database.list_tables",
                    "database.table.list_fields",
                    "database.table.list_rows",
                    "database.table.list_views",
                    "database.table.read_row",
                    "database.table.view.read",
                    "database.table.view.read_field_options",
                    "database.table.view.list_decoration",
                    "database.table.view.list_aggregations",
                    "database.table.view.read_aggregation",
                    "builder.list_pages",
                    "builder.page.list_elements",
                    "builder.page.list_workflow_actions",
                    "builder.page.data_source.dispatch",
                    "builder.page.list_data_sources",
                    "dashboard.widget.read",
                    "dashboard.list_widgets",
                    "dashboard.data_source.read",
                    "dashboard.list_data_sources",
                    "dashboard.data_source.dispatch",
                ],
                "workspace_template_ids": [],
            },
        },
        {"name": "member", "permissions": False},
    ]

    result = CoreHandler().get_permissions(user_2, workspace)

    assert result == [
        {"name": "view_ownership", "permissions": {}},
        {"name": "core", "permissions": ["list_workspaces"]},
        {
            "name": "setting_operation",
            "permissions": {
                "staff_only_operations": [],
                "always_allowed_operations": ["create_workspace"],
            },
        },
        {
            "name": "staff",
            "permissions": {
                "staff_only_operations": ["settings.update"],
                "is_staff": False,
            },
        },
        {
            "name": "allow_if_template",
            "permissions": {
                "allowed_operations_on_templates": [
                    "workspace.read",
                    "workspace.list_applications",
                    "application.list_integrations",
                    "application.list_user_sources",
                    "application.user_source.login",
                    "database.table.field_rules.read_field_rules",
                    "database.list_tables",
                    "database.table.list_fields",
                    "database.table.list_rows",
                    "database.table.list_views",
                    "database.table.read_row",
                    "database.table.view.read",
                    "database.table.view.read_field_options",
                    "database.table.view.list_decoration",
                    "database.table.view.list_aggregations",
                    "database.table.view.read_aggregation",
                    "builder.list_pages",
                    "builder.page.list_elements",
                    "builder.page.list_workflow_actions",
                    "builder.page.data_source.dispatch",
                    "builder.page.list_data_sources",
                    "dashboard.widget.read",
                    "dashboard.list_widgets",
                    "dashboard.data_source.read",
                    "dashboard.list_data_sources",
                    "dashboard.data_source.dispatch",
                ],
                "workspace_template_ids": [],
            },
        },
        {
            "name": "basic",
            "permissions": {
                "admin_only_operations": [
                    "workspace.list_invitations",
                    "workspace.create_invitation",
                    "invitation.read",
                    "invitation.update",
                    "invitation.delete",
                    "workspace.list_workspace_users",
                    "workspace.update",
                    "workspace.delete",
                    "workspace_user.update",
                    "workspace_user.delete",
                ],
                "is_admin": True,
            },
        },
    ]

    result = CoreHandler().get_permissions(user_3)

    assert result == [
        {"name": "view_ownership", "permissions": {}},
        {"name": "core", "permissions": ["list_workspaces"]},
        {
            "name": "setting_operation",
            "permissions": {
                "staff_only_operations": [],
                "always_allowed_operations": ["create_workspace"],
            },
        },
        {
            "name": "staff",
            "permissions": {
                "staff_only_operations": ["settings.update"],
                "is_staff": False,
            },
        },
        {
            "name": "allow_if_template",
            "permissions": {
                "allowed_operations_on_templates": [
                    "workspace.read",
                    "workspace.list_applications",
                    "application.list_integrations",
                    "application.list_user_sources",
                    "application.user_source.login",
                    "database.table.field_rules.read_field_rules",
                    "database.list_tables",
                    "database.table.list_fields",
                    "database.table.list_rows",
                    "database.table.list_views",
                    "database.table.read_row",
                    "database.table.view.read",
                    "database.table.view.read_field_options",
                    "database.table.view.list_decoration",
                    "database.table.view.list_aggregations",
                    "database.table.view.read_aggregation",
                    "builder.list_pages",
                    "builder.page.list_elements",
                    "builder.page.list_workflow_actions",
                    "builder.page.data_source.dispatch",
                    "builder.page.list_data_sources",
                    "dashboard.widget.read",
                    "dashboard.list_widgets",
                    "dashboard.data_source.read",
                    "dashboard.list_data_sources",
                    "dashboard.data_source.dispatch",
                ],
                "workspace_template_ids": [],
            },
        },
        {"name": "member", "permissions": False},
    ]

    result = CoreHandler().get_permissions(user_3, workspace)

    assert result == [
        {"name": "view_ownership", "permissions": {}},
        {"name": "core", "permissions": ["list_workspaces"]},
        {
            "name": "setting_operation",
            "permissions": {
                "staff_only_operations": [],
                "always_allowed_operations": ["create_workspace"],
            },
        },
        {
            "name": "staff",
            "permissions": {
                "staff_only_operations": ["settings.update"],
                "is_staff": False,
            },
        },
        {
            "name": "allow_if_template",
            "permissions": {
                "allowed_operations_on_templates": [
                    "workspace.read",
                    "workspace.list_applications",
                    "application.list_integrations",
                    "application.list_user_sources",
                    "application.user_source.login",
                    "database.table.field_rules.read_field_rules",
                    "database.list_tables",
                    "database.table.list_fields",
                    "database.table.list_rows",
                    "database.table.list_views",
                    "database.table.read_row",
                    "database.table.view.read",
                    "database.table.view.read_field_options",
                    "database.table.view.list_decoration",
                    "database.table.view.list_aggregations",
                    "database.table.view.read_aggregation",
                    "builder.list_pages",
                    "builder.page.list_elements",
                    "builder.page.list_workflow_actions",
                    "builder.page.data_source.dispatch",
                    "builder.page.list_data_sources",
                    "dashboard.widget.read",
                    "dashboard.list_widgets",
                    "dashboard.data_source.read",
                    "dashboard.list_data_sources",
                    "dashboard.data_source.dispatch",
                ],
                "workspace_template_ids": [],
            },
        },
        {
            "name": "basic",
            "permissions": {
                "admin_only_operations": [
                    "workspace.list_invitations",
                    "workspace.create_invitation",
                    "invitation.read",
                    "invitation.update",
                    "invitation.delete",
                    "workspace.list_workspace_users",
                    "workspace.update",
                    "workspace.delete",
                    "workspace_user.update",
                    "workspace_user.delete",
                ],
                "is_admin": False,
            },
        },
    ]

    result = CoreHandler().get_permissions(user_4, workspace)

    assert result == [
        {"name": "view_ownership", "permissions": {}},
        {"name": "core", "permissions": ["list_workspaces"]},
        {
            "name": "setting_operation",
            "permissions": {
                "staff_only_operations": [],
                "always_allowed_operations": ["create_workspace"],
            },
        },
        {
            "name": "staff",
            "permissions": {
                "staff_only_operations": ["settings.update"],
                "is_staff": False,
            },
        },
        {
            "name": "allow_if_template",
            "permissions": {
                "allowed_operations_on_templates": [
                    "workspace.read",
                    "workspace.list_applications",
                    "application.list_integrations",
                    "application.list_user_sources",
                    "application.user_source.login",
                    "database.table.field_rules.read_field_rules",
                    "database.list_tables",
                    "database.table.list_fields",
                    "database.table.list_rows",
                    "database.table.list_views",
                    "database.table.read_row",
                    "database.table.view.read",
                    "database.table.view.read_field_options",
                    "database.table.view.list_decoration",
                    "database.table.view.list_aggregations",
                    "database.table.view.read_aggregation",
                    "builder.list_pages",
                    "builder.page.list_elements",
                    "builder.page.list_workflow_actions",
                    "builder.page.data_source.dispatch",
                    "builder.page.list_data_sources",
                    "dashboard.widget.read",
                    "dashboard.list_widgets",
                    "dashboard.data_source.read",
                    "dashboard.list_data_sources",
                    "dashboard.data_source.dispatch",
                ],
                "workspace_template_ids": [],
            },
        },
        {"name": "member", "permissions": False},
    ]


@pytest.mark.django_db
@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=[
        "core",
        "setting_operation",
        "staff",
        "allow_if_template",
        "member",
        "token",
        "basic",
    ]
)
def test_allow_if_template_permission_manager(data_fixture):
    buser = data_fixture.create_user(username="Auth user")

    workspace_0 = data_fixture.create_workspace(user=buser)

    workspace_1 = data_fixture.create_workspace()
    application_1 = data_fixture.create_builder_application(workspace=workspace_1)
    integration_1 = data_fixture.create_integration_with_first_type(
        application=application_1
    )
    user_source_1 = data_fixture.create_user_source_with_first_type(
        application=application_1
    )

    workspace_2 = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace_2)
    application_2 = data_fixture.create_builder_application(workspace=workspace_2)
    integration_2 = data_fixture.create_integration_with_first_type(
        application=application_2
    )
    user_source_2 = data_fixture.create_user_source_with_first_type(
        application=application_2
    )

    template = [workspace_2, application_2, integration_2, user_source_2]

    checks = []
    for user in [
        buser,
        AnonymousUser(),
    ]:
        for perm_type, scope in [
            (ListApplicationsWorkspaceOperationType.type, workspace_1),
            (ListIntegrationsApplicationOperationType.type, application_1),
            (ListUserSourcesApplicationOperationType.type, application_1),
            (LoginUserSourceOperationType.type, user_source_1),
            (CreateApplicationsWorkspaceOperationType.type, workspace_1),
            (UpdateIntegrationOperationType.type, integration_1),
            (UpdateUserSourceOperationType.type, user_source_1),
        ]:
            checks.append(PermissionCheck(user, perm_type, scope))

    result_1 = CoreHandler().check_multiple_permissions(checks, workspace_1)

    list_result_1 = [
        (
            c.actor.username or "Anonymous",
            c.operation_name,
            "template" if c.context in template else "Not a template",
            result_1.get(c, None),
        )
        for c in checks
    ]

    checks = []
    for user in [
        buser,
        AnonymousUser(),
    ]:
        for perm_type, scope in [
            (ListApplicationsWorkspaceOperationType.type, workspace_2),
            (ListIntegrationsApplicationOperationType.type, application_2),
            (ListUserSourcesApplicationOperationType.type, application_2),
            (LoginUserSourceOperationType.type, user_source_2),
            (CreateApplicationsWorkspaceOperationType.type, workspace_2),
            (UpdateIntegrationOperationType.type, integration_2),
            (UpdateUserSourceOperationType.type, user_source_2),
        ]:
            checks.append(PermissionCheck(user, perm_type, scope))

    result_2 = CoreHandler().check_multiple_permissions(checks, workspace_2)

    list_result_2 = [
        (
            c.actor.username or "Anonymous",
            c.operation_name,
            "template" if c.context in template else "Not a template",
            result_2.get(c, None),
        )
        for c in checks
    ]

    list_result = list_result_1 + list_result_2

    assert list_result == [
        ("Auth user", "workspace.list_applications", "Not a template", False),
        ("Auth user", "application.list_integrations", "Not a template", False),
        ("Auth user", "application.list_user_sources", "Not a template", False),
        ("Auth user", "application.user_source.login", "Not a template", False),
        ("Auth user", "workspace.create_application", "Not a template", False),
        ("Auth user", "application.integration.update", "Not a template", False),
        ("Auth user", "application.user_source.update", "Not a template", False),
        ("Anonymous", "workspace.list_applications", "Not a template", False),
        ("Anonymous", "application.list_integrations", "Not a template", False),
        ("Anonymous", "application.list_user_sources", "Not a template", False),
        ("Anonymous", "application.user_source.login", "Not a template", False),
        ("Anonymous", "workspace.create_application", "Not a template", False),
        ("Anonymous", "application.integration.update", "Not a template", False),
        ("Anonymous", "application.user_source.update", "Not a template", False),
        ("Auth user", "workspace.list_applications", "template", True),
        ("Auth user", "application.list_integrations", "template", True),
        ("Auth user", "application.list_user_sources", "template", True),
        ("Auth user", "application.user_source.login", "template", True),
        ("Auth user", "workspace.create_application", "template", False),
        ("Auth user", "application.integration.update", "template", False),
        ("Auth user", "application.user_source.update", "template", False),
        ("Anonymous", "workspace.list_applications", "template", True),
        ("Anonymous", "application.list_integrations", "template", True),
        ("Anonymous", "application.list_user_sources", "template", True),
        ("Anonymous", "application.user_source.login", "template", True),
        ("Anonymous", "workspace.create_application", "template", False),
        ("Anonymous", "application.integration.update", "template", False),
        ("Anonymous", "application.user_source.update", "template", False),
    ]


@pytest.mark.django_db
@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=[
        "core",
        "setting_operation",
        "staff",
        "allow_if_template",
        "member",
        "token",
        "basic",
    ]
)
def test_allow_if_template_permission_manager_filter_queryset(data_fixture):
    user = data_fixture.create_user(username="Auth user")

    workspace_0 = data_fixture.create_workspace(user=user)

    workspace_1 = data_fixture.create_workspace()
    application_1 = data_fixture.create_builder_application(workspace=workspace_1)
    integration_1 = data_fixture.create_integration_with_first_type(
        application=application_1
    )
    user_source_1 = data_fixture.create_user_source_with_first_type(
        application=application_1
    )

    workspace_2 = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace_2)
    application_2 = data_fixture.create_builder_application(workspace=workspace_2)
    integration_2 = data_fixture.create_integration_with_first_type(
        application=application_2
    )
    user_source_2 = data_fixture.create_user_source_with_first_type(
        application=application_2
    )

    tests_w1 = [
        (
            ListApplicationsWorkspaceOperationType.type,
            workspace_1.application_set.all(),
        ),
        (
            ListIntegrationsApplicationOperationType.type,
            Integration.objects.filter(application__workspace=workspace_1),
        ),
        (
            ListUserSourcesApplicationOperationType.type,
            UserSource.objects.filter(application__workspace=workspace_1),
        ),
    ]

    for operation_name, queryset in tests_w1:
        assert (
            sorted(
                [
                    a.id
                    for a in CoreHandler().filter_queryset(
                        user,
                        operation_name,
                        queryset,
                        workspace=workspace_1,
                    )
                ]
            )
            == []
        )

    tests_w1 = [
        (
            ListApplicationsWorkspaceOperationType.type,
            workspace_2.application_set.all(),
            [application_2.id],
        ),
        (
            ListIntegrationsApplicationOperationType.type,
            Integration.objects.filter(application__workspace=workspace_2),
            [integration_2.id],
        ),
        (
            ListUserSourcesApplicationOperationType.type,
            UserSource.objects.filter(application__workspace=workspace_2),
            [user_source_2.id],
        ),
    ]

    for operation_name, queryset, expected in tests_w1:
        assert (
            sorted(
                [
                    a.id
                    for a in CoreHandler().filter_queryset(
                        user,
                        operation_name,
                        queryset,
                        workspace=workspace_2,
                    )
                ]
            )
            == expected
        ), operation_name


@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=[
        "core",
        "setting_operation",
        "staff",
        "allow_if_template",
        "member",
        "token",
        "basic",
    ],
)
def test_allow_if_template_permission_manager_query_count(data_fixture):
    buser = data_fixture.create_user(username="Auth user")

    workspace_1 = data_fixture.create_workspace(user=buser)
    application_1 = data_fixture.create_builder_application(workspace=workspace_1)

    integration_1 = data_fixture.create_integration_with_first_type(
        application=application_1
    )
    # Make sure settings exists, otherwise the first time they will be created and
    # the query count will be off.
    CoreHandler().get_settings()

    with CaptureQueriesContext(connection) as query_for_template:
        CoreHandler().check_permissions(
            buser,
            ListIntegrationsApplicationOperationType.type,
            context=application_1,
            workspace=workspace_1,
        )

    with CaptureQueriesContext(
        connection
    ) as query_not_for_template, local_cache.context():
        CoreHandler().check_permissions(
            buser,
            UpdateIntegrationOperationType.type,
            context=integration_1,
            workspace=workspace_1,
        )

    # We should have one more query when we query a template authorized permission
    assert len(query_not_for_template.captured_queries) + 1 == len(
        query_for_template.captured_queries
    )


@pytest.mark.django_db
def test_all_operations_are_registered():
    def get_all_subclasses(cls):
        all_subclasses = []

        for subclass in cls.__subclasses__():
            if not inspect.isabstract(subclass):
                all_subclasses.append(subclass)
            all_subclasses.extend(get_all_subclasses(subclass))

        return all_subclasses

    funcs = operation_type_registry.get_all()
    registered_operation_types = {f.type for f in funcs}
    all_operation_types = {
        t.type
        for t in get_all_subclasses(OperationType)
        if hasattr(t, "type") and t.type is not None
    }
    assert (
        all_operation_types == registered_operation_types
    ), "Please make sure the following operation " "types are added to the registry: " + str(
        all_operation_types.difference(registered_operation_types)
    ) + " or somehow the following operations are registered but not subclasses?: " + str(
        registered_operation_types.difference(all_operation_types)
    )


@pytest.mark.django_db
def test_all_scope_types_are_registered():
    def get_all_subclasses(cls):
        all_subclasses = []

        for subclass in cls.__subclasses__():
            if not inspect.isabstract(subclass):
                all_subclasses.append(subclass)
            all_subclasses.extend(get_all_subclasses(subclass))

        return all_subclasses

    funcs = object_scope_type_registry.get_all()
    registered_operation_types = {f.type for f in funcs}
    all_operation_types = {
        t.type for t in get_all_subclasses(ObjectScopeType) if hasattr(t, "type")
    }
    assert (
        all_operation_types == registered_operation_types
    ), "Please make sure the following operation " "types are added to the registry: " + str(
        all_operation_types.difference(registered_operation_types)
    ) + " or somehow the following operations are registered but not subclasses?: " + str(
        registered_operation_types.difference(all_operation_types)
    )


@pytest.mark.django_db
def test_all_scope_types_referenced_by_operations_are_registered():
    def get_all_subclasses(cls):
        all_subclasses = []

        for subclass in cls.__subclasses__():
            if not inspect.isabstract(subclass):
                all_subclasses.append(subclass)
            all_subclasses.extend(get_all_subclasses(subclass))

        return all_subclasses

    funcs = object_scope_type_registry.get_all()
    object_scope_types = {f.type for f in funcs}
    all_op_context_types = {
        t.context_scope_name for t in get_all_subclasses(OperationType)
    }
    assert (
        all_op_context_types == object_scope_types
    ), "Please make sure the following object_scope_types exist and are added to the " "registry: " + str(
        all_op_context_types.difference(object_scope_types)
    ) + " or somehow the following context types are registered but not subclasses?: " + str(
        object_scope_types.difference(all_op_context_types)
    )


@pytest.mark.django_db
def test_all_scope_types_query_methods():
    all_scope_type = object_scope_type_registry.get_all()

    for scope_type in all_scope_type:
        if scope_type.type == "core":
            continue

        assert isinstance(scope_type.get_base_queryset(), QuerySet)
        assert isinstance(scope_type.get_enhanced_queryset(), QuerySet)

        for parent in scope_type.get_parent_scopes():
            assert isinstance(scope_type.get_filter_for_scope_type(parent, []), Q)
