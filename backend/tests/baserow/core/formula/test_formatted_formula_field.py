"""
Tests for `FormattedFormulaField`, the formula field type whose value also says
how the surface showing the resolved formula renders it, as plain text or as
Markdown. It is declared only on the surfaces that can render Markdown, so the
type itself is the gate: a plain `FormulaField`, a `JSONFormulaField` property
or a `FormulaSerializerField` never reads, stores or returns a format, exactly
as before the type existed. (The text collection field, whose config is a
`JSONFormulaField` shared by every collection field type, keeps its format as a
sibling key of that config, see `TextCollectionFieldType`.)
"""

import json

from django.db import connection
from django.urls import reverse

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.application_types import BuilderApplicationType
from baserow.contrib.builder.elements.models import CheckboxElement, CollectionField
from baserow.contrib.integrations.local_baserow.models import LocalBaserowGetRow
from baserow.core.formula.field import (
    BASEROW_FORMULA_VERSION_INITIAL,
    FormattedFormulaField,
    FormulaField,
)
from baserow.core.formula.serializers import (
    FormattedFormulaSerializerField,
    FormulaSerializerField,
)
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_RAW,
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaObject,
    FormattedFormulaObject,
    get_formula_format,
)


def plain(formula):
    """A formula object of a plain `FormulaField`: three keys, no format."""

    return BaserowFormulaObject(
        formula=formula,
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version=BASEROW_FORMULA_VERSION_INITIAL,
    )


def formatted(formula, format="plain"):
    """A formula object of a `FormattedFormulaField`: the format is always there."""

    return FormattedFormulaObject(**plain(formula), format=format)


def stored(formula, **extra):
    """The minified form of a formula object, as stored in the database."""

    return {"f": formula, "m": "simple", "v": "0.1", **extra}


def read_column(instance, field_name):
    """
    Reads a column as stored, bypassing the field's `from_db_value`, and parses
    its JSON.
    """

    field = instance._meta.get_field(field_name)
    meta = field.model._meta
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT "{field.column}" FROM "{meta.db_table}" '
            f'WHERE "{meta.pk.column}" = %s',
            [instance.pk],
        )
        value = cursor.fetchone()[0]
    return json.loads(value) if isinstance(value, str) else value


def write_column(instance, field_name, value):
    """
    Writes a column as is, bypassing the field's `get_prep_value`. A dict is
    stored as JSON, a string as the raw text it is, e.g. a legacy formula string.
    """

    field = instance._meta.get_field(field_name)
    meta = field.model._meta
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE "{meta.db_table}" SET "{field.column}" = '
            f'%s::{field.db_type(connection)} WHERE "{meta.pk.column}" = %s',
            [value if isinstance(value, str) else json.dumps(value), instance.pk],
        )


def test_formatted_formula_object_always_carries_a_format():
    assert FormattedFormulaObject.create("'x'") == formatted("'x'")
    assert FormattedFormulaObject.create("'x'", format="markdown") == formatted(
        "'x'", "markdown"
    )
    # A plain object gains the plain default, or the given format.
    assert FormattedFormulaObject.from_formula(plain("'x'")) == formatted("'x'")
    assert FormattedFormulaObject.from_formula(plain("'x'"), "markdown") == formatted(
        "'x'", "markdown"
    )
    # A formatted object keeps its format unless another one is given.
    assert FormattedFormulaObject.from_formula(formatted("'x'", "markdown")) == (
        formatted("'x'", "markdown")
    )
    assert FormattedFormulaObject.from_formula(
        formatted("'x'", "markdown"), "plain"
    ) == formatted("'x'")


def test_get_formula_format_reads_both_forms_and_defaults_to_plain():
    assert get_formula_format(formatted("'x'", "markdown")) == "markdown"
    assert get_formula_format(stored("'x'", fmt="markdown")) == "markdown"
    assert get_formula_format(plain("'x'")) == "plain"
    assert get_formula_format(stored("'x'")) == "plain"
    assert get_formula_format({"format": None}) == "plain"
    assert get_formula_format("'x'") == "plain"
    assert get_formula_format(None) == "plain"


