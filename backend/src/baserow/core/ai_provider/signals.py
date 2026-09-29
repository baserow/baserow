from django.dispatch import Signal

# Sent after a provider or model update. ``workspace`` is the workspace that owns
# the update, or None for an instance-level update. ``model_availability_updated``
# tells receivers whether effective model availability changed; in that case,
# ``provider_type`` and optional ``model_identifiers`` scope affected consumers.
ai_provider_updated = Signal()
