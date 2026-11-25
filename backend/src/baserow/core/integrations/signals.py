from django.dispatch import Signal

integration_created = Signal()
integration_deleted = Signal()
integration_updated = Signal()
# Normalized dependency notification for creation (including restore), update
# (including promotion/demotion), and deletion. Carries integration_id,
# application, user and change_type. Lifecycle details are forwarded for realtime
# consumers; dependent applications own their invalidation behavior.
integration_changed = Signal()
integration_moved = Signal()
integration_orders_recalculated = Signal()
