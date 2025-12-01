from django.db import IntegrityError, connection, reset_queries
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest
from tqdm import tqdm

from baserow.contrib.database.fields.operations import (
    ReadFieldOperationType,
    SubmitAnonymousFieldValuesOperationType,
    UpdateFieldOperationType,
    WriteFieldValuesOperationType,
)
from baserow.contrib.database.models import Database
from baserow.contrib.database.operations import (
    CreateTableDatabaseTableOperationType,
    ListTablesDatabaseTableOperationType,
)
from baserow.contrib.database.rows.operations import (
    DeleteDatabaseRowOperationType,
    ReadDatabaseRowOperationType,
    UpdateDatabaseRowOperationType,
)
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    CreateRowDatabaseTableOperationType,
    DeleteDatabaseTableOperationType,
    ListRowsDatabaseTableOperationType,
    ReadDatabaseTableOperationType,
    UpdateDatabaseTableOperationType,
)
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.models import Application
from baserow.core.notifications.operations import (
    ClearNotificationsOperationType,
    ListNotificationsOperationType,
    MarkNotificationAsReadOperationType,
)
from baserow.core.operations import (
    CreateWorkspaceOperationType,
    DeleteApplicationOperationType,
    DeleteWorkspaceOperationType,
    ListApplicationsWorkspaceOperationType,
    ListWorkspacesOperationType,
    ReadApplicationOperationType,
    ReadWorkspaceOperationType,
    UpdateApplicationOperationType,
    UpdateSettingsOperationType,
    UpdateWorkspaceOperationType,
)
from baserow.core.registries import operation_type_registry
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.types import PermissionCheck
from baserow.core.utils import Progress
from baserow_enterprise.role.default_roles import default_roles
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.role.permission_manager import RolePermissionManagerType


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def _populate_test_data(data_fixture, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = data_fixture.create_user(email="admin@test.net")
    builder = data_fixture.create_user(email="builder@test.net")
    editor = data_fixture.create_user(email="editor@test.net")
    viewer = data_fixture.create_user(email="viewer@test.net")
    viewer_plus = data_fixture.create_user(email="viewer_plus@test.net")
    builder_less = data_fixture.create_user(email="builder_less@test.net")
    no_access = data_fixture.create_user(email="no_access@test.net")
    another_admin = data_fixture.create_user(email="another_admin@test.net")

    workspace_1 = data_fixture.create_workspace(
        user=admin,
        members=[builder, viewer, editor, viewer_plus, builder_less, no_access],
    )
    workspace_2 = data_fixture.create_workspace(
        user=another_admin,
        custom_permissions=[
            (admin, "NO_ACCESS"),
            (builder, "NO_ACCESS"),
            (viewer, "NO_ACCESS"),
            (editor, "NO_ACCESS"),
            (viewer_plus, "NO_ACCESS"),
            (builder_less, "NO_ACCESS"),
            (no_access, "NO_ACCESS"),
        ],
    )

    database_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    database_2 = data_fixture.create_database_application(
        workspace=workspace_2, order=2
    )
    database_3 = data_fixture.create_database_application(
        workspace=workspace_2, order=3
    )

    table_1_1, _, _ = data_fixture.build_table(
        columns=[("number", "number"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=1,
    )
    table_1_2, _, _ = data_fixture.build_table(
        columns=[("number", "text"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=2,
    )

    table_2_1, _, _ = data_fixture.build_table(
        columns=[("number", "text"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_2,
        order=1,
    )
    table_2_2, _, _ = data_fixture.build_table(
        columns=[("number", "text"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_2,
        order=2,
    )

    role_builder = Role.objects.get(uid="BUILDER")
    role_viewer = Role.objects.get(uid="VIEWER")
    role_editor = Role.objects.get(uid="EDITOR")
    role_no_access = Role.objects.get(uid="NO_ACCESS")

    # Workspace level assignments
    RoleAssignmentHandler().assign_role(builder, workspace_1, role=role_builder)
    RoleAssignmentHandler().assign_role(viewer, workspace_1, role=role_viewer)
    RoleAssignmentHandler().assign_role(editor, workspace_1, role=role_editor)
    RoleAssignmentHandler().assign_role(viewer_plus, workspace_1, role=role_viewer)
    RoleAssignmentHandler().assign_role(builder_less, workspace_1, role=role_builder)
    RoleAssignmentHandler().assign_role(no_access, workspace_1, role=role_no_access)

    # Table level assignments
    RoleAssignmentHandler().assign_role(
        builder, workspace_2, role=role_builder, scope=table_2_1
    )
    RoleAssignmentHandler().assign_role(
        viewer_plus, workspace_1, role=role_builder, scope=table_1_1
    )
    RoleAssignmentHandler().assign_role(
        builder_less, workspace_1, role=role_viewer, scope=table_1_1
    )

    return (
        admin,
        builder,
        editor,
        viewer,
        viewer_plus,
        builder_less,
        no_access,
        workspace_1,
        workspace_2,
        database_1,
        database_2,
        database_3,
        table_1_1,
        table_1_2,
        table_2_1,
        table_2_2,
    )


@pytest.mark.django_db(transaction=True)
@override_settings(
    PERMISSION_MANAGERS=["core", "staff", "member", "role", "basic"],
)
def test_check_permissions(data_fixture, enterprise_data_fixture):
    (
        admin,
        builder,
        editor,
        viewer,
        viewer_plus,
        builder_less,
        no_access,
        workspace_1,
        workspace_2,
        database_1,
        database_2,
        database_3,
        table_1_1,
        table_1_2,
        table_2_1,
        table_2_2,
    ) = _populate_test_data(data_fixture, enterprise_data_fixture)

    perm_manager = RolePermissionManagerType()

    def check_perms(user, test_list):
        for permission, context, result in test_list:
            if isinstance(context, Table):
                workspace = context.database.workspace
            elif isinstance(context, Database):
                workspace = context.workspace
            else:
                workspace = context

            if result:
                try:
                    assert perm_manager.check_permissions(
                        user, permission.type, workspace=workspace, context=context
                    ), f"User {user} should have permission {permission.type} on context {context}"
                except PermissionException:
                    print(
                        f"User {user} should have permission {permission.type} on context {context}"
                    )
                    raise
                except Exception:
                    print(
                        f"Fails to check permission {permission.type} for user {user} "
                        f"on context {context}"
                    )
                    raise

            else:
                with pytest.raises(PermissionException):
                    perm_manager.check_permissions(
                        user, permission.type, workspace=workspace, context=context
                    )
                    print(
                        f"User {user} shouldn't have permission {permission.type} on context {context}"
                    )

    no_access_tests = [
        # Workspace 1
        (ReadWorkspaceOperationType, workspace_1, False),
        (UpdateWorkspaceOperationType, workspace_1, False),
        (DeleteWorkspaceOperationType, workspace_1, False),
        # Workspace 2
        (ReadWorkspaceOperationType, workspace_2, False),
        # database1
        (ReadApplicationOperationType, workspace_1, False),
        (ReadDatabaseTableOperationType, table_1_1, False),
        (UpdateDatabaseTableOperationType, table_1_1, False),
        (DeleteDatabaseTableOperationType, table_1_1, False),
        (ReadDatabaseTableOperationType, table_1_2, False),
        (UpdateDatabaseTableOperationType, table_1_2, False),
        (DeleteDatabaseTableOperationType, table_1_2, False),
        # Table_2_1
        (ListTablesDatabaseTableOperationType, database_2, False),
        (CreateTableDatabaseTableOperationType, database_2, False),
        (ReadDatabaseTableOperationType, table_2_1, False),
        (UpdateDatabaseTableOperationType, table_2_1, False),
        (DeleteDatabaseTableOperationType, table_2_1, False),
        # Table_2_2
        (ReadDatabaseTableOperationType, table_2_2, False),
        (UpdateDatabaseTableOperationType, table_2_2, False),
        (DeleteDatabaseTableOperationType, table_2_2, False),
        # Table_1_1 rows
        (ListRowsDatabaseTableOperationType, table_1_1, False),
        (CreateRowDatabaseTableOperationType, table_1_1, False),
        (ReadDatabaseRowOperationType, table_1_1, False),
        (UpdateDatabaseRowOperationType, table_1_1, False),
        (DeleteDatabaseRowOperationType, table_1_1, False),
    ]

    check_perms(no_access, no_access_tests)

    print("ADMIN")

    admin_tests = [
        # Workspace 1
        (ReadWorkspaceOperationType, workspace_1, True),
        (UpdateWorkspaceOperationType, workspace_1, True),
        (DeleteWorkspaceOperationType, workspace_1, True),
        # Workspace 2
        (ReadWorkspaceOperationType, workspace_2, False),
        (UpdateWorkspaceOperationType, workspace_2, False),
        (DeleteWorkspaceOperationType, workspace_2, False),
        # Database_1
        (ReadApplicationOperationType, workspace_1, True),
        (CreateTableDatabaseTableOperationType, database_1, True),
        (ListTablesDatabaseTableOperationType, database_1, True),
        # Table_1_1
        (ReadDatabaseTableOperationType, table_1_1, True),
        (UpdateDatabaseTableOperationType, table_1_1, True),
        (DeleteDatabaseTableOperationType, table_1_1, True),
        (ListRowsDatabaseTableOperationType, table_1_1, True),
        (CreateRowDatabaseTableOperationType, table_1_1, True),
        # Table_1_2
        (ReadDatabaseTableOperationType, table_1_2, True),
        (UpdateDatabaseTableOperationType, table_1_2, True),
        (DeleteDatabaseTableOperationType, table_1_2, True),
        (ListRowsDatabaseTableOperationType, table_1_2, True),
        (CreateRowDatabaseTableOperationType, table_1_2, True),
        # Database_2
        (ReadApplicationOperationType, workspace_2, False),
        (CreateTableDatabaseTableOperationType, database_2, False),
        (ListTablesDatabaseTableOperationType, database_2, False),
        # Table_2_1
        (ReadDatabaseTableOperationType, table_2_1, False),
        (UpdateDatabaseTableOperationType, table_2_1, False),
        (DeleteDatabaseTableOperationType, table_2_1, False),
        (ListRowsDatabaseTableOperationType, table_2_1, False),
        (CreateRowDatabaseTableOperationType, table_2_1, False),
        # Table_2_2
        (ReadDatabaseTableOperationType, table_2_2, False),
        (UpdateDatabaseTableOperationType, table_2_2, False),
        (DeleteDatabaseTableOperationType, table_2_2, False),
        (ListRowsDatabaseTableOperationType, table_2_2, False),
        (CreateRowDatabaseTableOperationType, table_2_2, False),
        # Table_1_1 rows
        (ReadDatabaseRowOperationType, table_1_1, True),
        (UpdateDatabaseRowOperationType, table_1_1, True),
        (DeleteDatabaseRowOperationType, table_1_1, True),
        # Table_1_2 rows
        (ReadDatabaseRowOperationType, table_1_2, True),
        (UpdateDatabaseRowOperationType, table_1_2, True),
        (DeleteDatabaseRowOperationType, table_1_2, True),
        # Table_2_1 rows
        (ReadDatabaseRowOperationType, table_2_1, False),
        (UpdateDatabaseRowOperationType, table_2_1, False),
        (DeleteDatabaseRowOperationType, table_2_1, False),
        # Table_2_2 rows
        (ReadDatabaseRowOperationType, table_2_2, False),
        (UpdateDatabaseRowOperationType, table_2_2, False),
        (DeleteDatabaseRowOperationType, table_2_2, False),
    ]

    check_perms(admin, admin_tests)

    print("BUILDER")

    builder_tests = [
        # Workspace 1
        (ReadWorkspaceOperationType, workspace_1, True),
        (UpdateWorkspaceOperationType, workspace_1, False),
        (DeleteWorkspaceOperationType, workspace_1, False),
        (ListApplicationsWorkspaceOperationType, workspace_1, True),
        # Workspace 2
        (ReadWorkspaceOperationType, workspace_2, True),
        (UpdateWorkspaceOperationType, workspace_2, False),
        (DeleteWorkspaceOperationType, workspace_2, False),
        (ListApplicationsWorkspaceOperationType, workspace_2, True),
        # Database_1
        (ReadApplicationOperationType, workspace_1, True),
        (CreateTableDatabaseTableOperationType, database_1, True),
        (ListTablesDatabaseTableOperationType, database_1, True),
        # Table_1_1
        (ReadDatabaseTableOperationType, table_1_1, True),
        (UpdateDatabaseTableOperationType, table_1_1, True),
        (DeleteDatabaseTableOperationType, table_1_1, True),
        (ListRowsDatabaseTableOperationType, table_1_1, True),
        (CreateRowDatabaseTableOperationType, table_1_1, True),
        # Table_1_2
        (ReadDatabaseTableOperationType, table_1_2, True),
        (UpdateDatabaseTableOperationType, table_1_2, True),
        (DeleteDatabaseTableOperationType, table_1_2, True),
        (ListRowsDatabaseTableOperationType, table_1_2, True),
        (CreateRowDatabaseTableOperationType, table_1_2, True),
        # Database_2
        (ReadApplicationOperationType, workspace_2, True),
        (CreateTableDatabaseTableOperationType, database_2, False),
        (ListTablesDatabaseTableOperationType, database_2, True),
        # Table_2_1
        (ReadDatabaseTableOperationType, table_2_1, True),
        (UpdateDatabaseTableOperationType, table_2_1, True),
        (DeleteDatabaseTableOperationType, table_2_1, True),
        (ListRowsDatabaseTableOperationType, table_2_1, True),
        (CreateRowDatabaseTableOperationType, table_2_1, True),
        # Table_2_2
        (ReadDatabaseTableOperationType, table_2_2, False),
        (UpdateDatabaseTableOperationType, table_2_2, False),
        (DeleteDatabaseTableOperationType, table_2_2, False),
        (ListRowsDatabaseTableOperationType, table_2_2, False),
        (CreateRowDatabaseTableOperationType, table_2_2, False),
        # Table_1_1 rows
        (ReadDatabaseRowOperationType, table_1_1, True),
        (UpdateDatabaseRowOperationType, table_1_1, True),
        (DeleteDatabaseRowOperationType, table_1_1, True),
        # Table_1_2 rows
        (ReadDatabaseRowOperationType, table_1_2, True),
        (UpdateDatabaseRowOperationType, table_1_2, True),
        (DeleteDatabaseRowOperationType, table_1_2, True),
        # Table_2_1 rows
        (ReadDatabaseRowOperationType, table_2_1, True),
        (UpdateDatabaseRowOperationType, table_2_1, True),
        (DeleteDatabaseRowOperationType, table_2_1, True),
        # Table_2_2 rows
        (ReadDatabaseRowOperationType, table_2_2, False),
        (UpdateDatabaseRowOperationType, table_2_2, False),
        (DeleteDatabaseRowOperationType, table_2_2, False),
    ]

    check_perms(builder, builder_tests)

    print("EDITOR")

    editor_tests = [
        # Workspace 1
        (ReadWorkspaceOperationType, workspace_1, True),
        (UpdateWorkspaceOperationType, workspace_1, False),
        (DeleteWorkspaceOperationType, workspace_1, False),
        # Workspace 2
        (ReadWorkspaceOperationType, workspace_2, False),
        (UpdateWorkspaceOperationType, workspace_2, False),
        (DeleteWorkspaceOperationType, workspace_2, False),
        # Database_1
        (ReadApplicationOperationType, workspace_1, True),
        (CreateTableDatabaseTableOperationType, database_1, False),
        (ListTablesDatabaseTableOperationType, database_1, True),
        # Table_1_1
        (ReadDatabaseTableOperationType, table_1_1, True),
        (UpdateDatabaseTableOperationType, table_1_1, False),
        (DeleteDatabaseTableOperationType, table_1_1, False),
        (ListRowsDatabaseTableOperationType, table_1_1, True),
        (CreateRowDatabaseTableOperationType, table_1_1, True),
        # Table_1_2
        (ReadDatabaseTableOperationType, table_1_2, True),
        (UpdateDatabaseTableOperationType, table_1_2, False),
        (DeleteDatabaseTableOperationType, table_1_2, False),
        (ListRowsDatabaseTableOperationType, table_1_2, True),
        (CreateRowDatabaseTableOperationType, table_1_2, True),
        # Database_2
        (ReadApplicationOperationType, workspace_2, False),
        (CreateTableDatabaseTableOperationType, database_2, False),
        (ListTablesDatabaseTableOperationType, database_2, False),
        # Table_2_1
        (ReadDatabaseTableOperationType, table_2_1, False),
        (UpdateDatabaseTableOperationType, table_2_1, False),
        (DeleteDatabaseTableOperationType, table_2_1, False),
        (ListRowsDatabaseTableOperationType, table_2_1, False),
        (CreateRowDatabaseTableOperationType, table_2_1, False),
        # Table_2_2
        (ReadDatabaseTableOperationType, table_2_2, False),
        (UpdateDatabaseTableOperationType, table_2_2, False),
        (DeleteDatabaseTableOperationType, table_2_2, False),
        (ListRowsDatabaseTableOperationType, table_2_2, False),
        (CreateRowDatabaseTableOperationType, table_2_2, False),
        # Table_1_1 rows
        (ReadDatabaseRowOperationType, table_1_1, True),
        (UpdateDatabaseRowOperationType, table_1_1, True),
        (DeleteDatabaseRowOperationType, table_1_1, True),
        # Table_1_2 rows
        (ReadDatabaseRowOperationType, table_1_2, True),
        (UpdateDatabaseRowOperationType, table_1_2, True),
        (DeleteDatabaseRowOperationType, table_1_2, True),
        # Table_2_1 rows
        (ReadDatabaseRowOperationType, table_2_1, False),
        (UpdateDatabaseRowOperationType, table_2_1, False),
        (DeleteDatabaseRowOperationType, table_2_1, False),
        # Table_2_2 rows
        (ReadDatabaseRowOperationType, table_2_2, False),
        (UpdateDatabaseRowOperationType, table_2_2, False),
        (DeleteDatabaseRowOperationType, table_2_2, False),
    ]

    check_perms(editor, editor_tests)

    print("VIEWER")

    viewer_tests = [
        # Workspace 1
        (ReadWorkspaceOperationType, workspace_1, True),
        (UpdateWorkspaceOperationType, workspace_1, False),
        (DeleteWorkspaceOperationType, workspace_1, False),
        # Workspace 2
        (ReadWorkspaceOperationType, workspace_2, False),
        (UpdateWorkspaceOperationType, workspace_2, False),
        (DeleteWorkspaceOperationType, workspace_2, False),
        # Database_1
        (ReadApplicationOperationType, workspace_1, True),
        (CreateTableDatabaseTableOperationType, database_1, False),
        (ListTablesDatabaseTableOperationType, database_1, True),
        # Table_1_1
        (ReadDatabaseTableOperationType, table_1_1, True),
        (UpdateDatabaseTableOperationType, table_1_1, False),
        (DeleteDatabaseTableOperationType, table_1_1, False),
        (ListRowsDatabaseTableOperationType, table_1_1, True),
        (CreateRowDatabaseTableOperationType, table_1_1, False),
        # Table_1_2
        (ReadDatabaseTableOperationType, table_1_2, True),
        (UpdateDatabaseTableOperationType, table_1_2, False),
        (DeleteDatabaseTableOperationType, table_1_2, False),
        (ListRowsDatabaseTableOperationType, table_1_2, True),
        (CreateRowDatabaseTableOperationType, table_1_2, False),
        # Database_2
        (ReadApplicationOperationType, workspace_2, False),
        (CreateTableDatabaseTableOperationType, database_2, False),
        (ListTablesDatabaseTableOperationType, database_2, False),
        # Table_2_1
        (ReadDatabaseTableOperationType, table_2_1, False),
        (UpdateDatabaseTableOperationType, table_2_1, False),
        (DeleteDatabaseTableOperationType, table_2_1, False),
        (ListRowsDatabaseTableOperationType, table_2_1, False),
        (CreateRowDatabaseTableOperationType, table_2_1, False),
        # Table_2_2
        (ReadDatabaseTableOperationType, table_2_2, False),
        (UpdateDatabaseTableOperationType, table_2_2, False),
        (DeleteDatabaseTableOperationType, table_2_2, False),
        (ListRowsDatabaseTableOperationType, table_2_2, False),
        (CreateRowDatabaseTableOperationType, table_2_2, False),
        # Table_1_1 rows
        (ReadDatabaseRowOperationType, table_1_1, True),
        (UpdateDatabaseRowOperationType, table_1_1, False),
        (DeleteDatabaseRowOperationType, table_1_1, False),
        # Table_1_2 rows
        (ReadDatabaseRowOperationType, table_1_2, True),
        (UpdateDatabaseRowOperationType, table_1_2, False),
        (DeleteDatabaseRowOperationType, table_1_2, False),
        # Table_2_1 rows
        (ReadDatabaseRowOperationType, table_2_1, False),
        (UpdateDatabaseRowOperationType, table_2_1, False),
        (DeleteDatabaseRowOperationType, table_2_1, False),
        # Table_2_2 rows
        (ReadDatabaseRowOperationType, table_2_2, False),
        (UpdateDatabaseRowOperationType, table_2_2, False),
        (DeleteDatabaseRowOperationType, table_2_2, False),
    ]

    check_perms(viewer, viewer_tests)

    print("viewer+")

    viewer_plus_tests = [
        # Workspace 1
        (ReadWorkspaceOperationType, workspace_1, True),
        (UpdateWorkspaceOperationType, workspace_1, False),
        (DeleteWorkspaceOperationType, workspace_1, False),
        # Workspace 2
        (ReadWorkspaceOperationType, workspace_2, False),
        (UpdateWorkspaceOperationType, workspace_2, False),
        (DeleteWorkspaceOperationType, workspace_2, False),
        # Database_1
        (ReadApplicationOperationType, workspace_1, True),
        (CreateTableDatabaseTableOperationType, database_1, False),
        (ListTablesDatabaseTableOperationType, database_1, True),
        # Table_1_1
        (ReadDatabaseTableOperationType, table_1_1, True),
        (UpdateDatabaseTableOperationType, table_1_1, True),
        (DeleteDatabaseTableOperationType, table_1_1, True),
        (ListRowsDatabaseTableOperationType, table_1_1, True),
        (CreateRowDatabaseTableOperationType, table_1_1, True),
        # Table_1_2
        (ReadDatabaseTableOperationType, table_1_2, True),
        (UpdateDatabaseTableOperationType, table_1_2, False),
        (DeleteDatabaseTableOperationType, table_1_2, False),
        (ListRowsDatabaseTableOperationType, table_1_2, True),
        (CreateRowDatabaseTableOperationType, table_1_2, False),
        # Database_2
        (ReadApplicationOperationType, workspace_2, False),
        (CreateTableDatabaseTableOperationType, database_2, False),
        (ListTablesDatabaseTableOperationType, database_2, False),
        # Table_2_1
        (ReadDatabaseTableOperationType, table_2_1, False),
        (UpdateDatabaseTableOperationType, table_2_1, False),
        (DeleteDatabaseTableOperationType, table_2_1, False),
        (ListRowsDatabaseTableOperationType, table_2_1, False),
        (CreateRowDatabaseTableOperationType, table_2_1, False),
        # Table_2_2
        (ReadDatabaseTableOperationType, table_2_2, False),
        (UpdateDatabaseTableOperationType, table_2_2, False),
        (DeleteDatabaseTableOperationType, table_2_2, False),
        (ListRowsDatabaseTableOperationType, table_2_2, False),
        (CreateRowDatabaseTableOperationType, table_2_2, False),
        # Table_1_1 rows
        (ReadDatabaseRowOperationType, table_1_1, True),
        (UpdateDatabaseRowOperationType, table_1_1, True),
        (DeleteDatabaseRowOperationType, table_1_1, True),
        # Table_1_2 rows
        (ReadDatabaseRowOperationType, table_1_2, True),
        (UpdateDatabaseRowOperationType, table_1_2, False),
        (DeleteDatabaseRowOperationType, table_1_2, False),
        # Table_2_1 rows
        (ReadDatabaseRowOperationType, table_2_1, False),
        (UpdateDatabaseRowOperationType, table_2_1, False),
        (DeleteDatabaseRowOperationType, table_2_1, False),
        # Table_2_2 rows
        (ReadDatabaseRowOperationType, table_2_2, False),
        (UpdateDatabaseRowOperationType, table_2_2, False),
        (DeleteDatabaseRowOperationType, table_2_2, False),
    ]

    check_perms(viewer_plus, viewer_plus_tests)

    print("builder_less")

    builder_less_tests = [
        # Workspace 1
        (ReadWorkspaceOperationType, workspace_1, True),
        (UpdateWorkspaceOperationType, workspace_1, False),
        (DeleteWorkspaceOperationType, workspace_1, False),
        # Workspace 2
        (ReadWorkspaceOperationType, workspace_2, False),
        (UpdateWorkspaceOperationType, workspace_2, False),
        (DeleteWorkspaceOperationType, workspace_2, False),
        # Database_1
        (ReadApplicationOperationType, workspace_1, True),
        (CreateTableDatabaseTableOperationType, database_1, True),
        (ListTablesDatabaseTableOperationType, database_1, True),
        # Table_1_1
        (ReadDatabaseTableOperationType, table_1_1, True),
        (UpdateDatabaseTableOperationType, table_1_1, False),
        (DeleteDatabaseTableOperationType, table_1_1, False),
        (ListRowsDatabaseTableOperationType, table_1_1, True),
        (CreateRowDatabaseTableOperationType, table_1_1, False),
        # Table_1_2
        (ReadDatabaseTableOperationType, table_1_2, True),
        (UpdateDatabaseTableOperationType, table_1_2, True),
        (DeleteDatabaseTableOperationType, table_1_2, True),
        (ListRowsDatabaseTableOperationType, table_1_2, True),
        (CreateRowDatabaseTableOperationType, table_1_2, True),
        # Database_2
        (ReadApplicationOperationType, workspace_2, False),
        (CreateTableDatabaseTableOperationType, database_2, False),
        (ListTablesDatabaseTableOperationType, database_2, False),
        # Table_2_1
        (ReadDatabaseTableOperationType, table_2_1, False),
        (UpdateDatabaseTableOperationType, table_2_1, False),
        (DeleteDatabaseTableOperationType, table_2_1, False),
        (ListRowsDatabaseTableOperationType, table_2_1, False),
        (CreateRowDatabaseTableOperationType, table_2_1, False),
        # Table_2_2
        (ReadDatabaseTableOperationType, table_2_2, False),
        (UpdateDatabaseTableOperationType, table_2_2, False),
        (DeleteDatabaseTableOperationType, table_2_2, False),
        (ListRowsDatabaseTableOperationType, table_2_2, False),
        (CreateRowDatabaseTableOperationType, table_2_2, False),
        # Table_1_1 rows
        (ReadDatabaseRowOperationType, table_1_1, True),
        (UpdateDatabaseRowOperationType, table_1_1, False),
        (DeleteDatabaseRowOperationType, table_1_1, False),
        # Table_1_2 rows
        (ReadDatabaseRowOperationType, table_1_2, True),
        (UpdateDatabaseRowOperationType, table_1_2, True),
        (DeleteDatabaseRowOperationType, table_1_2, True),
        # Table_2_1 rows
        (ReadDatabaseRowOperationType, table_2_1, False),
        (UpdateDatabaseRowOperationType, table_2_1, False),
        (DeleteDatabaseRowOperationType, table_2_1, False),
        # Table_2_2 rows
        (ReadDatabaseRowOperationType, table_2_2, False),
        (UpdateDatabaseRowOperationType, table_2_2, False),
        (DeleteDatabaseRowOperationType, table_2_2, False),
    ]

    check_perms(builder_less, builder_less_tests)


def test_check_permissions_with_teams(
    data_fixture, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = data_fixture.create_user()

    workspace_1 = data_fixture.create_workspace(members=[user])
    database_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )

    table_1_1, _, _ = data_fixture.build_table(
        columns=[("number", "number"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=1,
    )

    table_1_2, _, _ = data_fixture.build_table(
        columns=[("number", "number"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=2,
    )

    team1 = enterprise_data_fixture.create_team(workspace=workspace_1, members=[user])

    role_builder = Role.objects.get(uid="BUILDER")
    role_viewer = Role.objects.get(uid="VIEWER")
    role_no_access = Role.objects.get(uid="NO_ACCESS")
    low_priority_role = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")

    perm_manager = RolePermissionManagerType()

    # The low priority role gives no permissions
    RoleAssignmentHandler().assign_role(user, workspace_1, role=low_priority_role)

    with pytest.raises(PermissionException):
        perm_manager.check_permissions(
            user,
            ReadApplicationOperationType.type,
            workspace=workspace_1,
            context=database_1,
        )

    # The user role should take the precedence
    RoleAssignmentHandler().assign_role(user, workspace_1, role=role_builder)
    RoleAssignmentHandler().assign_role(team1, workspace_1, role=role_viewer)

    assert (
        perm_manager.check_permissions(
            user,
            UpdateApplicationOperationType.type,
            workspace=workspace_1,
            context=database_1.application_ptr,
        )
        is True
    )

    # Now the user role is low_priority the team role should work
    RoleAssignmentHandler().assign_role(user, workspace_1, role=low_priority_role)

    assert (
        perm_manager.check_permissions(
            user,
            ReadApplicationOperationType.type,
            workspace=workspace_1,
            context=database_1.application_ptr,
        )
        is True
    )

    with pytest.raises(PermissionException):
        perm_manager.check_permissions(
            user,
            UpdateApplicationOperationType.type,
            workspace=workspace_1,
            context=database_1.application_ptr,
        )

    # Prevent from accessing the table at team level
    RoleAssignmentHandler().assign_role(
        team1, workspace_1, role=role_no_access, scope=table_1_1
    )

    with pytest.raises(PermissionException):
        perm_manager.check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=workspace_1,
            context=table_1_1,
        )

    assert (
        perm_manager.check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=workspace_1,
            context=table_1_2,
        )
        is True
    )

    # And now user level table role should override the team role
    RoleAssignmentHandler().assign_role(
        user, workspace_1, role=role_builder, scope=table_1_1
    )

    assert (
        perm_manager.check_permissions(
            user,
            UpdateDatabaseTableOperationType.type,
            workspace=workspace_1,
            context=table_1_1,
        )
        is True
    )

    with pytest.raises(PermissionException):
        perm_manager.check_permissions(
            user,
            UpdateDatabaseTableOperationType.type,
            workspace=workspace_1,
            context=table_1_2,
        )

    # User is now BUILDER at database level. Team most precise role should be used
    RoleAssignmentHandler().assign_role(user, workspace_1, role=None, scope=table_1_1)
    RoleAssignmentHandler().assign_role(
        user, workspace_1, role=role_builder, scope=database_1
    )

    with pytest.raises(PermissionException):
        perm_manager.check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=workspace_1,
            context=table_1_1,
        )

    assert (
        perm_manager.check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=workspace_1,
            context=table_1_2,
        )
        is True
    )


@pytest.mark.django_db
def test_check_multiple_permissions(data_fixture, enterprise_data_fixture):
    admin = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    user_4 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, members=[user_2, user_3, user_4]
    )
    database1 = data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    table11 = data_fixture.create_database_table(user=admin, database=database1)
    table12 = data_fixture.create_database_table(user=admin, database=database1)
    database2 = data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    table21 = data_fixture.create_database_table(user=admin, database=database2)
    table22 = data_fixture.create_database_table(user=admin, database=database2)

    team1 = enterprise_data_fixture.create_team(workspace=workspace, members=[user_3])
    team2 = enterprise_data_fixture.create_team(workspace=workspace, members=[user_4])
    team3 = enterprise_data_fixture.create_team(
        workspace=workspace, members=[user_3, user_4]
    )

    editor_role = Role.objects.get(uid="EDITOR")
    builder_role = Role.objects.get(uid="BUILDER")
    viewer_role = Role.objects.get(uid="VIEWER")
    no_role_role = Role.objects.get(uid="NO_ACCESS")
    low_priority_role = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")

    RoleAssignmentHandler().assign_role(
        user_2, workspace, role=builder_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user_3, workspace, role=no_role_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user_4, workspace, role=low_priority_role, scope=workspace
    )

    # User 2 assignments
    RoleAssignmentHandler().assign_role(
        user_2, workspace, role=editor_role, scope=database1
    )
    RoleAssignmentHandler().assign_role(
        user_2, workspace, role=no_role_role, scope=table12
    )
    RoleAssignmentHandler().assign_role(
        user_2, workspace, role=viewer_role, scope=table22
    )

    # User 4 assignments
    RoleAssignmentHandler().assign_role(
        user_4, workspace, role=no_role_role, scope=database1
    )
    RoleAssignmentHandler().assign_role(
        user_4, workspace, role=builder_role, scope=table11
    )
    RoleAssignmentHandler().assign_role(
        user_4, workspace, role=no_role_role, scope=table22
    )

    # Team assignments
    RoleAssignmentHandler().assign_role(
        team1, workspace, role=builder_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team1, workspace, role=viewer_role, scope=database2
    )
    RoleAssignmentHandler().assign_role(
        team2, workspace, role=editor_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team2, workspace, role=viewer_role, scope=database2
    )
    RoleAssignmentHandler().assign_role(
        team3, workspace, role=builder_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team3, workspace, role=viewer_role, scope=database2
    )

    permission_manager = RolePermissionManagerType()

    checks = [
        PermissionCheck(
            original_actor=user_2,
            operation_name=ReadApplicationOperationType.type,
            context=database1,
        ),
        PermissionCheck(
            original_actor=user_2,
            operation_name=ReadDatabaseTableOperationType.type,
            context=table12,
        ),
        PermissionCheck(
            original_actor=user_2,
            operation_name=ReadDatabaseTableOperationType.type,
            context=table21,
        ),
        PermissionCheck(
            original_actor=user_3,
            operation_name=DeleteApplicationOperationType.type,
            context=workspace,
        ),
        PermissionCheck(
            original_actor=user_3,
            operation_name=ReadApplicationOperationType.type,
            context=database2,
        ),
        PermissionCheck(
            original_actor=user_4,
            operation_name=ReadApplicationOperationType.type,
            context=database1,
        ),
        PermissionCheck(
            original_actor=user_4,
            operation_name=ReadDatabaseTableOperationType.type,
            context=table12,
        ),
        PermissionCheck(
            original_actor=user_4,
            operation_name=ReadDatabaseTableOperationType.type,
            context=table21,
        ),
    ]

    result = permission_manager.check_multiple_permissions(checks, workspace=workspace)

    assert len(result) == len(checks)
    assert [v is True for v in result.values()] == [
        True,
        False,
        True,
        False,
        True,
        True,
        False,
        True,
    ]


@pytest.mark.django_db(transaction=True)
@override_settings(
    PERMISSION_MANAGERS=["core", "staff", "member", "role", "basic"],
)
def test_get_permissions_object(data_fixture, enterprise_data_fixture, synced_roles):
    (
        admin,
        builder,
        editor,
        viewer,
        viewer_plus,
        builder_less,
        no_access,
        workspace_1,
        workspace_2,
        database_1,
        database_2,
        database_3,
        table_1_1,
        table_1_2,
        table_2_1,
        table_2_2,
    ) = _populate_test_data(data_fixture, enterprise_data_fixture)

    perm_manager = RolePermissionManagerType()

    perms = perm_manager.get_permissions_object(admin, workspace=workspace_1)

    assert perms[UpdateWorkspaceOperationType.type]["default"] is True
    assert perms[UpdateWorkspaceOperationType.type]["exceptions"] == []

    perms = perm_manager.get_permissions_object(builder, workspace=workspace_1)

    assert perms[UpdateWorkspaceOperationType.type]["default"] is False
    assert perms[UpdateWorkspaceOperationType.type]["exceptions"] == []

    perms = perm_manager.get_permissions_object(builder, workspace=workspace_2)

    assert perms[ReadApplicationOperationType.type]["default"] is False
    assert perms[ReadApplicationOperationType.type]["exceptions"] == [
        database_2.application_ptr_id
    ]

    assert perms[ListApplicationsWorkspaceOperationType.type]["default"] is False
    assert perms[ListApplicationsWorkspaceOperationType.type]["exceptions"] == [
        workspace_2.id
    ]

    assert perms[ReadFieldOperationType.type]["default"] is False
    assert sorted(perms[ReadFieldOperationType.type]["exceptions"]) == sorted(
        list(table_2_1.field_set.all().values_list("id", flat=True))
    )

    perms = perm_manager.get_permissions_object(viewer_plus, workspace=workspace_1)

    assert perms[UpdateDatabaseRowOperationType.type]["default"] is False
    assert perms[UpdateDatabaseRowOperationType.type]["exceptions"] == [table_1_1.id]

    assert perms[UpdateFieldOperationType.type]["default"] is False
    assert sorted(perms[UpdateFieldOperationType.type]["exceptions"]) == sorted(
        list(table_1_1.field_set.all().values_list("id", flat=True))
    )

    perms = perm_manager.get_permissions_object(builder_less, workspace=workspace_1)

    assert perms[UpdateDatabaseRowOperationType.type]["default"] is True
    assert perms[UpdateDatabaseRowOperationType.type]["exceptions"] == [table_1_1.id]


@pytest.mark.django_db(transaction=True)
@override_settings(
    PERMISSION_MANAGERS=["core", "staff", "member", "role", "basic"],
)
def test_get_permissions_object_with_database_and_table_level_permissions(
    data_fixture, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    admin = data_fixture.create_user(email="admin@test.net")
    editor = data_fixture.create_user(email="editor@test.net")

    workspace_1 = data_fixture.create_workspace(
        user=admin,
        members=[editor],
    )
    data_fixture.create_database_application()
    data_fixture.create_database_application()
    data_fixture.create_database_application()
    data_fixture.create_database_application()
    data_fixture.create_database_application()

    database_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    database_2 = data_fixture.create_database_application(
        workspace=workspace_1, order=2
    )

    table_0, _, _ = data_fixture.build_table(
        columns=[("number", "number"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=1,
    )
    table_1, _, _ = data_fixture.build_table(
        columns=[("number", "number"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=1,
    )
    table_2, _, _ = data_fixture.build_table(
        columns=[("number", "text"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_2,
        order=2,
    )
    table_3, _, _ = data_fixture.build_table(
        columns=[("number", "text"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_2,
        order=3,
    )

    role_editor = Role.objects.get(uid="EDITOR")
    role_no_access = Role.objects.get(uid="NO_ACCESS")

    perm_manager = RolePermissionManagerType()

    # Case 1 - default policy is False, we add the permission to db then we remove
    # it from the table

    # Workspace level assignments
    RoleAssignmentHandler().assign_role(editor, workspace_1, role=role_no_access)

    # Application level assignments
    RoleAssignmentHandler().assign_role(
        editor, workspace_1, role=role_editor, scope=database_1.application_ptr
    )

    # Table level assignments
    RoleAssignmentHandler().assign_role(
        editor, workspace_1, role=role_no_access, scope=table_1
    )

    perms = perm_manager.get_permissions_object(editor, workspace=workspace_1)

    assert perms[CreateRowDatabaseTableOperationType.type]["default"] is False

    # The user has editor permissions to `database_1` but no_role at `table_1`,
    # so we should see only the `table_0` as an exception to the default (False)
    # policy.
    assert perms[CreateRowDatabaseTableOperationType.type]["exceptions"] == [
        table_0.id,
    ]

    # Case 2 - default policy is True and we remove then add the permission

    # Now with the opposite default policy
    RoleAssignmentHandler().assign_role(editor, workspace_1, role=role_editor)

    # Application level assignments
    RoleAssignmentHandler().assign_role(
        editor, workspace_1, role=role_no_access, scope=database_1.application_ptr
    )

    # Table level assignments
    RoleAssignmentHandler().assign_role(
        editor, workspace_1, role=role_editor, scope=table_1
    )

    perms = perm_manager.get_permissions_object(editor, workspace=workspace_1)

    assert perms[CreateRowDatabaseTableOperationType.type]["default"] is True

    # The user has editor permissions to `table_1` but no_role at `database_1`,
    # so we should see only the `table_0` as an exception to the default
    # (True) policy.
    assert perms[CreateRowDatabaseTableOperationType.type]["exceptions"] == [
        table_0.id,
    ]

    # case 3 - default is False and we add the permission on another database

    # Workspace level assignments
    RoleAssignmentHandler().assign_role(editor, workspace_1, role=role_no_access)

    # Table level assignments
    RoleAssignmentHandler().assign_role(
        editor, workspace_1, role=role_editor, scope=table_1
    )

    # Database level assignments
    RoleAssignmentHandler().assign_role(
        editor, workspace_1, role=role_editor, scope=database_2
    )

    perms = perm_manager.get_permissions_object(editor, workspace=workspace_1)

    assert perms[CreateRowDatabaseTableOperationType.type]["default"] is False

    # The user has editor permissions to `table_1` and `database_2`, so we expect
    # table 1, table 2 and table 3 to be in there because table 2,3 belong
    # in database 2.
    assert sorted(
        perms[CreateRowDatabaseTableOperationType.type]["exceptions"]
    ) == sorted(
        [
            table_1.id,
            table_2.id,
            table_3.id,
        ]
    )


@pytest.mark.django_db(transaction=True)
def test_get_permissions_object_with_teams(
    data_fixture, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = data_fixture.create_user()

    workspace_1 = data_fixture.create_workspace(
        members=[user],
    )
    database_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )

    table_1_1, _, _ = data_fixture.build_table(
        columns=[("number", "number"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=1,
    )

    table_1_2, _, _ = data_fixture.build_table(
        columns=[("number", "number"), ("text", "text")],
        rows=[[1, "test"]],
        database=database_1,
        order=2,
    )

    team1 = enterprise_data_fixture.create_team(workspace=workspace_1, members=[user])
    team2 = enterprise_data_fixture.create_team(workspace=workspace_1, members=[user])

    role_builder = Role.objects.get(uid="BUILDER")
    role_viewer = Role.objects.get(uid="VIEWER")
    role_no_access = Role.objects.get(uid="NO_ACCESS")
    low_priority_role = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")

    perm_manager = RolePermissionManagerType()

    RoleAssignmentHandler().assign_role(user, workspace_1, role=low_priority_role)

    perms = perm_manager.get_permissions_object(user, workspace=workspace_1)

    for operation_type in [
        UpdateApplicationOperationType,
        ReadDatabaseTableOperationType,
    ]:
        assert perms[operation_type.type]["default"] is False
        assert perms[operation_type.type]["exceptions"] == []

    # The user role should take the precedence
    RoleAssignmentHandler().assign_role(user, workspace_1, role=role_builder)
    RoleAssignmentHandler().assign_role(team1, workspace_1, role=role_viewer)
    RoleAssignmentHandler().assign_role(team2, workspace_1, role=role_viewer)
    perms = perm_manager.get_permissions_object(user, workspace=workspace_1)

    assert perms[UpdateApplicationOperationType.type]["default"] is True
    assert perms[UpdateApplicationOperationType.type]["exceptions"] == []

    # Now the user role is low_priority the team role should work
    RoleAssignmentHandler().assign_role(user, workspace_1, role=low_priority_role)
    perms = perm_manager.get_permissions_object(user, workspace=workspace_1)

    assert perms[UpdateApplicationOperationType.type]["default"] is False
    assert perms[UpdateApplicationOperationType.type]["exceptions"] == []

    # Prevent from accessing the table at team level
    RoleAssignmentHandler().assign_role(
        team1, workspace_1, role=role_no_access, scope=table_1_1
    )
    perms = perm_manager.get_permissions_object(user, workspace=workspace_1)

    assert perms[ReadDatabaseTableOperationType.type]["default"] is True
    assert perms[ReadDatabaseTableOperationType.type]["exceptions"] == [table_1_1.id]

    # And now user level table role should override the team role
    RoleAssignmentHandler().assign_role(
        user, workspace_1, role=role_builder, scope=table_1_1
    )
    perms = perm_manager.get_permissions_object(user, workspace=workspace_1)

    assert perms[ReadDatabaseTableOperationType.type]["default"] is True
    assert perms[ReadDatabaseTableOperationType.type]["exceptions"] == []

    # User is now BUILDER at database level. Team most precise role should be used
    RoleAssignmentHandler().assign_role(user, workspace_1, role=None, scope=table_1_1)
    RoleAssignmentHandler().assign_role(
        user, workspace_1, role=role_builder, scope=database_1.application_ptr
    )
    perms = perm_manager.get_permissions_object(user, workspace=workspace_1)

    assert perms[ReadDatabaseTableOperationType.type]["default"] is True
    assert perms[ReadDatabaseTableOperationType.type]["exceptions"] == [table_1_1.id]

    RoleAssignmentHandler().assign_role(
        team2, workspace_1, role=role_builder, scope=table_1_1
    )
    perms = perm_manager.get_permissions_object(user, workspace=workspace_1)

    assert perms[ReadDatabaseTableOperationType.type]["default"] is True
    assert perms[ReadDatabaseTableOperationType.type]["exceptions"] == []


@pytest.mark.django_db(transaction=True)
@override_settings(
    PERMISSION_MANAGERS=["core", "staff", "member", "role", "basic"],
)
def test_filter_queryset(data_fixture, enterprise_data_fixture):
    (
        admin,
        builder,
        editor,
        viewer,
        viewer_plus,
        builder_less,
        no_access,
        workspace_1,
        workspace_2,
        database_1,
        database_2,
        database_3,
        table_1_1,
        table_1_2,
        table_2_1,
        table_2_2,
    ) = _populate_test_data(data_fixture, enterprise_data_fixture)

    perm_manager = RolePermissionManagerType()

    table_1_queryset = Table.objects.filter(database__workspace=workspace_1)
    table_2_queryset = Table.objects.filter(database__workspace=workspace_2)
    application_2_queryset = Application.objects.filter(workspace=workspace_2)

    admin_table_queryset = perm_manager.filter_queryset(
        admin,
        ListTablesDatabaseTableOperationType.type,
        table_1_queryset,
        workspace=workspace_1,
    )

    assert list(admin_table_queryset) == [table_1_1, table_1_2]

    admin_table_queryset_2 = perm_manager.filter_queryset(
        admin,
        ListTablesDatabaseTableOperationType.type,
        table_2_queryset,
        workspace=workspace_2,
    )

    assert list(admin_table_queryset_2) == []

    no_access_table_queryset = perm_manager.filter_queryset(
        no_access,
        ListTablesDatabaseTableOperationType.type,
        table_1_queryset,
        workspace=workspace_1,
    )

    assert list(no_access_table_queryset) == []

    builder_table_queryset = perm_manager.filter_queryset(
        builder,
        ListTablesDatabaseTableOperationType.type,
        table_2_queryset,
        workspace=workspace_2,
    )

    assert list(builder_table_queryset) == [table_2_1]

    viewer_role = Role.objects.get(uid="VIEWER")
    editor_role = Role.objects.get(uid="EDITOR")
    role_no_access = Role.objects.get(uid="NO_ACCESS")

    # In this scenario the user is:
    # - no_access at workspace_2 level
    # - Builder at table_2_1 level
    # -> should be able to see application_2 because it's parent of table_2_1
    builder_application_queryset = perm_manager.filter_queryset(
        builder,
        ListApplicationsWorkspaceOperationType.type,
        application_2_queryset,
        workspace=workspace_2,
    )

    assert list(builder_application_queryset) == [database_2.application_ptr]

    # In this scenario the user is:
    # - Viewer at workspace_2 level
    # - builder at at table_2_1 level
    # -> should be able to see application_2 and application_3
    RoleAssignmentHandler().assign_role(builder, workspace_2, role=viewer_role)

    builder_application_queryset = perm_manager.filter_queryset(
        builder,
        ListApplicationsWorkspaceOperationType.type,
        application_2_queryset,
        workspace=workspace_2,
    )

    assert list(builder_application_queryset) == [
        database_2.application_ptr,
        database_3.application_ptr,
    ]

    # In this scenario the user is:
    # - Viewer at workspace_2 level
    # - no_access at application_2 level
    # - builder at at table_2_1 level
    # -> should still be able to see application_2 and application_3
    # -> and table_2_1, table_1_x
    RoleAssignmentHandler().assign_role(
        builder, workspace_2, role=role_no_access, scope=database_2.application_ptr
    )

    builder_application_queryset = perm_manager.filter_queryset(
        builder,
        ListApplicationsWorkspaceOperationType.type,
        application_2_queryset,
        workspace=workspace_2,
    )

    assert list(builder_application_queryset) == [
        database_2.application_ptr,
        database_3.application_ptr,
    ]

    builder_table_queryset = perm_manager.filter_queryset(
        builder,
        ListTablesDatabaseTableOperationType.type,
        table_2_queryset,
        workspace=workspace_2,
    )

    assert list(builder_table_queryset) == [table_2_1]

    # In this scenario the user is:
    # - Viewer at workspace_2 level
    # - no_access at application_2 level
    # -> should be able to see application_3 only
    RoleAssignmentHandler().assign_role(builder, workspace_2, scope=table_2_1)

    builder_application_queryset = perm_manager.filter_queryset(
        builder,
        ListApplicationsWorkspaceOperationType.type,
        application_2_queryset,
        workspace=workspace_2,
    )

    assert list(builder_application_queryset) == [
        database_3.application_ptr,
    ]

    # In this scenario the user is:
    # - Viewer at workspace_2 level
    # - no_access at application_2 level
    # -> should be able to see application_3 only
    RoleAssignmentHandler().assign_role(builder, workspace_2, scope=table_2_1)

    builder_application_queryset = perm_manager.filter_queryset(
        builder,
        ListApplicationsWorkspaceOperationType.type,
        application_2_queryset,
        workspace=workspace_2,
    )

    assert list(builder_application_queryset) == [
        database_3.application_ptr,
    ]


@pytest.mark.django_db
def test_all_operations_are_in_at_least_one_default_role(data_fixture):
    exceptions = [
        CreateWorkspaceOperationType.type,
        ListWorkspacesOperationType.type,
        UpdateSettingsOperationType.type,
        ClearNotificationsOperationType.type,
        ListNotificationsOperationType.type,
        MarkNotificationAsReadOperationType.type,
        WriteFieldValuesOperationType.type,
        SubmitAnonymousFieldValuesOperationType.type,
    ]

    all_ops_in_roles = set()
    for ops in default_roles.values():
        all_ops_in_roles.update([o.type for o in ops])

    all_ops = set(operation_type_registry.get_all())

    missing_ops = []
    for op in all_ops:
        if op.type not in all_ops_in_roles and op.type not in exceptions:
            missing_ops.append(op)

    assert missing_ops == [], "Non Assigned Ops:\n" + str(
        "\n".join([o.__class__.__name__ + "," for o in missing_ops])
    )


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
# pytest -k "test_check_permission_performance" -s --run-disabled-in-ci
def test_check_permission_performance(data_fixture, enterprise_data_fixture, profiler):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user2])
    database1 = data_fixture.create_database_application(user=user, workspace=workspace)
    table11 = data_fixture.create_database_table(user=user, database=database1)
    table12 = data_fixture.create_database_table(user=user, database=database1)
    database2 = data_fixture.create_database_application(user=user, workspace=workspace)
    table21 = data_fixture.create_database_table(user=user, database=database2)
    table22 = data_fixture.create_database_table(user=user, database=database2)

    team1 = enterprise_data_fixture.create_team(
        workspace=workspace, members=[user, user2]
    )
    team2 = enterprise_data_fixture.create_team(
        workspace=workspace, members=[user, user2]
    )
    team3 = enterprise_data_fixture.create_team(
        workspace=workspace, members=[user, user2]
    )

    editor_role = Role.objects.get(uid="EDITOR")
    builder_role = Role.objects.get(uid="BUILDER")
    viewer_role = Role.objects.get(uid="VIEWER")
    no_role_role = Role.objects.get(uid="NO_ACCESS")
    low_priority_role = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")

    RoleAssignmentHandler().assign_role(
        user2, workspace, role=low_priority_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=editor_role, scope=database1
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_role_role, scope=table12
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=viewer_role, scope=table22
    )

    RoleAssignmentHandler().assign_role(
        team1, workspace, role=builder_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team1, workspace, role=viewer_role, scope=database2
    )
    RoleAssignmentHandler().assign_role(
        team2, workspace, role=editor_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team2, workspace, role=viewer_role, scope=database2
    )
    RoleAssignmentHandler().assign_role(
        team3, workspace, role=builder_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team3, workspace, role=viewer_role, scope=database2
    )

    permission_manager = RolePermissionManagerType()

    print("----------- first call queries ---------------")
    with CaptureQueriesContext(connection) as captured:
        permission_manager.check_permissions(
            user2,
            ReadDatabaseTableOperationType.type,
            workspace=workspace,
            context=table11,
        )

    for q in captured.captured_queries:
        print(q)
    print(len(captured.captured_queries))

    print("----------- second call queries ---------------")
    with CaptureQueriesContext(connection) as captured:
        permission_manager.check_permissions(
            user2,
            ReadDatabaseTableOperationType.type,
            workspace=workspace,
            context=table11,
        )

    for q in captured.captured_queries:
        print(q)
    print(len(captured.captured_queries))

    print("----------- check_permission perfs ---------------")
    with profiler(html_report_name="enterprise_check_permissions"):
        for i in range(1000):
            permission_manager.check_permissions(
                user2,
                ReadDatabaseTableOperationType.type,
                workspace=workspace,
                context=table11,
            )


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
# pytest -k "test_get_permissions_object_performance" -s --run-disabled-in-ci
def test_get_permissions_object_performance(
    data_fixture, enterprise_data_fixture, profiler
):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user2])
    database1 = data_fixture.create_database_application(user=user, workspace=workspace)
    table11 = data_fixture.create_database_table(user=user, database=database1)
    table12 = data_fixture.create_database_table(user=user, database=database1)
    database2 = data_fixture.create_database_application(user=user, workspace=workspace)
    table21 = data_fixture.create_database_table(user=user, database=database2)
    table22 = data_fixture.create_database_table(user=user, database=database2)

    team1 = enterprise_data_fixture.create_team(
        workspace=workspace, members=[user, user2]
    )
    team2 = enterprise_data_fixture.create_team(
        workspace=workspace, members=[user, user2]
    )
    team3 = enterprise_data_fixture.create_team(
        workspace=workspace, members=[user, user2]
    )

    editor_role = Role.objects.get(uid="EDITOR")
    builder_role = Role.objects.get(uid="BUILDER")
    viewer_role = Role.objects.get(uid="VIEWER")
    no_role_role = Role.objects.get(uid="NO_ACCESS")
    low_priority_role = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")

    RoleAssignmentHandler().assign_role(
        user2, workspace, role=low_priority_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=editor_role, scope=database1
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_role_role, scope=table12
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=viewer_role, scope=table22
    )

    RoleAssignmentHandler().assign_role(
        team1, workspace, role=builder_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team1, workspace, role=viewer_role, scope=database2
    )
    RoleAssignmentHandler().assign_role(
        team2, workspace, role=editor_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team2, workspace, role=viewer_role, scope=database2
    )
    RoleAssignmentHandler().assign_role(
        team3, workspace, role=builder_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        team3, workspace, role=viewer_role, scope=database2
    )

    permission_manager = RolePermissionManagerType()

    print("----------- first call queries ---------------")
    with CaptureQueriesContext(connection) as captured:
        permission_manager.get_permissions_object(user2, workspace=workspace)

    for q in captured.captured_queries:
        print(q)
    print(len(captured.captured_queries))

    print("----------- second call queries ---------------")
    with CaptureQueriesContext(connection) as captured:
        permission_manager.get_permissions_object(user2, workspace=workspace)

    for q in captured.captured_queries:
        print(q)
    print(len(captured.captured_queries))

    print("----------- get_permissions_object perfs ---------------")
    with profiler(html_report_name="enterprise_get_permissions_object"):
        for i in range(1000):
            permission_manager.get_permissions_object(user2, workspace=workspace)


@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
# pytest -k "test_check_multiple_permissions_perf" -s --run-disabled-in-ci
# 166 second for 3 710 000 checks on Intel(R) Core(TM) i9-9900K CPU @ 3.60GHz -
# 7200 bogomips
def test_check_multiple_permissions_perf(
    data_fixture, enterprise_data_fixture, profiler
):
    admin = data_fixture.create_user()

    users = []
    print("Populating database...")

    for _ in tqdm(range(1000), desc="Users creation"):
        try:
            users.append(data_fixture.create_user())
        except IntegrityError:
            pass

    workspace = data_fixture.create_workspace(user=admin, members=users)

    data = {}
    for _ in tqdm(range(10), desc="Database"):
        database = data_fixture.create_database_application(
            user=admin, workspace=workspace
        )
        data[database] = []
        for _ in range(10):
            data[database].append(
                data_fixture.create_database_table(user=admin, database=database)
            )

    teams = []
    for max in range(10):
        teams.append(
            enterprise_data_fixture.create_team(
                workspace=workspace,
                members=users,  # members=users[max * 10 : (max + 1) * 10 - 5]
            )
        )

    editor_role = Role.objects.get(uid="EDITOR")
    builder_role = Role.objects.get(uid="BUILDER")
    viewer_role = Role.objects.get(uid="VIEWER")
    no_role_role = Role.objects.get(uid="NO_ACCESS")
    low_priority_role = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")

    role_assignment_handler = RoleAssignmentHandler()

    def role_gen():
        while True:
            yield editor_role
            yield None
            yield viewer_role
            yield None
            yield no_role_role
            yield None
            yield builder_role
            yield None

    role_generator = role_gen()

    for user in tqdm(users, "User roles"):
        workspace_role = next(role_generator)
        if workspace_role is None:
            workspace_role = low_priority_role

        role_assignment_handler.assign_role(
            user, workspace, role=workspace_role, scope=workspace
        )

        for database, tables in data.items():
            role_assignment_handler.assign_role(
                user,
                workspace,
                role=next(role_generator),
                scope=database.application_ptr,
            )
            for table in tables:
                role_assignment_handler.assign_role(
                    user, workspace, role=next(role_generator), scope=table
                )

    for team in tqdm(teams, "Team roles"):
        for database, tables in data.items():
            role_assignment_handler.assign_role(
                team, workspace, role=next(role_generator), scope=database
            )
            for table in tables:
                role_assignment_handler.assign_role(
                    team, workspace, role=next(role_generator), scope=table
                )

    reset_queries()

    perm_manager = RolePermissionManagerType()

    all_op = operation_type_registry.get_all()

    db_op = [op for op in all_op if op.context_scope_name == "application"]
    table_op = [op for op in all_op if op.context_scope_name == "database_table"]

    checks = []
    for user in tqdm(users, "Creating checks"):
        for db, tables in data.items():
            for op in db_op:
                checks.append(
                    PermissionCheck(
                        original_actor=user,
                        operation_name=op.type,
                        context=db.application_ptr,
                    )
                )
            for table in tables:
                for op in table_op:
                    checks.append(
                        PermissionCheck(
                            original_actor=user, operation_name=op.type, context=table
                        )
                    )

    print(f"------------ For {len(checks)} checks! ----------")

    with CaptureQueriesContext(connection) as captured:
        with profiler(html_report_name="enterprise_check_multiple_permissions"):
            perm_manager.check_multiple_permissions(checks, workspace=workspace)

    for q in captured.captured_queries:
        print(q)
    print(len(captured.captured_queries))


@pytest.mark.django_db
def test_fetching_permissions_does_not_extra_queries_per_snapshot(
    data_fixture, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    admin = data_fixture.create_user()
    viewer = data_fixture.create_user()

    workspace = data_fixture.create_workspace(
        members=[admin, viewer],
    )
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    table = data_fixture.create_database_table(user=admin, database=database)

    role_admin = Role.objects.get(uid="ADMIN")
    role_viewer = Role.objects.get(uid="VIEWER")
    RoleAssignmentHandler().assign_role(admin, workspace, role=role_admin)
    RoleAssignmentHandler().assign_role(viewer, workspace, role=role_viewer)
    RoleAssignmentHandler().assign_role(
        admin, workspace, role=role_admin, scope=database.application_ptr
    )
    RoleAssignmentHandler().assign_role(
        viewer, workspace, role=role_viewer, scope=database.application_ptr
    )

    # The first time it also fetches the settings and the content types
    CoreHandler().get_permissions(viewer, workspace=workspace)

    with CaptureQueriesContext(connection) as captured_1, local_cache.context():
        CoreHandler().get_permissions(viewer, workspace=workspace)

    # Let's create a snapshot of the database
    handler = SnapshotHandler()
    snapshot = handler.create(database.id, admin, "Test snapshot")
    handler.perform_create(snapshot, Progress(100))

    with CaptureQueriesContext(connection) as captured_2, local_cache.context():
        CoreHandler().get_permissions(viewer, workspace=workspace)

    assert len(captured_2.captured_queries) == len(captured_1.captured_queries)

    # Another snapshot won't increase the number of queries
    snapshot = handler.create(database.id, admin, "Test snapshot 2")
    handler.perform_create(snapshot, Progress(100))

    with CaptureQueriesContext(connection) as captured_3, local_cache.context():
        CoreHandler().get_permissions(viewer, workspace=workspace)

    assert len(captured_3.captured_queries) == len(captured_2.captured_queries)

    # The same should be valid for builder applications

    builder = data_fixture.create_builder_application(user=admin, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    with CaptureQueriesContext(connection) as captured_1, local_cache.context():
        CoreHandler().get_permissions(viewer, workspace=workspace)

    # Let's create a snapshot of the builder app
    handler = SnapshotHandler()
    snapshot = handler.create(builder.id, admin, "Test snapshot")
    handler.perform_create(snapshot, Progress(100))

    with CaptureQueriesContext(connection) as captured_2, local_cache.context():
        CoreHandler().get_permissions(viewer, workspace=workspace)

    assert len(captured_1.captured_queries) == len(captured_2.captured_queries)
