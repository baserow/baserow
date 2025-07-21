from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List

from baserow.contrib.database.fields.models import Field, SelectOption


def normalize_datetime(d):
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    else:
        d = d.astimezone(timezone.utc)

    d = d.replace(second=0, microsecond=0)
    return d


def normalize_date(d):
    if isinstance(d, datetime):
        d = d.date()
    return d


def compare_date(date1, date2):
    if isinstance(date1, datetime) and isinstance(date2, datetime):
        date1 = normalize_datetime(date1)
        date2 = normalize_datetime(date2)
    elif isinstance(date1, date) or isinstance(date2, date):
        date1 = normalize_date(date1)
        date2 = normalize_date(date2)
    return date1 == date2


@dataclass
class SourceOption:
    id: int
    value: str
    color: str
    order: int


def update_baserow_field_select_options(
    source_options: List[SourceOption],
    baserow_field: Field,
    existing_mapping: dict,
) -> dict:
    """
    Creates, updates or deletes the select options based on the provided
    `source_options`. This function is made to be used in the `get_metadata`
    method of a DataSyncType if it should contain select options.

    :param source_options: A list of the options that must be created for the
        `baserow_field`.
    :param baserow_field: The Baserow field where the select options must be created
        for.
    :param existing_mapping: A key value dict mapping the source option id with the
        created target option. Must be provided if the field already has select
        options. It's used to correctly create, update, or delete the options.
    :return: The key value dict mapping with the source option id as key and created
        target option id as value. Must be passed into this function the next time the
        options must be updated.
    """

    select_options_mapping = {}

    # Collect existing select options and prepare new field options. By storing
    # them all in a list, we can loop over them and decide if they should be
    # created, updated, or deleted.
    target_field_options = [
        SelectOption(
            value=field_option.value,
            color=field_option.color,
            order=field_option.order,
            field=baserow_field,
        )
        for field_option in source_options
    ]

    # Prepare lists to track which options need to be created, updated, or deleted.
    to_create = []
    to_update = []
    to_delete_ids = set(existing_mapping.values())

    # Loop through the new options to decide on create or update actions.
    for existing_option, new_option in zip(source_options, target_field_options):
        target_id = existing_mapping.get(str(existing_option.id))

        # If a target_id exists in the mapping, we update, otherwise, we create new.
        if target_id:
            new_option.id = target_id
            to_update.append((new_option, existing_option.id))
            to_delete_ids.discard(target_id)
        else:
            to_create.append((new_option, existing_option.id))

    if to_create:
        created_select_options = SelectOption.objects.bulk_create(
            [r[0] for r in to_create]
        )
        for created_option, existing_option_id in zip(
            created_select_options, [r[1] for r in to_create]
        ):
            select_options_mapping[str(existing_option_id)] = created_option.id

    if to_update:
        SelectOption.objects.bulk_update(
            [r[0] for r in to_update], fields=["value", "color", "order", "field"]
        )
        for updated_option, existing_option_id in to_update:
            select_options_mapping[str(existing_option_id)] = updated_option.id

    if to_delete_ids:
        SelectOption.objects.filter(id__in=to_delete_ids).delete()

    return select_options_mapping
