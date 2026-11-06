from django.db import connection
from django.test.utils import override_settings
from django.urls import reverse

import pytest

from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.models import AgentApplication
from baserow.core.action.registries import action_type_registry
from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.models import Agent
from baserow_enterprise.audit_log.models import AuditLogEntry


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_configuration_audit_log_persists_full_before_and_after_snapshots(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(
        user=user,
        instructions="Original private instructions",
        provider_type="openai",
        model_identifier="test-model",
    )
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    original_values = {
        "instructions": agent.instructions,
        "provider_type": agent.provider_type,
        "model_identifier": agent.model_identifier,
        "run_as_subject_type": None,
        "run_as_subject_id": None,
        "allowed_tools": [],
    }
    changed_values = {
        "instructions": "Updated private instructions",
        "run_as_subject_type": AgentSubjectType.type,
        "run_as_subject_id": identity.id,
    }

    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user, agent.id, **changed_values
    )
    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user, agent.id, **changed_values
    )

    entry = AuditLogEntry.objects.get(
        action_type=UpdateAgentConfigurationActionType.type
    )
    assert entry.actor_id == user.id
    assert entry.workspace_id == agent.workspace_id
    assert entry.action_params == {
        "agent_id": agent.id,
        "original_values": original_values,
        "new_values": {**original_values, **changed_values},
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("audit_fails", [False, True], ids=["commit", "rollback"])
@override_settings(DEBUG=True)
def test_configuration_patch_commits_configuration_audit_and_notification_together(
    enterprise_data_fixture, api_client, mocker, audit_fails
):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_application(
        user=user, instructions="Original instructions"
    )
    notifications = []

    def record_committed_notification(*args, **kwargs):
        persisted = AgentApplication.objects.get(id=agent.id)
        entry = AuditLogEntry.objects.filter(
            action_type=UpdateAgentConfigurationActionType.type
        ).first()
        notifications.append(
            (
                args[4]["type"],
                args[4]["application_id"],
                persisted.instructions,
                entry.action_params["new_values"]["instructions"] if entry else None,
                connection.in_atomic_block,
            )
        )

    broadcast = mocker.patch(
        "baserow.ws.signals.broadcast_to_permitted_users.delay",
        side_effect=record_committed_notification,
    )
    if audit_fails:
        audit_write = mocker.patch.object(
            AuditLogEntry.objects,
            "create",
            side_effect=RuntimeError("Audit write failed"),
        )
    assert not connection.in_atomic_block
    url = reverse("api:agent:configuration", kwargs={"agent_id": agent.id})
    request_kwargs = {
        "data": {"instructions": "Updated instructions"},
        "format": "json",
        "HTTP_AUTHORIZATION": f"JWT {token}",
    }

    if audit_fails:
        with pytest.raises(RuntimeError, match="Audit write failed"):
            api_client.patch(url, **request_kwargs)
        audit_write.assert_called_once()
        agent.refresh_from_db()
        assert agent.instructions == "Original instructions"
        assert not AuditLogEntry.objects.filter(
            action_type=UpdateAgentConfigurationActionType.type
        ).exists()
        broadcast.assert_not_called()
        assert notifications == []
    else:
        response = api_client.patch(url, **request_kwargs)
        assert response.status_code == 200
        assert response.json()["instructions"] == "Updated instructions"
        broadcast.assert_called_once()
        assert notifications == [
            (
                "application_updated",
                agent.id,
                "Updated instructions",
                "Updated instructions",
                False,
            )
        ]
