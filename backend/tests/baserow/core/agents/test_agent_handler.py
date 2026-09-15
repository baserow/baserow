import pytest

from baserow.core.agents.handler import AgentHandler
from baserow.core.models import Agent


@pytest.mark.django_db
def test_update_last_active(data_fixture):
    agent = Agent.objects.create(
        workspace=data_fixture.create_workspace(),
        name="Writer",
    )

    updated_agent = AgentHandler().update_last_active(agent)

    assert updated_agent is agent
    assert agent.last_active is not None
    last_active = agent.last_active
    agent.refresh_from_db()
    assert agent.last_active == last_active
