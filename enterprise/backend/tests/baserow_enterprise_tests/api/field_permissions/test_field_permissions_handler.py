from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.export.handler import ExportHandler
from baserow.contrib.database.fields.exceptions import FieldNotInTable
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import WriteFieldValuesOperationType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow_enterprise.field_permissions.handler import (
    FieldPermissionRead,
    FieldPermissionsHandler,
)
from baserow_enterprise.field_permissions.models import (
    FieldPermissions,
    FieldPermissionsRoleEnum,
)
from baserow_enterprise.field_permissions.permission_manager import (
    FieldPermissionManagerType,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment
from baserow_enterprise.teams.models import Team


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_builder_and_up_can_get_field_permissions(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=editor_role, scope=database
    )

    with pytest.raises(PermissionDenied):
        FieldPermissionsHandler.get_field_permissions(user, field)

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=builder_role, scope=database
    )

    field_permissions = FieldPermissionsHandler.get_field_permissions(user, field)
    assert isinstance(field_permissions, FieldPermissionRead)
    assert not isinstance(field_permissions, FieldPermissions)
    assert field_permissions.field == field
    assert field_permissions.role == "EDITOR"
    assert field_permissions.allow_in_forms is True
    assert field_permissions.subjects == []


@pytest.mark.django_db
def test_get_field_permissions_reuses_the_loaded_field(
    enterprise_data_fixture, django_assert_num_queries
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    FieldPermissions.objects.create(
        field=field,
        role=FieldPermissionsRoleEnum.EDITOR.value,
        allow_in_forms=True,
    )
    persisted_permissions = FieldPermissions.objects.get(field=field)
    assert "field" not in persisted_permissions._state.fields_cache

    # Resolve the permission-check context before measuring only DTO construction.
    field.table.database.workspace
    with (
        patch.object(CoreHandler, "check_permissions"),
        patch.object(
            FieldPermissionsHandler,
            "_get_field_permissions",
            return_value=persisted_permissions,
        ),
        django_assert_num_queries(0),
    ):
        result = FieldPermissionsHandler.get_field_permissions(user, field)

    assert result.field is field


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_builder_and_up_can_update_field_permissions(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=editor_role, scope=database
    )

    with pytest.raises(PermissionDenied):
        FieldPermissionsHandler.update_field_permissions(user, field, "EDITOR", True)

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=builder_role, scope=database
    )

    field_permissions = FieldPermissionsHandler.update_field_permissions(
        user, field, "EDITOR", True
    )
    assert field_permissions.field == field
    assert field_permissions.role == "EDITOR"
    assert field_permissions.allow_in_forms is True
    assert field_permissions.can_write_values is True

    field_permissions = FieldPermissionsHandler.update_field_permissions(
        user, field, "NOBODY", False
    )
    assert field_permissions.field == field
    assert field_permissions.role == "NOBODY"
    assert field_permissions.allow_in_forms is False
    assert field_permissions.can_write_values is False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_field_permissions_require_selection_and_an_editor_or_higher_role(
    enterprise_data_fixture, synced_roles
):
    admin = enterprise_data_fixture.create_user()
    selected_editor = enterprise_data_fixture.create_user()
    unselected_editor = enterprise_data_fixture.create_user()
    selected_viewer = enterprise_data_fixture.create_user()
    selected_team_member = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=admin)
    workspace = database.workspace
    for workspace_user in [
        selected_editor,
        unselected_editor,
        selected_viewer,
        selected_team_member,
    ]:
        enterprise_data_fixture.create_user_workspace(
            user=workspace_user, workspace=workspace, permissions="EDITOR"
        )

    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    team = enterprise_data_fixture.create_team(
        workspace=workspace, members=[selected_team_member]
    )
    enterprise_data_fixture.enable_enterprise()

    editor_role = Role.objects.get(uid="EDITOR")
    viewer_role = Role.objects.get(uid="VIEWER")
    for editor in [selected_editor, unselected_editor, selected_team_member]:
        RoleAssignmentHandler().assign_role(
            editor, workspace, editor_role, scope=database
        )
    RoleAssignmentHandler().assign_role(
        selected_viewer, workspace, viewer_role, scope=database
    )

    FieldPermissionsHandler.update_field_permissions(
        admin,
        field,
        FieldPermissionsRoleEnum.CUSTOM,
        subjects=[
            {"subject_id": selected_editor.id, "subject_type": "auth.User"},
            {"subject_id": selected_viewer.id, "subject_type": "auth.User"},
            {
                "subject_id": team.id,
                "subject_type": "baserow_enterprise.Team",
            },
        ],
    )

    def assert_can_write(user, expected):
        if expected:
            assert CoreHandler().check_permissions(
                user,
                WriteFieldValuesOperationType.type,
                context=field,
                workspace=workspace,
            )
        else:
            with pytest.raises(PermissionDenied):
                CoreHandler().check_permissions(
                    user,
                    WriteFieldValuesOperationType.type,
                    context=field,
                    workspace=workspace,
                )

    assert_can_write(selected_editor, True)
    assert_can_write(selected_team_member, True)
    assert_can_write(unselected_editor, False)
    assert_can_write(selected_viewer, False)
    assert_can_write(admin, False)

    def write_exceptions_for(user):
        permissions = CoreHandler().get_permissions(user, workspace=workspace)
        field_manager = next(
            manager
            for manager in permissions
            if manager["name"] == FieldPermissionManagerType.type
        )
        return field_manager["permissions"][WriteFieldValuesOperationType.type][
            "exceptions"
        ]

    assert field.id not in write_exceptions_for(selected_editor)
    assert field.id not in write_exceptions_for(selected_team_member)
    assert field.id in write_exceptions_for(unselected_editor)
    assert field.id in write_exceptions_for(selected_viewer)
    assert field.id in write_exceptions_for(admin)

    # The marker must not replace the selected user's normal RBAC role.
    roles_by_scope = RoleAssignmentHandler().get_roles_per_scope(
        workspace, selected_editor
    )
    assert [
        role.uid
        for role in RoleAssignmentHandler().get_computed_roles(roles_by_scope, field)
    ] == ["EDITOR"]

    # Switching away from CUSTOM clears the selected subjects.
    FieldPermissionsHandler.update_field_permissions(admin, field, "EDITOR")
    assert FieldPermissionsHandler._get_field_permission_subjects(field) == []
    assert_can_write(selected_editor, True)
    assert_can_write(unselected_editor, True)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_field_subjects_are_resolved_in_two_queries_for_many_actors_and_fields(
    enterprise_data_fixture, synced_roles, django_assert_num_queries
):
    admin = enterprise_data_fixture.create_user()
    directly_selected = enterprise_data_fixture.create_user()
    selected_via_team = enterprise_data_fixture.create_user()
    unselected = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=admin)
    workspace = database.workspace
    for member in [directly_selected, selected_via_team, unselected]:
        enterprise_data_fixture.create_user_workspace(
            user=member, workspace=workspace, permissions="EDITOR"
        )

    table = enterprise_data_fixture.create_database_table(database=database)
    fields = [enterprise_data_fixture.create_text_field(table=table) for _ in range(5)]
    team = enterprise_data_fixture.create_team(
        workspace=workspace, members=[selected_via_team]
    )
    subjects = [
        {"subject_id": directly_selected.id, "subject_type": "auth.User"},
        {"subject_id": team.id, "subject_type": "baserow_enterprise.Team"},
    ]
    for field in fields:
        FieldPermissionsHandler._sync_field_permission_subjects(field, subjects)

    ContentType.objects.get_for_models(get_user_model(), Team, Field)
    manager = FieldPermissionManagerType()
    actors = [directly_selected, selected_via_team, unselected]

    with django_assert_num_queries(2):
        fields_by_actor = manager._get_custom_field_ids_by_actor(
            workspace, actors, {field.id for field in fields}
        )

    all_field_ids = {field.id for field in fields}
    assert fields_by_actor[directly_selected] == all_field_ids
    assert fields_by_actor[selected_via_team] == all_field_ids
    assert fields_by_actor[unselected] == set()


