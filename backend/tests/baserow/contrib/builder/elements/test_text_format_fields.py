"""
Tests for the Plain/Markdown format of the Application Builder text surfaces.
The formula surfaces with a column of their own (the form element labels, the
notification title and description, the file input label and help text) are
declared with the `FormattedFormulaField` type, whose value carries the format;
the text collection field keeps it as a key of its config; the two plain-string
surfaces, the collection field names and the choice element option names, have
a column.
"""

from collections import defaultdict

import pytest
from rest_framework import serializers

from baserow.contrib.builder.constants import TextFormats
from baserow.contrib.builder.elements.element_types import ChoiceElementType
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import (
    collection_field_type_registry,
    element_type_registry,
)
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.formula.field import FormattedFormulaField
from baserow.core.formula.serializers import FormattedFormulaSerializerField
from baserow.core.formula.types import FormattedFormulaObject
from baserow.core.utils import MirrorDict

# (element type, formula that can be rendered as Markdown)
ELEMENT_MARKDOWN_FORMULAS = [
    ("input_text", "label"),
    ("choice", "label"),
    ("checkbox", "label"),
    ("rating_input", "label"),
    ("datetime_picker", "label"),
    ("record_selector", "label"),
]

# Every formula declared with the formatted type, as (registry, type, field).
# These are exactly the surfaces the UI offers the Plain/Markdown toggle for.
MARKDOWN_MODEL_SURFACES = {
    ("element_type", "input_text", "label"),
    ("element_type", "choice", "label"),
    ("element_type", "checkbox", "label"),
    ("element_type", "rating_input", "label"),
    ("element_type", "datetime_picker", "label"),
    ("element_type", "record_selector", "label"),
    ("element_type", "input_file", "label"),
    ("element_type", "input_file", "help_text"),
    ("builder_workflow_action_type", "notification", "title"),
    ("builder_workflow_action_type", "notification", "description"),
}


def formatted_serializer_fields(registry):
    return {
        (registry.name, instance.type, name)
        for instance in registry.get_all()
        for name, field in instance.serializer_field_overrides.items()
        if isinstance(field, FormattedFormulaSerializerField)
    }


def formatted_model_fields(registry):
    return {
        (registry.name, instance.type, field.name)
        for instance in registry.get_all()
        for field in instance.model_class._meta.get_fields()
        if isinstance(field, FormattedFormulaField)
    }


def test_the_markdown_surfaces_are_declared_with_the_formatted_type_on_both_sides():
    """
    The type is the gate: a surface renders Markdown if, and only if, its model
    field is a `FormattedFormulaField` and its serializer field a
    `FormattedFormulaSerializerField`. Both sides must agree with each other and
    with the explicit list, so the API and the UI agree on which surfaces can be
    Markdown. The Text element keeps its own `format` column, so its `value` is
    not in the list.
    """

    model_surfaces, serializer_surfaces = set(), set()
    for registry in (element_type_registry, builder_workflow_action_type_registry):
        model_surfaces |= formatted_model_fields(registry)
        serializer_surfaces |= formatted_serializer_fields(registry)

    assert model_surfaces == serializer_surfaces == MARKDOWN_MODEL_SURFACES


def test_no_collection_field_uses_the_formatted_type():
    """
    A collection field's config is one `JSONFormulaField` shared by every field
    type and keyed by property name only, and `value` is the formula of the
    boolean and rating fields too, so the type can't apply per property there.
    The text field carries its format as a sibling `format` key of its config
    instead, validated as a choice like the column surfaces are.
    """

    assert formatted_serializer_fields(collection_field_type_registry) == set()

    field_type = collection_field_type_registry.get("text")
    assert field_type.allowed_fields == ["value", "format"]
    assert field_type.serializer_field_names == ["value", "format"]
    assert field_type.SerializedDict.__annotations__["format"] is str

    field = field_type.serializer_field_overrides["format"]
    assert type(field) is serializers.ChoiceField
    assert field.required is False
    assert field.default == TextFormats.PLAIN
    assert list(field.choices.items()) == TextFormats.choices


@pytest.mark.django_db
@pytest.mark.parametrize("element_type_name,field_name", ELEMENT_MARKDOWN_FORMULAS)
def test_export_import_element_formula_format(
    data_fixture, element_type_name, field_name
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element_type = element_type_registry.get(element_type_name)
    formula = FormattedFormulaObject.create("'**bold**'", format="markdown")
    element = data_fixture.create_builder_element(
        type(element_type), user, page=page, **{field_name: formula}
    )

    exported = element_type.export_serialized(element)
    assert exported[field_name] == formula

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_element = ElementHandler().import_element(page, exported, id_mapping)

    assert imported_element.id != element.id
    assert getattr(imported_element, field_name) == formula


@pytest.mark.django_db
def test_import_rewrites_the_formula_and_keeps_its_format(data_fixture):
    """
    The `get()` paths of a formula are rewritten on import (e.g. to the new
    data source id when duplicating a page). The format survives the rewrite.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["Foo"]]
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    path = f"0.{fields[0].db_column}"
    element = data_fixture.create_builder_checkbox_element(
        page=page,
        label=FormattedFormulaObject.create(
            f"get('data_source.{data_source.id}.{path}')", format="markdown"
        ),
    )

    exported = element.get_type().export_serialized(element)
    id_mapping = {"builder_data_sources": {data_source.id: data_source2.id}}
    imported_element = ElementHandler().import_element(page, exported, id_mapping)

    assert imported_element.label == FormattedFormulaObject.create(
        f"get('data_source.{data_source2.id}.{path}')", format="markdown"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("element_type_name,field_name", ELEMENT_MARKDOWN_FORMULAS)
def test_import_element_formula_without_format_reads_as_plain(
    data_fixture, element_type_name, field_name
):
    """
    Elements exported before the format existed have three-key formula objects.
    They import as plain, and the imported value carries that format like any
    other value of the type.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element_type = element_type_registry.get(element_type_name)
    element = data_fixture.create_builder_element(
        type(element_type), user, page=page, **{field_name: "'x'"}
    )

    exported = element_type.export_serialized(element)
    assert exported[field_name] == FormattedFormulaObject.create("'x'")
    del exported[field_name]["format"]

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_element = ElementHandler().import_element(page, exported, id_mapping)

    assert getattr(imported_element, field_name) == FormattedFormulaObject.create("'x'")


def test_choice_element_type_exposes_option_format():
    element_type = ChoiceElementType()

    assert "option_format" in element_type.allowed_fields
    assert "option_format" in element_type.serializer_field_names
    assert "option_format" in element_type.request_serializer_field_names
    assert "option_format" in element_type.SerializedDict.__annotations__

    field = element_type.serializer_field_overrides["option_format"]
    assert type(field) is serializers.ChoiceField
    assert field.required is False
    assert field.default == TextFormats.PLAIN
    assert list(field.choices.items()) == TextFormats.choices


@pytest.mark.django_db
def test_export_import_choice_element_option_format(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_choice_element(
        user=user, page=page, option_format=TextFormats.MARKDOWN
    )
    element_type = element.get_type()

    exported = element_type.export_serialized(element)
    assert exported["option_format"] == "markdown"

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_element = ElementHandler().import_element(page, exported, id_mapping)
    assert imported_element.option_format == "markdown"

    # Exports made before the setting existed don't have the key.
    del exported["option_format"]
    imported_legacy_element = ElementHandler().import_element(
        page, exported, id_mapping
    )
    assert imported_legacy_element.option_format == "plain"


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
