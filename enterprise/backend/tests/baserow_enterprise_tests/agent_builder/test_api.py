from django.urls import reverse

import pytest

from baserow.core.action.models import Action
from baserow.core.actions import (
    CreateApplicationActionType,
    DeleteApplicationActionType,
    UpdateApplicationActionType,
)
from baserow_enterprise.agent_builder.actions import (
    CreateAgentActionType,
    DeleteAgentActionType,
    OrderAgentsActionType,
    UpdateAgentActionType,
)
from baserow_enterprise.agent_builder.models import AgentBuilder, AgentDefinition


def agents_url(agent_builder):
    return reverse(
        "api:agent_builder:agents", kwargs={"agent_builder_id": agent_builder.id}
    )


def agent_url(agent):
    return reverse("api:agent_builder:agent", kwargs={"agent_id": agent.id})


def application_url(application):
    return reverse("api:applications:item", kwargs={"application_id": application.id})


@pytest.mark.django_db
def test_agent_builder_application_crud_uses_core_actions(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Support team", "type": "agent_builder"},
        format="json",
        **headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "agent_builder"
    assert "agents" not in response.json()
    builder = AgentBuilder.objects.get(id=response.json()["id"])
    assert not builder.agents.exists()
    assert (
        Action.objects.get(type=CreateApplicationActionType.type).params[
            "application_type"
        ]
        == "agent_builder"
    )

    response = api_client.get(application_url(builder), **headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Support team"

    response = api_client.patch(
        application_url(builder), {"name": "Research team"}, format="json", **headers
    )
    assert response.status_code == 200
    builder.refresh_from_db()
    assert builder.name == "Research team"
    assert Action.objects.filter(type=UpdateApplicationActionType.type).exists()

    response = api_client.delete(application_url(builder), **headers)
    assert response.status_code == 204
    assert not AgentBuilder.objects.filter(id=builder.id).exists()
    assert Action.objects.filter(type=DeleteApplicationActionType.type).exists()


@pytest.mark.django_db
def test_empty_agent_crud_persists_names_order_and_actions(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        agents_url(builder), {"name": "Writer"}, format="json", **headers
    )
    assert response.status_code == 200
    first = AgentDefinition.objects.get(id=response.json()["id"])
    assert response.json()["agent_builder_id"] == builder.id
    assert first.name == "Writer"
    assert first.order == 1
    assert first.created_on is not None
    assert first.updated_on is not None
    assert Action.objects.filter(type=CreateAgentActionType.type).count() == 1

    response = api_client.post(
        agents_url(builder), {"name": "Researcher"}, format="json", **headers
    )
    assert response.status_code == 200
    second = AgentDefinition.objects.get(id=response.json()["id"])
    assert second.order == 2
    response = api_client.get(agents_url(builder), **headers)
    assert response.status_code == 200
    assert [agent["id"] for agent in response.json()] == [first.id, second.id]

    response = api_client.get(agent_url(first), **headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Writer"
    response = api_client.patch(
        agent_url(first), {"name": "Editor"}, format="json", **headers
    )
    assert response.status_code == 200
    first.refresh_from_db()
    assert first.name == "Editor"
    assert (
        Action.objects.get(type=UpdateAgentActionType.type).params["agent_id"]
        == first.id
    )

    response = api_client.delete(agent_url(first), **headers)
    assert response.status_code == 204
    assert not AgentDefinition.objects.filter(id=first.id).exists()
    assert AgentDefinition.objects_and_trash.get(id=first.id).trashed
    assert (
        Action.objects.get(type=DeleteAgentActionType.type).params["agent_id"]
        == first.id
    )
    assert api_client.get(agent_url(first), **headers).status_code == 404
    assert [
        agent["id"] for agent in api_client.get(agents_url(builder), **headers).json()
    ] == [second.id]


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", " ", None, "x" * 256])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_agent_name_validation_does_not_write(
    enterprise_data_fixture, api_client, name, method
):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_definition(user=user, name="Original")
    url = agents_url(agent.agent_builder) if method == "post" else agent_url(agent)
    response = getattr(api_client, method)(
        url, {"name": name}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert AgentDefinition.objects.count() == 1
    agent.refresh_from_db()
    assert agent.name == "Original"
    assert Action.objects.count() == 0


@pytest.mark.django_db
def test_agent_update_cannot_move_agent_to_another_builder(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_definition(user=user, name="Original")
    other = enterprise_data_fixture.create_agent_builder_application(user=user)
    response = api_client.patch(
        agent_url(agent),
        {"name": "Renamed", "agent_builder_id": other.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    agent.refresh_from_db()
    assert agent.name == "Renamed"
    assert agent.agent_builder_id != other.id


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
def test_agent_crud_requires_workspace_membership(
    enterprise_data_fixture, api_client, method
):
    _, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_definition(name="Private")
    url = agents_url(agent.agent_builder) if method == "post" else agent_url(agent)
    response = getattr(api_client, method)(
        url, {"name": "Changed"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 401
    assert response.json()["error"] == "PERMISSION_DENIED"
    agent.refresh_from_db()
    assert agent.name == "Private"
    assert not agent.trashed
    assert AgentDefinition.objects.count() == 1
    assert Action.objects.count() == 0


@pytest.mark.django_db
def test_agent_crud_requires_authentication(enterprise_data_fixture, api_client):
    agent = enterprise_data_fixture.create_agent_definition()
    assert api_client.get(agents_url(agent.agent_builder)).status_code == 401
    assert (
        api_client.post(agents_url(agent.agent_builder), {"name": "New"}).status_code
        == 401
    )
    assert api_client.get(agent_url(agent)).status_code == 401
    assert api_client.patch(agent_url(agent), {"name": "New"}).status_code == 401
    assert api_client.delete(agent_url(agent)).status_code == 401


@pytest.mark.django_db
def test_agent_endpoints_reject_other_application_types(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)
    url = reverse("api:agent_builder:agents", kwargs={"agent_builder_id": database.id})
    assert api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}").status_code == 404
    response = api_client.post(
        url, {"name": "Wrong"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 404
    assert not AgentDefinition.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
def test_agent_crud_disabled_by_feature_flag(
    enterprise_data_fixture, api_client, settings, method
):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_definition(user=user, name="Original")
    settings.FEATURE_FLAGS = []
    url = agents_url(agent.agent_builder) if method == "post" else agent_url(agent)
    response = getattr(api_client, method)(
        url, {"name": "Changed"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 403
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    agent.refresh_from_db()
    assert agent.name == "Original"
    assert not agent.trashed
    assert AgentDefinition.objects.count() == 1
    assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "patch", "delete", "duplicate", "post"])
def test_generic_agent_builder_crud_disabled_by_feature_flag(
    enterprise_data_fixture, api_client, settings, method
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    settings.FEATURE_FLAGS = []
    if method == "post":
        url = reverse(
            "api:applications:list", kwargs={"workspace_id": builder.workspace_id}
        )
        payload = {"name": "Changed", "type": "agent_builder"}
    elif method == "duplicate":
        url = reverse(
            "api:applications:async_duplicate", kwargs={"application_id": builder.id}
        )
        method = "post"
        payload = {}
    else:
        url = application_url(builder)
        payload = {"name": "Changed"}
    response = getattr(api_client, method)(
        url, payload, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 403
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert AgentBuilder.objects.count() == 1
    builder.refresh_from_db()
    assert not builder.trashed
    assert not Action.objects.exists()


@pytest.mark.django_db
def test_application_lists_hide_agent_builders_when_disabled(
    enterprise_data_fixture, api_client, settings
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    database = enterprise_data_fixture.create_database_application(
        workspace=builder.workspace
    )
    enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    settings.FEATURE_FLAGS = []
    for url in [
        reverse("api:applications:list", kwargs={"workspace_id": builder.workspace_id}),
        reverse("api:applications:list"),
    ]:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200
        assert [application["id"] for application in response.json()] == [database.id]


@pytest.mark.django_db
def test_reorder_agents_and_reject_agents_from_other_builders(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    first = enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    second = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=2
    )
    foreign = enterprise_data_fixture.create_agent_definition(user=user)
    url = reverse("api:agent_builder:order", kwargs={"agent_builder_id": builder.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        url, {"agent_ids": [second.id, first.id]}, format="json", **headers
    )
    assert response.status_code == 204
    assert list(builder.agents.values_list("id", flat=True)) == [second.id, first.id]
    assert Action.objects.filter(type=OrderAgentsActionType.type).count() == 1

    response = api_client.post(
        url, {"agent_ids": [foreign.id, first.id]}, format="json", **headers
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_AGENT_NOT_IN_AGENT_BUILDER"
    assert list(builder.agents.values_list("id", flat=True)) == [second.id, first.id]
    assert Action.objects.filter(type=OrderAgentsActionType.type).count() == 1


@pytest.mark.django_db
def test_new_agents_do_not_reuse_trashed_agent_order(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=4, trashed=True
    )
    response = api_client.post(
        agents_url(builder),
        {"name": "New"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert response.json()["order"] == 5


@pytest.mark.django_db
def test_reorder_agents_rejects_duplicate_ids(enterprise_data_fixture, api_client):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_definition(user=user)
    response = api_client.post(
        reverse(
            "api:agent_builder:order",
            kwargs={"agent_builder_id": agent.agent_builder_id},
        ),
        {"agent_ids": [agent.id, agent.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert not Action.objects.exists()
    agent.refresh_from_db()
    assert agent.order == 1


@pytest.mark.django_db
def test_reorder_agents_repairs_duplicate_numeric_order_values(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    first = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=1
    )
    second = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=1
    )
    response = api_client.post(
        reverse("api:agent_builder:order", kwargs={"agent_builder_id": builder.id}),
        {"agent_ids": [second.id, first.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    assert list(builder.agents.values_list("id", flat=True)) == [second.id, first.id]
    assert len(set(builder.agents.values_list("order", flat=True))) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("enabled", [True, False])
def test_template_preview_allows_only_reading_agents_and_respects_feature_flag(
    enterprise_data_fixture, api_client, settings, enabled
):
    _, token = enterprise_data_fixture.create_user_and_token()
    template = enterprise_data_fixture.create_template()
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=template.workspace
    )
    agent = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Template agent"
    )
    settings.FEATURE_FLAGS = ["agent-builder"] if enabled else []
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.get(agents_url(builder), **headers)
    assert response.status_code == (200 if enabled else 403)
    if enabled:
        assert [item["id"] for item in response.json()] == [agent.id]
    response = api_client.get(agent_url(agent), **headers)
    assert response.status_code == (200 if enabled else 403)
    if enabled:
        assert response.json()["name"] == "Template agent"
    assert api_client.post(
        agents_url(builder), {"name": "New"}, format="json", **headers
    ).status_code == (401 if enabled else 403)
    assert api_client.patch(
        agent_url(agent), {"name": "Changed"}, format="json", **headers
    ).status_code == (401 if enabled else 403)
    assert api_client.delete(agent_url(agent), **headers).status_code == (
        401 if enabled else 403
    )
    agent.refresh_from_db()
    assert agent.name == "Template agent"
    assert not agent.trashed
    assert AgentDefinition.objects.count() == 1
    assert not Action.objects.exists()


@pytest.mark.django_db
def test_agent_order_endpoint_disabled_by_feature_flag(
    enterprise_data_fixture, api_client, settings
):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_definition(user=user)
    settings.FEATURE_FLAGS = []
    response = api_client.post(
        reverse(
            "api:agent_builder:order",
            kwargs={"agent_builder_id": agent.agent_builder_id},
        ),
        {"agent_ids": [agent.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 403
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert not Action.objects.exists()
