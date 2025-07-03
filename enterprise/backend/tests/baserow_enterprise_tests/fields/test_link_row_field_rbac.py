"""
This file tests the link row field in combination with RBAC enabled
"""
import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.formula import InvalidFormulaType
from baserow.core.exceptions import PermissionDenied
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_link_row_field_linked_to_table_with_no_access_created(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_with_access = data_fixture.create_database_table(user, database=database)
    table_with_no_access = data_fixture.create_database_table(user, database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    RoleAssignmentHandler().assign_role(
        user, workspace, role=no_access_role, scope=table_with_no_access
    )

    with pytest.raises(PermissionDenied):
        FieldHandler().create_field(
            user=user,
            table=table_with_access,
            type_name="link_row",
            name="link row",
            link_row_table=table_with_no_access,
        )

    with pytest.raises(PermissionDenied):
        FieldHandler().create_field(
            user=user,
            table=table_with_access,
            type_name="link_row",
            name="link row",
            link_row_table=table_with_no_access,
            has_related_field=False,
        )


@pytest.mark.django_db
def test_link_row_field_linked_to_table_with_no_access_updated(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_with_access = data_fixture.create_database_table(user, database=database)
    table_with_no_access = data_fixture.create_database_table(user, database=database)
    table_unrelated = data_fixture.create_database_table(user, database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    RoleAssignmentHandler().assign_role(
        user, workspace, role=no_access_role, scope=table_with_no_access
    )

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table_with_access,
        type_name="link_row",
        name="link row",
        link_row_table=table_unrelated,
    )

    with pytest.raises(PermissionDenied):
        FieldHandler().update_field(
            user=user,
            field=link_row_field.specific,
            link_row_table=table_with_no_access,
        )


@pytest.mark.django_db
def test_link_row_field_linked_to_table_with_no_access_deleted(data_fixture):
    user = data_fixture.create_user()
    user_with_access = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user_with_access])
    database = data_fixture.create_database_application(workspace=workspace)
    table_with_access = data_fixture.create_database_table(user, database=database)
    table_with_no_access = data_fixture.create_database_table(user, database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    RoleAssignmentHandler().assign_role(
        user, workspace, role=no_access_role, scope=table_with_no_access
    )

    link_row_field = FieldHandler().create_field(
        user=user_with_access,
        table=table_with_access,
        type_name="link_row",
        name="link row",
        link_row_table=table_with_no_access,
    )

    with pytest.raises(PermissionDenied):
        FieldHandler().delete_field(
            user=user,
            field=link_row_field.specific,
        )


@pytest.mark.django_db
def test_link_row_field_linked_to_table_with_no_access_from_inaccessible_to_accessable_table(
    data_fixture,
):
    user = data_fixture.create_user()
    user_with_access = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user_with_access])
    database = data_fixture.create_database_application(workspace=workspace)
    table_with_access = data_fixture.create_database_table(user, database=database)
    table_with_no_access = data_fixture.create_database_table(user, database=database)
    table_unrelated = data_fixture.create_database_table(user, database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    RoleAssignmentHandler().assign_role(
        user, workspace, role=no_access_role, scope=table_with_no_access
    )

    link_row_field = FieldHandler().create_field(
        user=user_with_access,
        table=table_with_access,
        type_name="link_row",
        name="link row",
        link_row_table=table_with_no_access,
    )

    with pytest.raises(PermissionDenied):
        FieldHandler().update_field(
            user=user,
            field=link_row_field.specific,
            link_row_table=table_unrelated,
        )


@pytest.mark.django_db
def test_cant_create_lookup_at_table_where_not_viewer_or_higher(
    data_fixture,
):
    user_without_access = data_fixture.create_user()
    user_with_access = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=user_with_access, members=[user_without_access]
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table_with_access = data_fixture.create_database_table(
        user_without_access, database=database
    )
    table_with_no_access = data_fixture.create_database_table(
        user_without_access, database=database
    )
    private_field_in_no_access_table = data_fixture.create_text_field(
        user_with_access, table=table_with_no_access, name="private"
    )
    no_access = Role.objects.get(uid="NO_ACCESS")
    viewer_role = Role.objects.get(uid="VIEWER")

    RoleAssignmentHandler().assign_role(
        user_without_access, workspace, role=no_access, scope=table_with_no_access
    )

    link_row_field = FieldHandler().create_field(
        user=user_with_access,
        table=table_with_access,
        type_name="link_row",
        name="link row",
        link_row_table=table_with_no_access,
    )

    with pytest.raises(InvalidFormulaType):
        FieldHandler().create_field(
            user=user_without_access,
            table=table_with_access,
            type_name="lookup",
            name="shouldnt be able to create",
            target_field_name=private_field_in_no_access_table.name,
            through_field_name=link_row_field.name,
        )

    # Now make them a viewer and it should work
    RoleAssignmentHandler().assign_role(
        user_without_access, workspace, role=viewer_role, scope=table_with_no_access
    )

    FieldHandler().create_field(
        user=user_without_access,
        table=table_with_access,
        type_name="lookup",
        name="now it will work",
        target_field_name=private_field_in_no_access_table.name,
        through_field_name=link_row_field.name,
    )


@pytest.mark.django_db
def test_cant_update_target_lookup_point_at_table_where_not_viewer_or_higher(
    data_fixture,
):
    user_without_access = data_fixture.create_user()
    user_with_access = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=user_with_access, members=[user_without_access]
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table_with_access = data_fixture.create_database_table(
        user_without_access, database=database
    )
    table_with_no_access = data_fixture.create_database_table(
        user_without_access, database=database
    )
    private_field_in_no_access_table = data_fixture.create_text_field(
        user_with_access, table=table_with_no_access, name="private"
    )
    other_private_field_in_no_access_table = data_fixture.create_text_field(
        user_with_access, table=table_with_no_access, name="other private"
    )
    no_access = Role.objects.get(uid="NO_ACCESS")
    viewer_role = Role.objects.get(uid="VIEWER")

    RoleAssignmentHandler().assign_role(
        user_without_access, workspace, role=no_access, scope=table_with_no_access
    )

    link_row_field = FieldHandler().create_field(
        user=user_with_access,
        table=table_with_access,
        type_name="link_row",
        name="link row",
        link_row_table=table_with_no_access,
    )
    lookup_field = FieldHandler().create_field(
        user=user_with_access,
        table=table_with_access,
        type_name="lookup",
        name="lookup",
        target_field_id=private_field_in_no_access_table.id,
        through_field_id=link_row_field.id,
    )

    with pytest.raises(InvalidFormulaType):
        # The user without the access tries to point the lookup at a different field
        FieldHandler().update_field(
            user=user_without_access,
            field=lookup_field,
            target_field_id=other_private_field_in_no_access_table.id,
            through_field_id=link_row_field.id,
        )

    # Now make them a viewer and it should work
    RoleAssignmentHandler().assign_role(
        user_without_access, workspace, role=viewer_role, scope=table_with_no_access
    )
    FieldHandler().update_field(
        user=user_without_access,
        field=lookup_field,
        target_field_name=other_private_field_in_no_access_table.name,
        through_field_name=link_row_field.name,
    )
