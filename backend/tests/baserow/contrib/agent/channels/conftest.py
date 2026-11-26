from collections.abc import Iterator

import pytest

from baserow.contrib.agent.channels.registries import (
    AgentChannelType,
    agent_channel_type_registry,
)
from baserow.contrib.agent.models import AgentChannel


class BaseAgentChannelType(AgentChannelType):
    type = "base"
    model_class = AgentChannel


@pytest.fixture
def channel_type() -> Iterator[AgentChannelType]:
    channel_type = BaseAgentChannelType()
    agent_channel_type_registry.register(channel_type)
    agent_channel_type_registry.get_for_class.cache_clear()
    yield channel_type
    agent_channel_type_registry.unregister(channel_type)
    agent_channel_type_registry.get_for_class.cache_clear()
