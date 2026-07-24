from django.dispatch import Signal

# Sent after any instance-level provider or model state changes so connected
# clients can refresh provider administration and, when required, workspace
# model availability.
ai_provider_changed = Signal()

# Sent when an instance-level provider change can alter which AI models are
# available. Premium uses this to refresh the computed error state of AI fields.
ai_provider_availability_changed = Signal()
