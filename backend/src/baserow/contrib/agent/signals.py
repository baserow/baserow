from django.dispatch import Signal

agent_loaded = Signal()
agent_conversation_updated = Signal()
agent_conversation_renamed = Signal()
agent_conversation_deleted = Signal()
