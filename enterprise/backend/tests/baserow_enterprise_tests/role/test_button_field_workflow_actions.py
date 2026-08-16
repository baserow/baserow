from django.test import override_settings

import pytest

from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.exceptions import PermissionException
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def _button_with_an_action_targeting(data_fixture, user, workspace, target_table):
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=target_table
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )
    return button_field


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_a_viewer_cannot_read_the_actions_of_a_button_field(
    data_fixture, enterprise_data_fixture
):
    """An action carries the schema of the table it writes to, so reading the
    field is not enough to be shown a table the reader has no access to."""

    admin = data_fixture.create_user()
    viewer = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[admin, viewer])
    secret_database = data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    secret_table = data_fixture.create_database_table(
        user=admin, database=secret_database
    )
    button_field = _button_with_an_action_targeting(
        data_fixture, admin, workspace, secret_table
    )

    RoleAssignmentHandler().assign_role(
        viewer, workspace, role=Role.objects.get(uid="VIEWER")
    )

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().get_workflow_actions(viewer, button_field)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_a_builder_can_still_read_the_actions_of_a_button_field(
    data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[admin, builder])
    target_database = data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    target_table = data_fixture.create_database_table(
        user=admin, database=target_database
    )
    button_field = _button_with_an_action_targeting(
        data_fixture, admin, workspace, target_table
    )

    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="BUILDER")
    )

    actions = DatabaseWorkflowActionService().get_workflow_actions(
        builder, button_field
    )

    assert len(actions) == 1
