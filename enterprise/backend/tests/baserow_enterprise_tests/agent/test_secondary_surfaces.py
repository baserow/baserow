from unittest.mock import patch

from django.urls import reverse

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.subjects import UserSubjectType
from baserow.core.trash.handler import TrashHandler
from baserow.ws.tasks import broadcast_application_created, broadcast_to_permitted_users
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment


@pytest.mark.django_db
def test_trash_contents_exclude_unreadable_agent_applications(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    hidden = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Secret agent"
    )
    visible = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Visible agent"
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(member, workspace, Role.objects.get(uid="BUILDER"))
    roles.assign_role(
        member,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=hidden.application_ptr,
    )
    CoreHandler().delete_application(owner, hidden)
    CoreHandler().delete_application(owner, visible)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(
        reverse("api:trash:contents", kwargs={"workspace_id": workspace.id}), **headers
    )
    assert response.status_code == 200
    assert [
        (item["trash_item_type"], item["trash_item_id"])
        for item in response.json()["results"]
    ] == [("application", visible.id)]
    assert "Secret" not in response.content.decode()
    response = api_client.get(reverse("api:trash:list"), **headers)
    assert response.status_code == 200
    assert [
        item["id"] for item in response.json()["workspaces"][0]["applications"]
    ] == [visible.id]
    assert "Secret" not in response.content.decode()


@pytest.mark.django_db
def test_disabled_agents_hidden_from_workspace_trash_and_structure(
    enterprise_data_fixture, api_client, settings
):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_application(
        user=user, name="Hidden agent"
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=agent.workspace, name="Visible database"
    )
    CoreHandler().delete_application(user, agent)
    CoreHandler().delete_application(user, database)
    settings.FEATURE_FLAGS = []
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(
        reverse("api:trash:contents", kwargs={"workspace_id": agent.workspace_id}),
        **headers,
    )
    assert response.status_code == 200
    assert [
        (item["trash_item_type"], item["trash_item_id"])
        for item in response.json()["results"]
    ] == [("application", database.id)]
    response = api_client.get(reverse("api:trash:list"), **headers)
    assert response.status_code == 200
    workspace = next(
        item
        for item in response.json()["workspaces"]
        if item["id"] == agent.workspace_id
    )
    assert [item["id"] for item in workspace["applications"]] == [database.id]


@pytest.mark.django_db
@pytest.mark.workspace_search
def test_agent_search_respects_application_roles_and_feature_flag(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles, settings
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
    settings.FEATURE_FLAGS = []
    response = api_client.get(url, {"query": "Search"}, **headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [database.id]


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post", "batch"])
def test_disabled_agent_application_roles_cannot_be_read_or_assigned(
    enterprise_data_fixture,
    api_client,
    enable_enterprise,
    synced_roles,
    settings,
    method,
):
    owner, token = enterprise_data_fixture.create_user_and_token()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    assignment = RoleAssignmentHandler().assign_role(
        member, workspace, Role.objects.get(uid="VIEWER"), scope=agent.application_ptr
    )
    settings.FEATURE_FLAGS = []
    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})
    payload = {"scope_id": agent.id, "scope_type": "application"}
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    if method == "get":
        response = api_client.get(url, payload, **headers)
    else:
        payload.update(
            {
                "subject_id": member.id,
                "subject_type": UserSubjectType.type,
                "role": "BUILDER",
            }
        )
        if method == "batch":
            url = reverse(
                "api:enterprise:role:batch", kwargs={"workspace_id": workspace.id}
            )
            payload = {"items": [payload]}
        response = api_client.post(url, payload, format="json", **headers)
    assert response.status_code == 403, response.json()
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assignment.refresh_from_db()
    assert assignment.role.uid == "VIEWER"
    assert (
        RoleAssignment.objects.filter(
            scope_id=agent.id, scope_type=assignment.scope_type
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_queued_agent_application_creation_hidden_after_feature_disabled(
    enterprise_data_fixture, settings
):
    agent = enterprise_data_fixture.create_agent_application(name="Secret agent")
    settings.FEATURE_FLAGS = []
    with patch("baserow.ws.tasks.broadcast_to_users_individual_payloads") as broadcast:
        broadcast_application_created(agent.id)
    broadcast.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("deleted", [True, False])
def test_queued_agent_application_events_hidden_after_feature_disabled(
    enterprise_data_fixture, settings, deleted
):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(user=user, name="Secret")
    if deleted:
        CoreHandler().delete_application(user, agent)
    settings.FEATURE_FLAGS = []
    with patch("baserow.ws.tasks.broadcast_to_users") as broadcast:
        broadcast_to_permitted_users(
            agent.workspace_id,
            "application.read",
            "application",
            agent.id,
            {"type": "application_deleted" if deleted else "application_updated"},
        )
    broadcast.assert_not_called()


@pytest.mark.django_db
def test_workspace_restored_broadcast_hides_disabled_agent_applications(
    enterprise_data_fixture, settings, django_capture_on_commit_callbacks
):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(user=user, name="Secret")
    database = enterprise_data_fixture.create_database_application(
        workspace=agent.workspace, name="Visible database"
    )
    TrashHandler.trash(user, agent.workspace, None, agent.workspace)
    settings.FEATURE_FLAGS = []
    with patch("baserow.ws.signals.broadcast_to_users") as broadcast:
        with django_capture_on_commit_callbacks(execute=True):
            TrashHandler.restore_item(user, "workspace", agent.workspace_id)
    broadcast.delay.assert_called_once()
    payload = broadcast.delay.call_args.args[1]
    assert payload["type"] == "group_restored"
    assert [application["id"] for application in payload["applications"]] == [
        database.id
    ]
    assert "Secret" not in str(payload)


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
