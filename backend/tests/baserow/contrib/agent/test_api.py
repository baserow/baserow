from django.urls import reverse

import pytest

from baserow.contrib.agent.models import AgentApplication
from baserow.core.action.models import Action
from baserow.core.actions import (
    CreateApplicationActionType,
    DeleteApplicationActionType,
    UpdateApplicationActionType,
)
from baserow.core.models import Agent, Application
from baserow.core.registries import (
    application_type_registry,
    object_scope_type_registry,
    subject_type_registry,
)
from baserow.core.trash.registries import trash_item_type_registry


def application_url(application):
    return reverse("api:applications:item", kwargs={"application_id": application.id})


@pytest.mark.django_db
@pytest.mark.parametrize("init_with_data", [True, False])
def test_agent_application_crud_uses_core_actions(
    data_fixture, api_client, init_with_data
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Support agent", "type": "agent", "init_with_data": init_with_data},
        format="json",
        **headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "agent"
    assert "agents" not in response.json()
    application = AgentApplication.objects.get(id=response.json()["id"])
    assert Application.objects.get(id=application.id).specific == application
    assert application.get_parent() == workspace
    assert object_scope_type_registry.get_by_model(application).type == "application"
    assert (
        Action.objects.get(type=CreateApplicationActionType.type).params[
            "application_type"
        ]
        == "agent"
    )

    response = api_client.get(application_url(application), **headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Support agent"
    response = api_client.patch(
        application_url(application),
        {"name": "Research agent"},
        format="json",
        **headers,
    )
    assert response.status_code == 200
    application.refresh_from_db()
    assert application.name == "Research agent"
    assert Action.objects.filter(type=UpdateApplicationActionType.type).exists()

    response = api_client.delete(application_url(application), **headers)
    assert response.status_code == 204
    assert not AgentApplication.objects.filter(id=application.id).exists()
    assert Action.objects.filter(type=DeleteApplicationActionType.type).exists()
    assert api_client.get(application_url(application), **headers).status_code == 404


@pytest.mark.django_db
def test_agents_use_workspace_application_ordering(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})
    first = api_client.post(
        url, {"name": "Writer", "type": "agent"}, format="json", **headers
    ).json()
    second = api_client.post(
        url, {"name": "Researcher", "type": "agent"}, format="json", **headers
    ).json()
    assert first["order"] == 2
    assert second["order"] == 3
    assert [item["id"] for item in api_client.get(url, **headers).json()] == [
        database.id,
        first["id"],
        second["id"],
    ]
    response = api_client.post(
        reverse("api:applications:order", kwargs={"workspace_id": workspace.id}),
        {"application_ids": [second["id"], database.id, first["id"]]},
        format="json",
        **headers,
    )
    assert response.status_code == 204
    assert [item["id"] for item in api_client.get(url, **headers).json()] == [
        second["id"],
        database.id,
        first["id"],
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", " ", None, "x" * 161])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_agent_application_name_validation_does_not_write(
    data_fixture, api_client, name, method
):
    user, token = data_fixture.create_user_and_token()
    agent = data_fixture.create_agent_application(user=user, name="Original")
    url = (
        reverse("api:applications:list", kwargs={"workspace_id": agent.workspace_id})
        if method == "post"
        else application_url(agent)
    )
    response = getattr(api_client, method)(
        url,
        {"name": name, "type": "agent"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert AgentApplication.objects.count() == 1
    agent.refresh_from_db()
    assert agent.name == "Original"
    assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
def test_agent_application_crud_requires_workspace_membership(
    data_fixture, api_client, method
):
    _, token = data_fixture.create_user_and_token()
    agent = data_fixture.create_agent_application(name="Private")
    url = (
        reverse("api:applications:list", kwargs={"workspace_id": agent.workspace_id})
        if method == "post"
        else application_url(agent)
    )
    response = getattr(api_client, method)(
        url,
        {"name": "Changed", "type": "agent"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    agent.refresh_from_db()
    assert agent.name == "Private"
    assert not agent.trashed
    assert AgentApplication.objects.count() == 1
    assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
def test_agent_application_crud_requires_authentication(
    data_fixture, api_client, method
):
    agent = data_fixture.create_agent_application()
    url = (
        reverse("api:applications:list", kwargs={"workspace_id": agent.workspace_id})
        if method == "post"
        else application_url(agent)
    )
    response = getattr(api_client, method)(
        url, {"name": "Changed", "type": "agent"}, format="json"
    )
    assert response.status_code == 401
    assert not Action.objects.exists()


@pytest.mark.django_db
def test_template_preview_lists_agent_applications_and_is_read_only(
    data_fixture, api_client
):
    _, token = data_fixture.create_user_and_token()
    template = data_fixture.create_template()
    agent = data_fixture.create_agent_application(
        workspace=template.workspace, name="Template agent"
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(
        reverse("api:applications:list", kwargs={"workspace_id": agent.workspace_id})
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [agent.id]
    assert response.json()[0]["name"] == "Template agent"
    assert (
        api_client.patch(
            application_url(agent), {"name": "Changed"}, format="json", **headers
        ).status_code
        == 400
    )
    assert api_client.delete(application_url(agent), **headers).status_code == 400
    agent.refresh_from_db()
    assert agent.name == "Template agent"
    assert not agent.trashed


@pytest.mark.django_db
@pytest.mark.parametrize("init_with_data", [True, False])
def test_agent_application_creation_disabled_by_feature_flag(
    data_fixture, api_client, settings, init_with_data
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    settings.FEATURE_FLAGS = []
    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Researcher", "type": "agent", "init_with_data": init_with_data},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 403
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert not AgentApplication.objects.exists()
    assert list(Application.objects.filter(workspace=workspace)) == [
        database.application_ptr
    ]
    assert not Action.objects.exists()


@pytest.mark.django_db
def test_agent_application_is_distinct_from_execution_subject(data_fixture):
    application = data_fixture.create_agent_application()
    subject = Agent.objects.create(
        workspace=application.workspace, name="Execution actor"
    )
    assert isinstance(subject, Agent)
    assert not isinstance(application, Agent)
    assert application_type_registry.get_by_model(application).type == "agent"
    assert subject_type_registry.get_by_model(subject).type == "core.Agent"
    assert trash_item_type_registry.get_by_model(application).type == "application"
    assert trash_item_type_registry.get_by_model(subject).type == "agent"