@pytest.mark.django_db
def test_get_subject_options_returns_searchable_workspace_users_and_teams(
    enterprise_data_fixture,
):
    admin = enterprise_data_fixture.create_user()
    selected_user = enterprise_data_fixture.create_user(
        first_name="Selectable user", email="selectable-user@example.com"
    )
    outsider = enterprise_data_fixture.create_user(first_name="Selectable outsider")
    database = enterprise_data_fixture.create_database_application(user=admin)
    workspace = database.workspace
    enterprise_data_fixture.create_user_workspace(
        user=selected_user, workspace=workspace, permissions="EDITOR"
    )
    team = enterprise_data_fixture.create_team(
        name="Selectable team", workspace=workspace, members=[selected_user]
    )

    options = list(
        FieldPermissionsHandler.get_subject_options(
            workspace,
            search=" selectable ",
            exclude_user_ids=[],
            exclude_team_ids=[],
        )
    )

    assert {(option["subject_type"], option["subject_id"]) for option in options} == {
        ("auth.User", selected_user.id),
        ("baserow_enterprise.Team", team.id),
    }
    assert all(option["subject_id"] != outsider.id for option in options)
    assert (
        next(
            option
            for option in options
            if option["subject_type"] == "baserow_enterprise.Team"
        )["subject_count"]
        == 1
    )


