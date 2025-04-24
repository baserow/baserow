from typing import List

from baserow.contrib.database.fields.models import Field, SelectOption

from .constants import AIRTABLE_BASEROW_COLOR_MAPPING


def import_airtable_date_type_options(type_options) -> dict:
    date_format_mapping = {"European": "EU", "US": "US"}
    time_format_mapping = {"12hour": "12", "24hour": "24"}
    return {
        "date_format": date_format_mapping.get(type_options.get("dateFormat"), "ISO"),
        "date_include_time": type_options.get("isDateTime", False),
        "date_time_format": time_format_mapping.get(
            type_options.get("timeFormat"), "24"
        ),
    }


def to_import_select_option_id(field_id, choice_id):
    return f"{field_id}_{choice_id}"


def import_airtable_choices(field_id: str, type_options: dict) -> List[SelectOption]:
    order = type_options.get("choiceOrder", [])
    choices = type_options.get("choices", [])
    return [
        SelectOption(
            # Combine select id with choice id as choice id is not guaranteed to be
            # unique across table
            id=to_import_select_option_id(field_id, choice["id"]),
            value=choice["name"],
            color=AIRTABLE_BASEROW_COLOR_MAPPING.get(
                # The color isn't always provided, hence the fallback to an empty
                # color, which will fallback on the blue color.
                choice.get("color", ""),
                "blue",
            ),
            order=order.index(choice["id"]),
        )
        for choice in choices.values()
    ]


def set_select_options_on_field(
    field: Field, field_id: str, type_options: dict
) -> Field:
    """
    Set the `select_options` of a field in the prefetched objects cache. Overriding
    this object makes sure that when later `field.select_options.all()` is executed,
    it will return Airtable choices. This for example happens in
    `FieldType::export_serialized`.

    :param field: The field where the select must be set on.
    :param field_id: id of airtable choice field
    :param type_options: The options where to extract the Airtable choices from.
    :return: The updated field object.
    """

    # Overriding this object makes sure that when later
    # `field.select_options.all()` is executed, it will return Airtable choices.
    # This for example happens in `FieldType::export_serialized`.
    field._prefetched_objects_cache = {
        "select_options": import_airtable_choices(field_id, type_options)
    }
    return field
