from copy import deepcopy
from uuid import uuid4

from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

import pytest

from baserow.contrib.agent.action_tools.actions import (
    CreateAgentActionActionType,
    UpdateAgentActionActionType,
)
from baserow.contrib.agent.action_tools.exceptions import AgentActionDoesNotExist
from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.action_tools.trash_types import AgentActionTrashableItemType
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentAction
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.integrations.core.service_types import CoreSMTPEmailServiceType
from baserow.core.exceptions import FeatureDisabledException
from baserow.core.handler import CoreHandler
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.object_scopes import ApplicationObjectScopeType
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.services.models import Service
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.handler import TrashHandler

from ..utils import agent_url


def action_url(agent, action):
    return agent_url(agent, "actions:item", action_id=action.id)


@pytest.mark.django_db
def test_create_seeds_independent_inputs_and_audits_only_identifiers(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    audit = mocker.spy(CreateAgentActionActionType, "send_action_done_signal")
    dispatch = mocker.patch.object(CoreSMTPEmailServiceType, "dispatch")
    bodies = []
    for _ in range(2):
        response = api_client.post(
            agent_url(agent, "actions:list"), {"type": "smtp_email"}
        )
        assert response.status_code == 200, response.json()
        bodies.append(response.json())
    first, second = bodies
    assert [item["name"] for item in bodies] == ["send_email", "send_email_2"]
    assert first["enabled"] is True and first["ask_first"] is False
    assert first["description"]
    assert [(i["name"], i["type"], i["required"]) for i in first["inputs"]] == [
        ("to_email", "email", True),
        ("subject", "string", True),
        ("body", "string", True),
    ]
    assert {i["id"] for i in first["inputs"]}.isdisjoint(
        i["id"] for i in second["inputs"]
    )
    for field, item in zip(("to_emails", "subject", "body"), first["inputs"]):
        assert first["service"][field]["formula"] == f"get('tool_input.{item['id']}')"
    assert set(audit.call_args.args[1]) == {"agent_id", "action_id", "action_type"}
    dispatch.assert_not_called()


@pytest.mark.django_db
def test_partial_service_create_and_updates_preserve_input_bindings(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    integration = data_fixture.create_smtp_integration(application=agent)
    response = api_client.post(
        agent_url(agent, "actions:list"),
        {
            "type": "smtp_email",
            "service": {
                "integration_id": integration.id,
                "use_instance_smtp_settings": False,
            },
        },
    )
    assert response.status_code == 200, response.json()
    action = AgentAction.objects.get()
    original = response.json()
    assert all(
        original["service"][field]["formula"]
        for field in ("to_emails", "subject", "body")
    )
    audit = mocker.spy(UpdateAgentActionActionType, "send_action_done_signal")
    response = api_client.patch(action_url(agent, action), {"service": {}})
    assert response.status_code == 200, response.json()
    assert response.json() == original
    audit.assert_not_called()
    inputs = deepcopy(original["inputs"])
    inputs[0]["name"] = "recipient"
    response = api_client.patch(
        action_url(agent, action), {"inputs": inputs, "name": "welcome_email"}
    )
    assert response.status_code == 200, response.json()
    assert response.json()["service"] == original["service"]
    assert response.json()["inputs"][0]["id"] == original["inputs"][0]["id"]
    assert set(audit.call_args.args[1]["changed_fields"]) == {"name", "inputs"}
    response = api_client.patch(action_url(agent, action), {"inputs": inputs[1:]})
    assert response.json()["errors"]["to_emails"] == "invalid"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "has spaces"},
        {"name": "create_rows"},
        {"name": "web_search"},
        {"name": "mcp12_search"},
        {
            "inputs": [
                {
                    "id": str(uuid4()),
                    "name": "recipient",
                    "type": "unknown",
                    "required": True,
                }
            ]
        },
        {"service": {"type": "http_request"}},
        {
            "service": {
                "subject": {
                    "formula": "get('trigger.triggered_at')",
                    "mode": "advanced",
                    "version": "0.1",
                }
            }
        },
    ],
)
def test_api_rejects_invalid_configuration(data_fixture, api_client, api_user, payload):
    agent = data_fixture.create_agent_application(user=api_user)
    action = data_fixture.create_agent_action(agent=agent)
    response = api_client.patch(action_url(agent, action), payload)
    assert response.status_code == 400, response.json()
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_duplicate_names_and_unregistered_types_are_rejected(
    data_fixture, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    action = data_fixture.create_agent_action(agent=agent)
    response = api_client.post(
        agent_url(agent, "actions:list"), {"type": "smtp_email", "name": action.name}
    )
    assert response.status_code == 400
    assert "name" in response.json()["detail"]
    for type_name in ("http_request", "periodic", "unknown"):
        response = api_client.post(
            agent_url(agent, "actions:list"), {"type": type_name}
        )
        assert response.status_code == 400
        assert response.json()["error"] == "ERROR_AGENT_ACTION_TYPE_NOT_AVAILABLE"
    assert AgentAction.objects.count() == 1


def call(name, user, agent, action):
    service = AgentActionService()
    return {
        "list": lambda: service.list_actions(user, agent.id),
        "get": lambda: service.get_action(user, agent.id, action.id),
        "create": lambda: service.create_action(user, agent.id, "smtp_email"),
        "update": lambda: service.update_action(
            user, agent.id, action.id, enabled=False
        ),
        "delete": lambda: service.delete_action(user, agent.id, action.id),
    }[name]()


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["list", "get", "create", "update", "delete"])
def test_each_call_checks_operations_on_owning_agent(data_fixture, mocker, name):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    action = data_fixture.create_agent_action(agent=agent)
    check = mocker.spy(CoreHandler, "check_multiple_permissions")
    call(name, user, agent, action)
    expected = [ReadAgentConfigurationOperationType.type]
    if name not in ("list", "get"):
        expected.insert(0, UpdateApplicationOperationType.type)
    assert [
        (permission.operation_name, permission.context.id)
        for args, _ in check.call_args_list
        for permission in args[1]
    ] == [(operation, agent.id) for operation in expected]


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["create", "update", "delete"])
def test_writes_need_feature_flag(data_fixture, settings, name):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    action = data_fixture.create_agent_action(agent=agent)
    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        call(name, user, agent, action)
    assert AgentAction.objects.filter(id=action.id, enabled=True).exists()