@pytest.mark.django_db
def test_sync_empty_field_permission_subjects_uses_single_delete_query(
    enterprise_data_fixture, django_assert_num_queries
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    ContentType.objects.get_for_model(Field)

    with django_assert_num_queries(1):
        subjects = FieldPermissionsHandler._sync_field_permission_subjects(field, [])

    assert subjects == []


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_deleting_field_cascades_to_custom_field_subject_assignments(
    enterprise_data_fixture, synced_roles
):
    admin = enterprise_data_fixture.create_user()
    selected_user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=admin)
    workspace = database.workspace
    enterprise_data_fixture.create_user_workspace(
        user=selected_user, workspace=workspace, permissions="EDITOR"
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)

    FieldPermissionsHandler._sync_field_permission_subjects(
        field,
        [{"subject_id": selected_user.id, "subject_type": "auth.User"}],
    )
    assert RoleAssignment.objects.filter(scope_id=field.id).exists()

    field.delete()

    assert not RoleAssignment.objects.filter(scope_id=field.id).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_update_field_permissions_send_permissions_updated_signal(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    test_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[user, test_user])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=builder_role, scope=database
    )

    with patch(
        "baserow_enterprise.signals.field_permissions_updated.send"
    ) as mocked_signal:
        FieldPermissionsHandler.update_field_permissions(user, field, "ADMIN", True)

        assert mocked_signal.call_count == 1
        assert mocked_signal.call_args[1]["user"] == user
        assert mocked_signal.call_args[1]["workspace"] == database.workspace
        assert mocked_signal.call_args[1]["field"] == field
        assert mocked_signal.call_args[1]["role"] == "ADMIN"
        assert mocked_signal.call_args[1]["allow_in_forms"] is True

    with patch("baserow.ws.tasks.broadcast_to_users.delay") as mocked_task:
        FieldPermissionsHandler.update_field_permissions(user, field, "NOBODY", True)
        assert mocked_task.call_count == 1
        assert mocked_task.call_args[0][0] == unordered([user.id, test_user.id])
        assert mocked_task.call_args[0][1] == {
            "type": "field_permissions_updated",
            "workspace_id": database.workspace.id,
            "field_id": field.id,
            "role": "NOBODY",
            "allow_in_forms": True,
        }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_create_or_update_rows_without_proper_permisisons(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    test_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[user, test_user])
    database = enterprise_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    number_field = enterprise_data_fixture.create_number_field(table=table)
    enterprise_data_fixture.enable_enterprise()
    model = table.get_model()

    (row,) = RowHandler().force_create_rows(user, table, [{}], model=model).created_rows

    def _assign_role(role):
        RoleAssignmentHandler().assign_role(
            subject=test_user,
            workspace=database.workspace,
            role=role,
            scope=database,
        )

    def _create_row_with_field_value(field, value):
        RowHandler().create_rows(
            user=test_user,
            table=table,
            rows_values=[{field.db_column: value}],
            model=model,
        )

    def _update_row_with_field_value(field, value):
        RowHandler().update_rows(
            user=test_user,
            table=table,
            rows_values=[{"id": row.id, field.db_column: value}],
            model=model,
        )

    def _import_rows_with_values(values):
        return RowHandler().import_rows(
            user=test_user,
            table=table,
            data=[values],
            configuration=None,
            validate=False,
        )

    _assign_role(Role.objects.get(uid="EDITOR"))

    with pytest.raises(ValueError):
        FieldPermissionsHandler.update_field_permissions(
            test_user, text_field, "NON_EXISTING_ROLE"
        )

    # Default: everyone with at least EDITOR role can edit the field
    FieldPermissionsHandler.update_field_permissions(user, text_field, "EDITOR")

    _update_row_with_field_value(text_field, "editor")
    _create_row_with_field_value(text_field, "editor")

    rows, _ = _import_rows_with_values(["editor"])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "editor"

    # BUILDER and up can edit the field
    FieldPermissionsHandler.update_field_permissions(
        user, text_field, FieldPermissionsRoleEnum.BUILDER
    )

    # cannot edit/create rows with the text_field
    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "builder")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "builder")

    # Import treats the unwritable text field like a read-only field and maps the
    # first value to the remaining writable number field.
    rows, _ = _import_rows_with_values([10])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None
    assert getattr(rows[0], number_field.db_column) == 10

    # test_user can still edit the number_field
    _update_row_with_field_value(number_field, 1)
    _create_row_with_field_value(number_field, 1)

    # Let's assign BUILDER role to test_user
    _assign_role(Role.objects.get(uid="BUILDER"))

    # Now test_user has BUILDER role and can edit the text_field
    _update_row_with_field_value(text_field, "builder")
    _create_row_with_field_value(text_field, "builder")

    rows, _ = _import_rows_with_values(["builder"])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "builder"

    FieldPermissionsHandler.update_field_permissions(user, text_field, "ADMIN")

    # Builders cannot edit/create rows with the text_field anymore
    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "admin")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "admin")

    rows, _ = _import_rows_with_values([20])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None
    assert getattr(rows[0], number_field.db_column) == 20

    # they can still edit other fields
    _update_row_with_field_value(number_field, 2)
    _create_row_with_field_value(number_field, 2)

    # Let's assign ADMIN role to test_user
    _assign_role(Role.objects.get(uid="ADMIN"))

    _update_row_with_field_value(text_field, "admin")
    _create_row_with_field_value(text_field, "admin")

    rows, _ = _import_rows_with_values(["admin"])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "admin"

    # Now no one is allowed to edit the text_field
    FieldPermissionsHandler.update_field_permissions(user, text_field, "NOBODY")

    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "nobody")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "nobody")

    rows, _ = _import_rows_with_values([30])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None
    assert getattr(rows[0], number_field.db_column) == 30


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("use_upsert", [False, True])
def test_import_rows_excludes_unwritable_fields_from_positional_schema(
    enterprise_data_fixture, synced_roles, use_upsert
):
    admin = enterprise_data_fixture.create_user()
    importer = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[admin, importer])
    database = enterprise_data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    name_field = enterprise_data_fixture.create_text_field(
        table=table, name="Name", primary=True
    )
    notes_field = enterprise_data_fixture.create_long_text_field(
        table=table, name="Notes"
    )
    active_field = enterprise_data_fixture.create_boolean_field(
        table=table, name="Active"
    )
    enterprise_data_fixture.enable_enterprise()

    RoleAssignmentHandler().assign_role(
        subject=admin,
        workspace=workspace,
        role=Role.objects.get(uid="ADMIN"),
        scope=database,
    )
    RoleAssignmentHandler().assign_role(
        subject=importer,
        workspace=workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=database,
    )
    FieldPermissionsHandler.update_field_permissions(admin, notes_field, "ADMIN")

    model = table.get_model()
    configuration = {
        "import_fields": [name_field.id, active_field.id],
    }
    if use_upsert:
        RowHandler().force_create_rows(
            admin,
            table,
            [
                {
                    name_field.db_column: "Ada",
                    notes_field.db_column: "Protected",
                    active_field.db_column: False,
                }
            ],
            model=model,
        )
        configuration.update(
            {
                "upsert_fields": [name_field.id],
                "upsert_values": [["Ada"]],
            }
        )

    _, report = RowHandler().import_rows(
        importer,
        table,
        data=[["Ada", True]],
        configuration=configuration,
        validate=False,
    )

    assert report == {}
    row = model.objects.get()
    assert getattr(row, name_field.db_column) == "Ada"
    assert getattr(row, notes_field.db_column) == ("Protected" if use_upsert else None)
    assert getattr(row, active_field.db_column) is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("permission_revoked_after_snapshot", [False, True])
