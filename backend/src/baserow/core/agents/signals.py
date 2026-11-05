from django.dispatch import Signal

agent_created = Signal()
# updated_fields contains changed core fields; extension-only notifications omit it.
agent_updated = Signal()
agent_deleted = Signal()
