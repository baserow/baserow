"""Convert and persist grouped filters without coupling their owning models."""


def serialize_filter(
    condition, *, group_id, field_key="field_id", include_group=True, extra=None
):
    """Serialize the common condition fields with the caller's group reference."""
    result = {
        **(extra or {}),
        field_key: condition.field_id,
        "type": condition.type,
        "value": condition.value,
    }
    if include_group:
        result["group"] = group_id
    return result


def serialize_filter_group(group, *, reference, parent_reference, extra=None):
    return {
        **(extra or {}),
        "id": reference,
        "filter_type": group.filter_type,
        "parent_group": parent_reference,
    }


def sync_filter_groups(
    queryset, groups, *, owner_values, root=None, allow_unresolved_parents=False
):
    """Reconcile model groups using opaque payload IDs, preserving existing IDs.

    Groups supply model values plus the correlation keys `id` and
    `parent_group_id`. Parents may follow their children in the payload. The
    caller can retain the legacy service behavior of putting unresolved groups
    at the root, while validated widget groups reject an invalid hierarchy.
    """
    existing = {str(group.id): group for group in queryset}
    incoming_ids = {str(group["id"]) for group in groups}
    for group_id, group in list(existing.items()):
        if group_id not in incoming_ids:
            group.delete()
            del existing[group_id]

    resolved = {}
    pending = list(groups)

    def upsert(values, parent):
        """Apply model values while keeping an existing group's primary key."""
        values = {**values}
        reference = str(values.pop("id"))
        values.pop("parent_group_id", None)
        values["parent_group"] = parent
        instance = existing.get(reference)
        if instance is None:
            instance = queryset.model(**owner_values, **values)
        else:
            for key, value in values.items():
                setattr(instance, key, value)
        instance.save()
        resolved[reference] = instance

    while pending:
        remaining = []
        for group in pending:
            parent_id = group.get("parent_group_id")
            if parent_id is not None and str(parent_id) not in resolved:
                remaining.append(group)
                continue
            upsert(group, resolved[str(parent_id)] if parent_id is not None else root)
        if len(remaining) == len(pending):
            if not allow_unresolved_parents:
                raise ValueError("Invalid filter group hierarchy.")
            for group in remaining:
                upsert(group, root)
            break
        pending = remaining
    return resolved


def replace_filters(queryset, filters, *, groups, owner_values, root=None):
    """Replace conditions, translating payload group IDs into model relations.

    The caller supplies model-ready values (including validated formula values),
    plus a `group_id` correlation key. Order follows the payload, independently
    of the groups' ordering. The caller owns the transaction and cache updates.
    """
    queryset.all().delete()
    instances = []
    for order, values in enumerate(filters):
        values = {**values}
        reference = values.pop("group_id", None)
        group = groups.get(str(reference)) if reference is not None else root
        instances.append(
            queryset.model(**owner_values, **values, group=group, order=order)
        )
    return queryset.model.objects.bulk_create(instances)
