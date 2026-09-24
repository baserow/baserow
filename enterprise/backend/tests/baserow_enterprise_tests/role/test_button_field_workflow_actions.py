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


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_an_editor_is_not_shown_the_schema_of_a_table_they_cannot_read(
    data_fixture, enterprise_data_fixture, api_client
):
    """Being able to configure the button is not access to whatever table it
    was pointed at."""

    admin, admin_token = enterprise_data_fixture.create_user_and_token()
    editor, editor_token = enterprise_data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(users=[admin, editor])
    secret_database = data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    secret_table = data_fixture.create_database_table(
        user=admin, database=secret_database
    )
    data_fixture.create_text_field(table=secret_table, name="Salary")
    button_field = _button_with_an_action_targeting(
        data_fixture, admin, workspace, secret_table
    )

    RoleAssignmentHandler().assign_role(
        editor, workspace, role=Role.objects.get(uid="BUILDER")
    )
    RoleAssignmentHandler().assign_role(
        editor, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=secret_table
    )

    response = api_client.get(
        f"/api/database/field/{button_field.id}/workflow_actions/",
        HTTP_AUTHORIZATION=f"JWT {editor_token}",
    )

    assert response.status_code == 200
    (action,) = response.json()
    assert action["service"]["table_accessible"] is False
    assert action["service"]["schema"] is None
    assert action["service"]["context_data"] is None
    assert "Salary" not in response.content.decode()


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_the_schema_is_there_for_a_table_the_editor_can_read(
    data_fixture, enterprise_data_fixture, api_client
):
    admin = data_fixture.create_user()
    editor, editor_token = enterprise_data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(users=[admin, editor])
    target_database = data_fixture.create_database_application(
        user=admin, workspace=workspace
    )
    target_table = data_fixture.create_database_table(
        user=admin, database=target_database
    )
    data_fixture.create_text_field(table=target_table, name="Salary")
    button_field = _button_with_an_action_targeting(
        data_fixture, admin, workspace, target_table
    )

    RoleAssignmentHandler().assign_role(
        editor, workspace, role=Role.objects.get(uid="BUILDER")
    )

    response = api_client.get(
        f"/api/database/field/{button_field.id}/workflow_actions/",
        HTTP_AUTHORIZATION=f"JWT {editor_token}",
    )

    assert response.status_code == 200
    (action,) = response.json()
    assert action["service"]["table_accessible"] is True
    assert action["service"]["schema"] is not None
