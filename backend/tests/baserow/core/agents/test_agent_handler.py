from datetime import datetime, timezone

from django.core.cache import cache

import pytest
from freezegun import freeze_time

from baserow.core.agents.handler import (
    AGENT_LAST_ACTIVE_CACHE_KEY,
    AGENT_LAST_ACTIVE_CACHE_TTL_SECONDS,
    AgentHandler,
)
from baserow.core.cache import global_cache
from baserow.core.models import Agent


@pytest.mark.django_db
def test_update_last_active(data_fixture):
    cache.clear()
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


@pytest.mark.django_db
def test_update_last_active_is_throttled_until_cache_expires(data_fixture):
    agent = Agent.objects.create(
        workspace=data_fixture.create_workspace(),
        name="Writer",
    )
    cache.clear()

    first_activity = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    with freeze_time(first_activity):
        AgentHandler().update_last_active(agent)

    with freeze_time("2026-01-01 12:00:59"):
        AgentHandler().update_last_active(agent)

    agent.refresh_from_db()
    assert agent.last_active == first_activity

    global_cache.invalidate(
        AGENT_LAST_ACTIVE_CACHE_KEY.format(agent_id=agent.id),
    )

    second_activity = datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)
    with freeze_time(second_activity):
        AgentHandler().update_last_active(agent)

    agent.refresh_from_db()
    assert agent.last_active == second_activity
    assert AGENT_LAST_ACTIVE_CACHE_TTL_SECONDS == 60
