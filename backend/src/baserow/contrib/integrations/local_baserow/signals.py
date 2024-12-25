from typing import TYPE_CHECKING, Optional

from django.dispatch import receiver

from baserow.contrib.database.fields.signals import field_updated
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFieldMapping,
    LocalBaserowTableServiceFilter,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


@receiver(field_updated)
def handle_local_baserow_field_updated_changes(
    sender, field: "Field", old_field: Optional["Field"] = None, **kwargs
):
    if kwargs.get("field_type_changed", False):
        # If the field type has changed, and the new field type is read-only,
        # then we'll delete the field mapping, as the value won't be used.
        if field.get_type().read_only:
            LocalBaserowTableServiceFieldMapping.objects.filter(field=field).delete()
        # If the field type has changed, and the old field has service filters
        # which are no longer compatible with the new field type, delete them.
        incompatible_filter_ids = []
        service_filters = LocalBaserowTableServiceFilter.objects.filter(
            field=old_field
        ).only("type", "id")
        for service_filter in service_filters:
            filter_type = view_filter_type_registry.get(service_filter.type)
            if not filter_type.field_is_compatible(field):
                incompatible_filter_ids.append(service_filter.id)
        LocalBaserowTableServiceFilter.objects.filter(
            id__in=incompatible_filter_ids
        ).delete()