def test_import_rows_rejects_unwritable_upsert_fields(
    enterprise_data_fixture, synced_roles, permission_revoked_after_snapshot
):
    admin = enterprise_data_fixture.create_user()
    importer = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[admin, importer])
    database = enterprise_data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    enterprise_data_fixture.create_text_field(table=table, name="Name", primary=True)
    protected_field = enterprise_data_fixture.create_text_field(
        table=table, name="Protected"
    )
    enterprise_data_fixture.enable_enterprise()

    RoleAssignmentHandler().assign_role(
        subject=admin,
        workspace=workspace,
        role=Role.objects.get(uid="ADMIN"),
        scope=database,
    )
    RoleAssignmentHandler().assign_role(
        subject=importer,
        workspace=workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=database,
    )

    initial_role = "EDITOR" if permission_revoked_after_snapshot else "ADMIN"
    FieldPermissionsHandler.update_field_permissions(
        admin, protected_field, initial_role
    )
    row_handler = RowHandler()
    import_field_ids = [
        field.id for field in row_handler.get_import_fields(importer, table)
    ]

    if permission_revoked_after_snapshot:
        assert protected_field.id in import_field_ids
        FieldPermissionsHandler.update_field_permissions(
            admin, protected_field, "ADMIN"
        )
    else:
        assert protected_field.id not in import_field_ids

    with pytest.raises(FieldNotInTable):
        row_handler.import_rows(
            importer,
            table,
            data=[["Ada"] * len(import_field_ids)],
            configuration={
                "import_fields": import_field_ids,
                "upsert_fields": [protected_field.id],
                "upsert_values": [["Secret"]],
            },
            validate=False,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("permission_revoked", [False, True])
def test_import_rows_preserves_queued_field_positions_when_permissions_change(
    enterprise_data_fixture, synced_roles, permission_revoked
):
    admin = enterprise_data_fixture.create_user()
    importer = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[admin, importer])
    database = enterprise_data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    name_field = enterprise_data_fixture.create_text_field(
        table=table, name="Name", primary=True
    )
    protected_field = enterprise_data_fixture.create_number_field(
        table=table, name="Protected number"
    )
    active_field = enterprise_data_fixture.create_boolean_field(
        table=table, name="Active"
    )
    enterprise_data_fixture.enable_enterprise()

    RoleAssignmentHandler().assign_role(
        subject=admin,
        workspace=workspace,
        role=Role.objects.get(uid="ADMIN"),
        scope=database,
    )
    RoleAssignmentHandler().assign_role(
        subject=importer,
        workspace=workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=database,
    )

    initial_role = "EDITOR" if permission_revoked else "ADMIN"
    final_role = "ADMIN" if permission_revoked else "EDITOR"
    FieldPermissionsHandler.update_field_permissions(
        admin, protected_field, initial_role
    )

    row_handler = RowHandler()
    import_field_ids = [
        field.id for field in row_handler.get_import_fields(importer, table)
    ]
    expected_import_field_ids = [name_field.id, active_field.id]
    data = ["Ada", True]
    if permission_revoked:
        expected_import_field_ids.insert(1, protected_field.id)
        data.insert(1, "Not a number")
    assert import_field_ids == expected_import_field_ids

    FieldPermissionsHandler.update_field_permissions(admin, protected_field, final_role)

    _, report = row_handler.import_rows(
        importer,
        table,
        data=[data],
        configuration={"import_fields": import_field_ids},
        validate=True,
    )

    assert report == {}
    row = table.get_model().objects.get()
    assert getattr(row, name_field.db_column) == "Ada"
    assert getattr(row, protected_field.db_column) is None
    assert getattr(row, active_field.db_column) is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_unwritable_field_values_can_still_be_exported(
    enterprise_data_fixture, synced_roles, tmp_path
):
    admin = enterprise_data_fixture.create_user()
    exporter = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[admin, exporter])
    database = enterprise_data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    name_field = enterprise_data_fixture.create_text_field(
        table=table, name="Name", primary=True
    )
    notes_field = enterprise_data_fixture.create_long_text_field(
        table=table, name="Notes"
    )
    enterprise_data_fixture.enable_enterprise()

    RoleAssignmentHandler().assign_role(
        subject=admin,
        workspace=workspace,
        role=Role.objects.get(uid="ADMIN"),
        scope=database,
    )
    RoleAssignmentHandler().assign_role(
        subject=exporter,
        workspace=workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=database,
    )

    model = table.get_model()
    RowHandler().force_create_rows(
        admin,
        table,
        [
            {
                name_field.db_column: "Ada",
                notes_field.db_column: "Protected",
            }
        ],
        model=model,
    )
    FieldPermissionsHandler.update_field_permissions(admin, notes_field, "ADMIN")

    storage = FileSystemStorage(location=tmp_path)
    with patch("baserow.core.storage.get_default_storage", return_value=storage):
        export_handler = ExportHandler()
        job = export_handler.create_pending_export_job(
            exporter,
            table,
            None,
            {"exporter_type": "csv", "export_charset": "utf-8"},
        )
        export_handler.run_export_job(job)
        export_path = ExportHandler.export_file_path(job.exported_file_name)
        with storage.open(export_path, "rb") as exported_file:
            contents = exported_file.read().decode("utf-8")

    assert contents == "\ufeffid,Name,Notes\r\n1,Ada,Protected\r\n"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_fields_with_permissions_can_be_excluded_from_forms(
    api_client, enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(
        table=table, name="text", primary=True
    )
    number_field = enterprise_data_fixture.create_number_field(
        table=table, name="number`"
    )
    model = table.get_model()
    form = enterprise_data_fixture.create_form_view(
        table=table, public=True, slug="a_public_slug"
    )
    enterprise_data_fixture.create_form_view_field_option(
        form, text_field, enabled=True, order=1, name="text"
    )
    enterprise_data_fixture.create_form_view_field_option(
        form, number_field, enabled=True, order=2, name="number"
    )

    enterprise_data_fixture.enable_enterprise()

    # With the default permissions, everything works the same as before
    FieldPermissionsHandler.update_field_permissions(user, text_field, "EDITOR")

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    rsp = api_client.get(url, format="json")
    assert rsp.status_code == HTTP_200_OK
    rsp_json = rsp.json()
    assert len(rsp_json["fields"]) == 2
    assert rsp_json["fields"][0]["field"]["id"] == text_field.id
    assert rsp_json["fields"][1]["field"]["id"] == number_field.id

    # Also submit a value for the text field works
    rsp = api_client.post(
        url,
        format="json",
        data={text_field.db_column: "some text", number_field.db_column: 1},
    )
    assert rsp.status_code == HTTP_200_OK
    submitted_row_id = rsp.json()["row_id"]
    submitted_row = model.objects.get(id=submitted_row_id)
    assert getattr(submitted_row, text_field.db_column) == "some text"
    assert getattr(submitted_row, number_field.db_column) == 1

    for i, role in enumerate(["BUILDER", "ADMIN", "NOBODY"]):
        FieldPermissionsHandler.update_field_permissions(
            user, text_field, role, allow_in_forms=False
        )

        url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
        rsp = api_client.get(url, format="json")
        assert rsp.status_code == HTTP_200_OK
        rsp_json = rsp.json()

        # The field is no longer present in the form
        assert len(rsp_json["fields"]) == 1
        assert rsp_json["fields"][0]["field"]["id"] == number_field.id

        # It's still possible to submit a value for other fields, but it will be ignored
        rsp = api_client.post(
            url,
            format="json",
            data={text_field.db_column: "some other text", number_field.db_column: i},
        )
        assert rsp.status_code == HTTP_200_OK
        submitted_row_id = rsp.json()["row_id"]
        submitted_row = model.objects.get(id=submitted_row_id)
        # The text field is ignored, only the number field is submitted
        assert getattr(submitted_row, text_field.db_column) is None
        assert getattr(submitted_row, number_field.db_column) == i

    # But if even nobody can change the data, it's not possible to submit a value
    # via a form if the setting is enabled
    FieldPermissionsHandler.update_field_permissions(
        user, text_field, "NOBODY", allow_in_forms=True
    )
    rsp = api_client.post(
        url,
        format="json",
        data={text_field.db_column: "nobody can edit me", number_field.db_column: 10},
    )
    assert rsp.status_code == HTTP_200_OK
    submitted_row_id = rsp.json()["row_id"]
    submitted_row = model.objects.get(id=submitted_row_id)
    assert getattr(submitted_row, text_field.db_column) == "nobody can edit me"
    assert getattr(submitted_row, number_field.db_column) == 10


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_if_license_expires_field_permissions_are_ignored(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    enterprise_data_fixture.enable_enterprise()
    model = table.get_model()

    (row,) = RowHandler().force_create_rows(user, table, [{}], model=model).created_rows

    def _assign_role(role):
        RoleAssignmentHandler().assign_role(
            subject=user,
            workspace=database.workspace,
            role=role,
            scope=database,
        )

    def _create_row_with_field_value(field, value):
        RowHandler().create_rows(
            user=user,
            table=table,
            rows_values=[{field.db_column: value}],
            model=model,
        )

    def _update_row_with_field_value(field, value):
        RowHandler().update_rows(
            user=user,
            table=table,
            rows_values=[{"id": row.id, field.db_column: value}],
            model=model,
        )

    def _import_rows_with_values(values):
        return RowHandler().import_rows(
            user=user,
            table=table,
            data=[values],
            configuration=None,
            validate=False,
        )

    FieldPermissionsHandler.update_field_permissions(user, text_field, "NOBODY")

    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "nobody")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "nobody")

    rows, _ = _import_rows_with_values([])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None

    enterprise_data_fixture.delete_all_licenses()

    _update_row_with_field_value(text_field, "nobody")
    _create_row_with_field_value(text_field, "nobody")

    rows, _ = _import_rows_with_values(["nobody"])
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "nobody"
