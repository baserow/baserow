from django.dispatch import Signal

agent_definition_updated = Signal()
agent_chat_created = Signal()
agent_chat_updated = Signal()
agent_chat_deleted = Signal()

# Configuration objects: each carries the object (or its id for deletions),
# the application and the user who made the change, so the change can be
# broadcast with its payload and without echoing it to the sender.
agent_trigger_created = Signal()
agent_trigger_updated = Signal()
agent_trigger_deleted = Signal()
agent_tool_created = Signal()
agent_tool_updated = Signal()
agent_tool_deleted = Signal()
agent_chat_channel_created = Signal()
agent_chat_channel_updated = Signal()
agent_chat_channel_deleted = Signal()