def test_formatted_formula_field_deconstructs_as_a_formula_field():
    """
    Both types share the same text column, so declaring a column with either
    must not generate a migration, the way `JSONFormulaField` deconstructs as a
    `JSONField`.
    """

    formatted_field = CheckboxElement._meta.get_field("label")
    plain_field = CheckboxElement._meta.get_field("default_value")
    assert isinstance(formatted_field, FormattedFormulaField)
    assert type(plain_field) is FormulaField

    _, path, args, kwargs = formatted_field.deconstruct()
    _, plain_path, plain_args, plain_kwargs = plain_field.deconstruct()
    assert path == plain_path == "baserow.core.formula.field.FormulaField"
    assert args == plain_args
    assert kwargs.keys() == plain_kwargs.keys()
    assert {k: v for k, v in kwargs.items() if k != "help_text"} == {
        k: v for k, v in plain_kwargs.items() if k != "help_text"
    }


@pytest.mark.django_db
def test_formatted_formula_field_round_trips_the_format(data_fixture):
    """
    `FormattedFormulaField` is a text column holding the minified JSON, with the
    format as `fmt`.
    """

    element = data_fixture.create_builder_checkbox_element(
        label=formatted("'**I agree**'", "markdown")
    )

    assert read_column(element, "label") == stored("'**I agree**'", fmt="markdown")
    # The in-memory value is normalised after the save, like a read is.
    assert element.label == formatted("'**I agree**'", "markdown")
    assert CheckboxElement.objects.get(id=element.id).label == formatted(
        "'**I agree**'", "markdown"
    )


@pytest.mark.django_db
def test_formatted_formula_field_always_stores_and_returns_a_format(data_fixture):
    """
    A value written without a format, e.g. a plain object or a formula string,
    is a plain one: the key is always there on the way out.
    """

    element = data_fixture.create_builder_checkbox_element(label=plain("'I agree'"))
    assert read_column(element, "label") == stored("'I agree'", fmt="plain")
    assert element.label == formatted("'I agree'")
    assert CheckboxElement.objects.get(id=element.id).label == formatted("'I agree'")

    element = data_fixture.create_builder_checkbox_element(label="'I agree'")
    assert read_column(element, "label") == stored("'I agree'", fmt="plain")
    assert CheckboxElement.objects.get(id=element.id).label == formatted("'I agree'")


@pytest.mark.django_db
def test_formatted_formula_field_reads_stored_values_without_fmt_as_plain(
    data_fixture,
):
    """
    Rows written before the column was declared with the type have no `fmt`, or
    are still a raw formula string. They read as plain without any migration.
    """

    element = data_fixture.create_builder_checkbox_element()

    write_column(element, "label", stored("'x'"))
    assert CheckboxElement.objects.get(id=element.id).label == formatted("'x'")

    write_column(element, "label", "'x'")
    assert CheckboxElement.objects.get(id=element.id).label == formatted("'x'")


@pytest.mark.django_db
def test_plain_formula_field_ignores_a_stray_format(data_fixture):
    """
    A plain `FormulaField` behaves exactly as before the type existed: a stray
    `format` on the object written through it is not stored, and a stray `fmt`
    in its column is not returned.
    """

    element = data_fixture.create_builder_checkbox_element(
        default_value={**plain("'x'"), "format": "markdown"}
    )
    assert read_column(element, "default_value") == stored("'x'")
    assert CheckboxElement.objects.get(id=element.id).default_value == plain("'x'")

    write_column(element, "default_value", stored("'x'", fmt="markdown"))
    assert CheckboxElement.objects.get(id=element.id).default_value == plain("'x'")


@pytest.mark.django_db
def test_json_formula_field_ignores_a_stray_format(data_fixture):
    """
    Every `JSONFormulaField` property is a plain formula, the text collection
    field `value` included.
    """

    table_element = data_fixture.create_builder_table_element(
        fields=[
            {
                "name": "Text",
                "type": "text",
                "config": {"value": {**plain("'x'"), "format": "markdown"}},
            },
            {"name": "Button", "type": "button", "config": {"label": "'y'"}},
        ]
    )
    text_field, button_field = table_element.fields.all()
    assert read_column(text_field, "config") == {"value": stored("'x'")}
    assert CollectionField.objects.get(id=text_field.id).config == {
        "value": plain("'x'")
    }

    write_column(button_field, "config", {"label": stored("'y'", fmt="markdown")})
    assert CollectionField.objects.get(id=button_field.id).config == {
        "label": plain("'y'")
    }


def serializer_field(field_class, **kwargs):
    field = field_class(**kwargs)
    field._context = {"application_type": BuilderApplicationType}
    return field


