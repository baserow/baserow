"""
Export/import tests for the Plain/Markdown `*_format` settings of the form
element labels, the choice element option names and the collection field names.
"""

from collections import defaultdict

import pytest
from rest_framework import serializers

from baserow.contrib.builder.constants import TextFormats
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.core.utils import MirrorDict

# (element type, format field)
ELEMENT_FORMAT_FIELDS = [
    ("input_text", "label_format"),
    ("choice", "label_format"),
    ("choice", "option_format"),
    ("checkbox", "label_format"),
    ("rating_input", "label_format"),
    ("datetime_picker", "label_format"),
    ("record_selector", "label_format"),
]


@pytest.mark.parametrize("element_type_name,field_name", ELEMENT_FORMAT_FIELDS)
def test_element_type_exposes_format_field(element_type_name, field_name):
    element_type = element_type_registry.get(element_type_name)

    assert field_name in element_type.allowed_fields
    assert field_name in element_type.serializer_field_names
    assert field_name in element_type.SerializedDict.__annotations__

    field = element_type.serializer_field_overrides[field_name]
    assert type(field) is serializers.ChoiceField
    assert field.required is False
    assert field.default == TextFormats.PLAIN
    assert list(field.choices.items()) == TextFormats.choices


@pytest.mark.django_db
@pytest.mark.parametrize("element_type_name,field_name", ELEMENT_FORMAT_FIELDS)
def test_export_import_element_format(data_fixture, element_type_name, field_name):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element_type = element_type_registry.get(element_type_name)
    element = data_fixture.create_builder_element(
        type(element_type), user, page=page, **{field_name: TextFormats.MARKDOWN}
    )

    exported = element_type.export_serialized(element)
    assert exported[field_name] == "markdown"

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_element = ElementHandler().import_element(page, exported, id_mapping)

    assert imported_element.id != element.id
    assert getattr(imported_element, field_name) == "markdown"


@pytest.mark.django_db
@pytest.mark.parametrize("element_type_name,field_name", ELEMENT_FORMAT_FIELDS)
def test_import_element_without_format_defaults_to_plain(
    data_fixture, element_type_name, field_name
):
    """
    Elements exported before the `*_format` settings existed don't have the key.
    They must be imported with the `plain` format.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element_type = element_type_registry.get(element_type_name)
    element = data_fixture.create_builder_element(type(element_type), user, page=page)

    exported = element_type.export_serialized(element)
    del exported[field_name]

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_element = ElementHandler().import_element(page, exported, id_mapping)

    assert getattr(imported_element, field_name) == "plain"


@pytest.mark.django_db
def test_export_import_collection_field_name_format(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table_element = data_fixture.create_builder_table_element(
        user=user,
        page=page,
        fields=[
            {
                "name": "**Bold** header",
                "name_format": "markdown",
                "type": "text",
                "config": {"value": "'x'"},
            },
            {"name": "Plain header", "type": "text", "config": {"value": "'y'"}},
        ],
    )

    exported = table_element.get_type().export_serialized(table_element)
    assert exported["fields"][0]["name_format"] == "markdown"
    assert exported["fields"][1]["name_format"] == "plain"

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_table_element = ElementHandler().import_element(page, exported, id_mapping)

    markdown_field, plain_field = imported_table_element.fields.all()
    assert markdown_field.name == "**Bold** header"
    assert markdown_field.name_format == "markdown"
    assert plain_field.name_format == "plain"


@pytest.mark.django_db
def test_import_collection_field_without_name_format_defaults_to_plain(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table_element = data_fixture.create_builder_table_element(
        user=user,
        page=page,
        fields=[{"name": "Header", "type": "text", "config": {"value": "'x'"}}],
    )

    exported = table_element.get_type().export_serialized(table_element)
    del exported["fields"][0]["name_format"]

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_table_element = ElementHandler().import_element(page, exported, id_mapping)

    assert imported_table_element.fields.get().name_format == "plain"
