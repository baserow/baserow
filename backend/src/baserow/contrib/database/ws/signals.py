from django.conf import settings

from .field_rules.signals import (
    on_field_rule_created,
    on_field_rule_deleted,
    on_field_rule_updated,
)
from .fields.signals import field_created, field_deleted, field_updated
from .rows.signals import rows_created, rows_deleted, rows_updated
from .table.signals import table_created, table_deleted, table_updated
from .views.rows.signals import (
    views_before_rows_delete,
    views_before_rows_update,
    views_rows_created,
    views_rows_deleted,
    views_rows_updated,
)
from .views.signals import view_created, view_deleted, view_updated, views_reordered

if settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS:
    PUBLIC_SIGNALS = []
else:
    # isort: off
    # noinspection PyUnresolvedReferences
    from .public.views.signals import (  # noqa: F401
        public_view_field_options_updated,
        public_view_filter_created,
        public_view_filter_deleted,
        public_view_filter_updated,
        public_view_updated,
    )

    # noinspection PyUnresolvedReferences
    from .public.fields.signals import (  # noqa: F401
        public_field_created,
        public_field_deleted,
        public_field_restored,
        public_field_updated,
    )

    # isort: on

    PUBLIC_SIGNALS = [
        "public_view_filter_updated",
        "public_view_filter_deleted",
        "public_view_filter_created",
        "public_view_updated",
        "public_view_field_options_updated",
        "public_field_created",
        "public_field_deleted",
        "public_field_updated",
        "public_field_restored",
    ]

__all__ = [
    "table_created",
    "table_updated",
    "table_deleted",
    "views_reordered",
    "view_created",
    "view_updated",
    "view_deleted",
    "rows_created",
    "rows_updated",
    "rows_deleted",
    "field_created",
    "field_updated",
    "field_deleted",
    "on_field_rule_created",
    "on_field_rule_updated",
    "on_field_rule_deleted",
    "views_rows_created",
    "views_rows_updated",
    "views_rows_deleted",
    "views_before_rows_update",
    "views_before_rows_delete",
    *PUBLIC_SIGNALS,
]