def test_formatted_serializer_field_validates_and_always_returns_the_format():
    field = serializer_field(FormattedFormulaSerializerField)

    assert field.to_internal_value({"formula": "'x'", "format": "markdown"}) == (
        formatted("'x'", "markdown")
    )
    assert field.to_internal_value({"formula": "'x'", "format": "plain"}) == (
        formatted("'x'")
    )
    # Omitted, or given as a bare formula string, means plain.
    assert field.to_internal_value({"formula": "'x'"}) == formatted("'x'")
    assert field.to_internal_value("'x'") == formatted("'x'")
    assert field.to_internal_value("") == formatted("")
    assert field.to_internal_value({}) == formatted("")
    assert field.default == formatted("")

    with pytest.raises(ValidationError) as exc:
        field.to_internal_value({"formula": "'x'", "format": "html"})
    assert exc.value.detail["format"][0].code == "invalid_choice"

    # The formula itself is still validated, before its format is applied.
    with pytest.raises(ValidationError) as exc:
        field.to_internal_value({"formula": "get('foobar.123')", "format": "markdown"})
    assert exc.value.detail[0].code == "invalid_formula_argument"


def test_formatted_serializer_field_formats_raw_and_empty_formulas():
    """
    The format is applied after the base field's early return for raw mode and
    empty formulas, so a raw Markdown text works.
    """

    field = serializer_field(FormattedFormulaSerializerField)

    assert field.to_internal_value(
        {"formula": "**x**", "mode": BASEROW_FORMULA_MODE_RAW, "format": "markdown"}
    ) == {
        "formula": "**x**",
        "mode": BASEROW_FORMULA_MODE_RAW,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
        "format": "markdown",
    }
    assert field.to_internal_value({"formula": "", "format": "markdown"}) == (
        formatted("", "markdown")
    )


def test_formatted_serializer_field_represents_a_missing_format_as_plain():
    field = serializer_field(FormattedFormulaSerializerField)

    assert field.to_representation(formatted("'x'", "markdown")) == formatted(
        "'x'", "markdown"
    )
    # An instance that never went through the model field, e.g. a bulk created
    # one, still shows the format.
    assert field.to_representation(plain("'x'")) == formatted("'x'")


def test_plain_serializer_field_drops_the_format():
    """
    A plain `FormulaSerializerField` doesn't declare the key, so it drops it the
    way it drops any undeclared key, exactly as before the type existed. The API
    therefore only keeps a format on the surfaces that render one.
    """

    field = serializer_field(FormulaSerializerField)

    assert field.to_internal_value({"formula": "'x'", "format": "markdown"}) == (
        plain("'x'")
    )
    assert field.to_internal_value({"formula": "'x'"}) == plain("'x'")
    assert field.default == plain("")


@pytest.mark.django_db
def test_other_formula_consumers_keep_three_key_objects(data_fixture):
    """
    The services shared by the automation and dashboard applications use the
    plain field. Nothing they never set is stored or returned.
    """

    service = data_fixture.create_local_baserow_get_row_service(
        row_id={**plain("'1'"), "format": "markdown"}
    )

    assert read_column(service, "row_id") == stored("'1'")
    assert LocalBaserowGetRow.objects.get(id=service.id).row_id == plain("'1'")


@pytest.mark.django_db
def test_automation_node_formulas_drop_a_format(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_local_baserow_get_row_action_node(
        user=user, workflow=workflow
    )

    response = api_client.patch(
        reverse("api:automation:nodes:item", kwargs={"node_id": node.id}),
        {
            "service": {
                "type": node.service.get_type().type,
                "row_id": {"formula": "'1'", "format": "markdown"},
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["service"]["row_id"] == plain("'1'")
    assert LocalBaserowGetRow.objects.get(id=node.service.id).row_id == plain("'1'")


@pytest.mark.django_db
def test_dashboard_data_source_formulas_drop_a_format(api_client, data_fixture):
    """
    A raw formula, because the dashboard data source view gives the formula
    serializer no application type context and can't validate a parsed one.
    """

    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard
    )

    response = api_client.patch(
        reverse(
            "api:dashboard:data_sources:item",
            kwargs={"data_source_id": data_source.id},
        ),
        {
            "search_query": {
                "formula": "x",
                "mode": BASEROW_FORMULA_MODE_RAW,
                "format": "markdown",
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["search_query"] == {
        "formula": "x",
        "mode": BASEROW_FORMULA_MODE_RAW,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }
