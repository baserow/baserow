from unittest.mock import patch

from django.urls import reverse

import pytest

from baserow.core.handler import CoreHandler
from baserow.ws.tasks import broadcast_to_permitted_users
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
@pytest.mark.workspace_search
def test_agent_search_respects_application_roles(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    visible = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Search agent"
    )
    hidden = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Search secret"
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Search database"
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(member, workspace, Role.objects.get(uid="VIEWER"))
    roles.assign_role(
        member,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=hidden.application_ptr,
    )
    url = reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(url, {"query": "Search"}, **headers)
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["results"]} == {
        visible.id,
        database.id,
    }
    result = next(
        item for item in response.json()["results"] if item["id"] == visible.id
    )
    assert result["type"] == "agent"
    assert result["subtitle"] == "Agents"


@pytest.mark.django_db
@pytest.mark.parametrize("application_type", ["agent", "database"])
def test_deleted_application_broadcast_respects_application_roles(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    django_capture_on_commit_callbacks,
    settings,
    application_type,
):
    owner = enterprise_data_fixture.create_user()
    granted = enterprise_data_fixture.create_user()
    denied = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=owner, members=[granted, denied]
    )
    if application_type == "agent":
        application = enterprise_data_fixture.create_agent_application(
            workspace=workspace
        )
    else:
        settings.FEATURE_FLAGS = []
        application = enterprise_data_fixture.create_database_application(
            workspace=workspace
        )
    roles = RoleAssignmentHandler()
    roles.assign_role(granted, workspace, Role.objects.get(uid="NO_ACCESS"))
    roles.assign_role(
        granted,
        workspace,
        Role.objects.get(uid="VIEWER"),
        scope=application.application_ptr,
    )
    roles.assign_role(denied, workspace, Role.objects.get(uid="BUILDER"))
    roles.assign_role(
        denied,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=application.application_ptr,
    )
    with patch("baserow.ws.signals.broadcast_to_permitted_users.delay") as queued:
        with django_capture_on_commit_callbacks(execute=True):
            CoreHandler().delete_application(owner, application)
    queued.assert_called_once()
    assert queued.call_args.kwargs == {}
    with patch("baserow.ws.tasks.broadcast_to_users") as broadcast:
        broadcast_to_permitted_users(*queued.call_args.args, **queued.call_args.kwargs)
    broadcast.assert_called_once()
    recipient_ids, payload = broadcast.call_args.args
    assert payload == {"type": "application_deleted", "application_id": application.id}
    assert owner.id in recipient_ids
    assert granted.id in recipient_ids
    assert denied.id not in recipient_ids
