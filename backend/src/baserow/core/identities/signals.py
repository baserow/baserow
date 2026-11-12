from django.dispatch import Signal

identity_created = Signal()
# updated_fields names the changed core fields; extension-only updates omit it.
identity_updated = Signal()
identity_deleted = Signal()
