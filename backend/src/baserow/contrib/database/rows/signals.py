from django.dispatch import Signal

# Note that it could happen that this signal is triggered, but the actual update still
# fails because of a validation error.
before_rows_create = Signal()
before_rows_update = Signal()
before_rows_delete = Signal()

rows_loaded = Signal()
rows_created = Signal()
rows_updated = Signal()
rows_deleted = Signal()
rows_ai_values_generation_error = Signal()

row_orders_recalculated = Signal()

rows_history_updated = Signal()