@pytest.mark.django_db
def test_action_and_integration_cannot_cross_agent_boundary(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    other = data_fixture.create_agent_application(
        user=api_user, workspace=agent.workspace
    )
    action = data_fixture.create_agent_action(agent=agent)
    foreign = data_fixture.create_smtp_integration(application=other)
    response = api_client.patch(action_url(other, action), {"name": "hidden"})
    assert response.status_code == 404
    for integration_id in (foreign.id, 99999999):
        response = api_client.patch(
            action_url(agent, action),
            {
                "service": {
                    "integration_id": integration_id,
                    "use_instance_smtp_settings": False,
                }
            },
        )
        assert response.status_code == 400, response.json()
        assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    integration = data_fixture.create_smtp_integration(application=agent)
    check = mocker.spy(CoreHandler, "check_permissions")
    response = api_client.patch(
        action_url(agent, action),
        {
            "service": {
                "integration_id": integration.id,
                "use_instance_smtp_settings": False,
            }
        },
    )
    assert response.status_code == 200, response.json()
    assert any(
        args[2] == ReadIntegrationOperationType.type
        and kwargs["context"].id == integration.id
        for args, kwargs in check.call_args_list
    )


@pytest.mark.django_db
def test_trash_restore_collision_and_deletion_leave_approval_unchanged(data_fixture):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    action = data_fixture.create_agent_action(agent=agent)
    conversation = data_fixture.create_agent_conversation(agent=agent, user=user)
    approval = data_fixture.create_agent_tool_approval(
        conversation=conversation, tool_name=action.name
    )
    approval_values = {
        field.attname: getattr(approval, field.attname)
        for field in approval._meta.fields
    }
    service_id = action.service_id
    AgentActionService().delete_action(user, agent.id, action.id)
    assert Service.trash.filter(id=service_id).exists()
    with pytest.raises(AgentActionDoesNotExist):
        AgentActionHandler().get_action(action.id)
    replacement = data_fixture.create_agent_action(agent=agent)
    TrashHandler.restore_item(user, AgentActionTrashableItemType.type, action.id)
    action.refresh_from_db()
    assert action.name == "send_email_2" and replacement.name == "send_email"
    assert Service.objects.filter(id=service_id).exists()
    AgentActionService().delete_action(user, agent.id, action.id)
    TrashHandler.permanently_delete(action)
    assert not Service.objects_and_trash.filter(id=service_id).exists()
    approval.refresh_from_db()
    assert {
        field.attname: getattr(approval, field.attname)
        for field in approval._meta.fields
    } == approval_values
    agent.delete()
    assert not Service.objects_and_trash.filter(id=replacement.service_id).exists()


@pytest.mark.django_db
def test_configuration_events_only_reach_configuration_readers(
    data_fixture, mocker, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    user.web_socket_id = "acting-session"
    agent = data_fixture.create_agent_application(user=user)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_permitted_users.delay"
    )
    service = AgentActionService()
    with django_capture_on_commit_callbacks(execute=True):
        action = service.create_action(user, agent.id, "smtp_email")
        service.update_action(user, agent.id, action.id, name="welcome_email")
        service.delete_action(user, agent.id, action.id)
    assert [args[4]["type"] for args, _ in broadcast.call_args_list] == [
        "agent_action_created",
        "agent_action_updated",
        "agent_action_deleted",
    ]
    for args, kwargs in broadcast.call_args_list:
        assert args[:4] == (
            agent.workspace_id,
            ReadAgentConfigurationOperationType.type,
            ApplicationObjectScopeType.type,
            agent.id,
        )
        assert args[4]["agent_id"] == agent.id
        assert kwargs["ignore_web_socket_id"] == user.web_socket_id
    assert broadcast.call_args.args[4]["action_id"] == action.id


@pytest.mark.django_db
def test_configuration_offers_only_registered_available_actions(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    assert api_client.get(agent_url(agent, "configuration")).json()[
        "available_action_types"
    ] == ["smtp_email"]
    mocker.patch.object(CoreSMTPEmailServiceType, "is_deactivated", return_value=True)
    assert (
        api_client.get(agent_url(agent, "configuration")).json()[
            "available_action_types"
        ]
        == []
    )


@pytest.mark.django_db
@override_settings(BASEROW_AGENT_MAX_ACTIONS_PER_AGENT=1)
def test_an_agent_at_its_action_limit_refuses_added_and_restored_actions(
    data_fixture, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    url = agent_url(agent, "actions:list")
    assert api_client.get(agent_url(agent, "configuration")).json()["max_actions"] == 1
    first = api_client.post(url, {"type": "smtp_email"}).json()

    response = api_client.post(url, {"type": "smtp_email"})

    assert response.status_code == 400, response.json()
    assert response.json()["error"] == "ERROR_AGENT_ACTION_LIMIT_REACHED"
    AgentActionService().delete_action(api_user, agent.id, first["id"])
    assert api_client.post(url, {"type": "smtp_email"}).status_code == 200
    with pytest.raises(TrashItemRestorationDisallowed):
        TrashHandler.restore_item(
            api_user, AgentActionTrashableItemType.type, first["id"]
        )
    assert AgentAction.objects.filter(agent=agent).count() == 1


@pytest.mark.django_db
def test_agents_have_no_action_limit_by_default(data_fixture, api_client, api_user):
    agent = data_fixture.create_agent_application(user=api_user)
    assert (
        api_client.get(agent_url(agent, "configuration")).json()["max_actions"] is None
    )


@pytest.mark.django_db
def test_reading_actions_takes_the_same_queries_for_one_as_for_many(
    data_fixture, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    integration = data_fixture.create_smtp_integration(application=agent)

    def add_ready_action():
        action = data_fixture.create_agent_action(agent=agent)
        service = action.service.specific
        service.integration = integration
        service.use_instance_smtp_settings = False
        service.from_email = {"formula": "'sender@example.com'"}
        service.save()

    def count_queries():
        with CaptureQueriesContext(connection) as tools:
            offered = AgentHandler().get_action_tools(agent)
        with CaptureQueriesContext(connection) as listed:
            response = api_client.get(agent_url(agent, "actions:list"))
        assert len(offered) == len(response.json())
        return len(offered), len(tools), len(listed)

    add_ready_action()
    # The first request also fills caches a later one reuses.
    count_queries()
    one = count_queries()
    for _ in range(5):
        add_ready_action()

    assert count_queries() == (6, *one[1:])
