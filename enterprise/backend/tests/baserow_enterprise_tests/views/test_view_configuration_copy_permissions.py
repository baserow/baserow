from django.test.utils import override_settings

import pytest

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import UpdateViewOperationType
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Operation
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_cannot_copy_filters_from_restricted_view(enterprise_data_fixture):
    """
    Restricted views hide their filters from users without the create filter
    permission, so those users must not be able to read them by copying them
    into another view either.
    """

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user2 = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)

    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=field, type="equal", value="secret"
    )
    dest_view = enterprise_data_fixture.create_grid_view(table=table)

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    editor_role = Role.objects.get(uid="EDITOR")
    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=builder_role, scope=View.objects.get(id=dest_view.id)
    )

    with pytest.raises(PermissionDenied):
        ViewHandler().copy_view_configuration(
            user2, restricted_view, dest_view, ["filters"]
        )

    assert dest_view.viewfilter_set.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_copy_filters_with_role_that_can_only_update_the_view(
    enterprise_data_fixture,
):
    """
    A role can allow updating a view without allowing filter creation, so the
    copy must check the category's own operations instead of only the view
    update operation.
    """

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user2 = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)

    source_view = enterprise_data_fixture.create_grid_view(table=table)
    enterprise_data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )
    dest_view = enterprise_data_fixture.create_grid_view(table=table)

    editor_role = Role.objects.get(uid="EDITOR")
    update_only_role = Role.objects.create(
        uid="view_update_only", name="View update only", workspace=workspace
    )
    update_only_role.operations.set(editor_role.operations.all())
    update_only_role.operations.add(
        Operation.objects.get(name=UpdateViewOperationType.type)
    )
    # The handler caches the roles per process, so it must pick up the newly
    # created custom role.
    RoleAssignmentHandler._init = False

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=builder_role, scope=View.objects.get(id=source_view.id)
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=update_only_role,
        scope=View.objects.get(id=dest_view.id),
    )

    with pytest.raises(PermissionDenied):
        ViewHandler().copy_view_configuration(
            user2, source_view, dest_view, ["filters"]
        )

    # The view settings category only needs the view update operation, so that
    # one is allowed for this role.
    ViewHandler().copy_view_configuration(
        user2, source_view, dest_view, ["view_settings"]
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_builder_can_copy_configuration(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user2 = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)

    source_view = enterprise_data_fixture.create_grid_view(table=table)
    enterprise_data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )
    dest_view = enterprise_data_fixture.create_grid_view(table=table)

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=builder_role, scope=workspace
    )

    ViewHandler().copy_view_configuration(user2, source_view, dest_view, ["filters"])

    assert dest_view.viewfilter_set.count() == 1
