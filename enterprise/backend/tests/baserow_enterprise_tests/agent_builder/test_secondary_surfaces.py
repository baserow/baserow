from unittest.mock import patch

from django.urls import reverse

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.subjects import UserSubjectType
from baserow.core.trash.handler import TrashHandler
from baserow.ws.tasks import broadcast_application_created, broadcast_to_permitted_users
from baserow_enterprise.agent_builder.service import AgentService
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment


@pytest.mark.django_db
def test_trash_contents_exclude_unreadable_agents(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    visible = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Visible"
    )
    hidden = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Secret", order=2
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(member, workspace, Role.objects.get(uid="BUILDER"))
    roles.assign_role(
        member, workspace, Role.objects.get(uid="NO_ACCESS"), scope=hidden
    )
    AgentService().delete_agent(owner, visible.id)
    AgentService().delete_agent(owner, hidden.id)
    url = reverse("api:trash:contents", kwargs={"workspace_id": workspace.id})
    for params in [{}, {"application_id": builder.id}]:
        response = api_client.get(url, params, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200
        assert [item["trash_item_id"] for item in response.json()["results"]] == [
            visible.id
        ]
        assert "Secret" not in response.content.decode()


@pytest.mark.django_db
def test_trash_contents_exclude_unreadable_agent_builder_applications(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace, name="Secret team"
    )
    agent = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Secret agent"
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Visible database"
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(member, workspace, Role.objects.get(uid="BUILDER"))
    roles.assign_role(
        member,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=builder.application_ptr,
    )
    AgentService().delete_agent(owner, agent.id)
    CoreHandler().delete_application(owner, builder)
    CoreHandler().delete_application(owner, database)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(
        reverse("api:trash:contents", kwargs={"workspace_id": workspace.id}), **headers
    )
    assert response.status_code == 200
    assert [
        (item["trash_item_type"], item["trash_item_id"])
        for item in response.json()["results"]
    ] == [("application", database.id)]
    assert "Secret" not in response.content.decode()
    response = api_client.get(reverse("api:trash:list"), **headers)
    assert response.status_code == 200
    assert [
        item["id"] for item in response.json()["workspaces"][0]["applications"]
    ] == [database.id]
    assert "Secret" not in response.content.decode()


@pytest.mark.django_db
def test_disabled_agent_builder_hidden_from_workspace_trash_and_structure(
    enterprise_data_fixture, api_client, settings
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(
        user=user, name="Hidden team"
    )
    agent = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Hidden agent"
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=builder.workspace, name="Visible database"
    )
    AgentService().delete_agent(user, agent.id)
    CoreHandler().delete_application(user, builder)
    CoreHandler().delete_application(user, database)
    settings.FEATURE_FLAGS = []
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(
        reverse("api:trash:contents", kwargs={"workspace_id": builder.workspace_id}),
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
        if item["id"] == builder.workspace_id
    )
    assert [item["id"] for item in workspace["applications"]] == [database.id]


@pytest.mark.django_db
@pytest.mark.workspace_search
def test_disabled_agent_builder_hidden_from_workspace_search(
    enterprise_data_fixture, api_client, settings
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(
        user=user, name="Search team"
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=builder.workspace, name="Search database"
    )
    url = reverse(
        "api:search:workspace_search", kwargs={"workspace_id": builder.workspace_id}
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(url, {"query": "Search"}, **headers)
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["results"]} == {
        builder.id,
        database.id,
    }
    settings.FEATURE_FLAGS = []
    response = api_client.get(url, {"query": "Search"}, **headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [database.id]


@pytest.mark.django_db
def test_deleted_agent_realtime_recipients_keep_child_role_restrictions(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    granted = enterprise_data_fixture.create_user()
    denied = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=owner, members=[granted, denied]
    )
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    agent = enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    roles = RoleAssignmentHandler()
    roles.assign_role(granted, workspace, Role.objects.get(uid="NO_ACCESS"))
    roles.assign_role(granted, workspace, Role.objects.get(uid="VIEWER"), scope=agent)
    roles.assign_role(denied, workspace, Role.objects.get(uid="BUILDER"))
    roles.assign_role(denied, workspace, Role.objects.get(uid="NO_ACCESS"), scope=agent)
    AgentService().delete_agent(owner, agent.id)
    payload = {
        "type": "agent_builder_agent_deleted",
        "agent_id": agent.id,
        "agent_builder_id": agent.agent_builder_id,
    }
    with patch("baserow.ws.tasks.broadcast_to_users") as broadcast:
        broadcast_to_permitted_users(
            workspace.id,
            "agent_builder_agent.read",
            "agent_builder_agent",
            agent.id,
            payload,
            include_trash=True,
        )
    recipient_ids = broadcast.call_args.args[0]
    assert owner.id in recipient_ids
    assert granted.id in recipient_ids
    assert denied.id not in recipient_ids


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post", "batch"])
def test_disabled_agent_child_roles_cannot_be_read_or_assigned(
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
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    agent = enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    assignment = RoleAssignmentHandler().assign_role(
        member, workspace, Role.objects.get(uid="VIEWER"), scope=agent
    )
    settings.FEATURE_FLAGS = []
    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})
    payload = {"scope_id": agent.id, "scope_type": "agent_builder_agent"}
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
def test_queued_application_creation_does_not_broadcast_after_feature_is_disabled(
    enterprise_data_fixture, settings
):
    user = enterprise_data_fixture.create_user()
    builder = enterprise_data_fixture.create_agent_builder_application(
        user=user, name="Secret team"
    )
    settings.FEATURE_FLAGS = []
    with patch("baserow.ws.tasks.broadcast_to_users_individual_payloads") as broadcast:
        broadcast_application_created(builder.id)
    broadcast.assert_not_called()


@pytest.mark.django_db
def test_queued_agent_creation_does_not_broadcast_after_feature_is_disabled(
    enterprise_data_fixture, settings
):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_definition(
        user=user, name="Secret agent"
    )
    payload = {
        "type": "agent_builder_agent_created",
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "agent_builder_id": agent.agent_builder_id,
            "order": agent.order,
        },
    }
    settings.FEATURE_FLAGS = []
    with patch("baserow.ws.tasks.broadcast_to_users") as broadcast:
        broadcast_to_permitted_users(
            agent.agent_builder.workspace_id,
            "agent_builder_agent.read",
            "agent_builder_agent",
            agent.id,
            payload,
        )
    broadcast.assert_not_called()


@pytest.mark.django_db
def test_workspace_restored_broadcast_hides_disabled_agent_builders(
    enterprise_data_fixture, settings, django_capture_on_commit_callbacks
):
    user = enterprise_data_fixture.create_user()
    builder = enterprise_data_fixture.create_agent_builder_application(
        user=user, name="Secret team"
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=builder.workspace, name="Visible database"
    )
    TrashHandler.trash(user, builder.workspace, None, builder.workspace)
    settings.FEATURE_FLAGS = []
    with patch("baserow.ws.signals.broadcast_to_users") as broadcast:
        with django_capture_on_commit_callbacks(execute=True):
            TrashHandler.restore_item(user, "workspace", builder.workspace_id)
    broadcast.delay.assert_called_once()
    payload = broadcast.delay.call_args.args[1]
    assert payload["type"] == "group_restored"
    assert [application["id"] for application in payload["applications"]] == [
        database.id
    ]
    assert "Secret team" not in str(payload)


@pytest.mark.django_db
def test_deleted_agent_builder_broadcast_preserves_application_role_restrictions(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    django_capture_on_commit_callbacks,
):
    owner = enterprise_data_fixture.create_user()
    granted = enterprise_data_fixture.create_user()
    denied = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=owner, members=[granted, denied]
    )
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(granted, workspace, Role.objects.get(uid="NO_ACCESS"))
    roles.assign_role(
        granted,
        workspace,
        Role.objects.get(uid="VIEWER"),
        scope=builder.application_ptr,
    )
    roles.assign_role(denied, workspace, Role.objects.get(uid="BUILDER"))
    roles.assign_role(
        denied,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=builder.application_ptr,
    )
    with patch("baserow.ws.signals.broadcast_to_permitted_users.delay") as queued:
        with django_capture_on_commit_callbacks(execute=True):
            CoreHandler().delete_application(owner, builder)
    queued.assert_called_once()
    assert queued.call_args.kwargs["include_trash"] is True
    with patch("baserow.ws.tasks.broadcast_to_users") as broadcast:
        broadcast_to_permitted_users(*queued.call_args.args, **queued.call_args.kwargs)
    broadcast.assert_called_once()
    recipient_ids, payload = broadcast.call_args.args
    assert payload == {"type": "application_deleted", "application_id": builder.id}
    assert owner.id in recipient_ids
    assert granted.id in recipient_ids
    assert denied.id not in recipient_ids
