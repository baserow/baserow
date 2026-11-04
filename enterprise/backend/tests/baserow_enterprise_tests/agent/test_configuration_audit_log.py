from django.test.utils import override_settings

import pytest

from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
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
    }
    changed_values = {
        "instructions": "Updated private instructions",
        "run_as_subject_type": AgentSubjectType.type,
        "run_as_subject_id": identity.id,
    }

    UpdateAgentConfigurationActionType.do(user, agent.id, **changed_values)
    UpdateAgentConfigurationActionType.do(user, agent.id, **changed_values)

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
