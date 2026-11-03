"""The shared formula step for each kind of item, without a model."""

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.core.exceptions import PermissionException
from baserow_enterprise.builder.tools import formulas
from baserow_enterprise.builder.tools.formulas import apply_builder_formulas
from baserow_enterprise.builder.tools.types import (
    DisplayElementCreate,
)


def stored(element_id, field):
    element = ElementHandler().get_element(element_id).specific
    return getattr(element, field)


def _store_on_heading(builder_ctx, data_fixture, page, formula):
    heading = data_fixture.create_builder_heading_element(page=page, value="''")
    errors = apply_builder_formulas(
        builder_ctx["ctx"],
        page,
        [
            (
                heading,
                DisplayElementCreate(
                    ref="a", type="heading", value=formula
                ).to_element_item_create(),
            )
        ],
        "element",
    )
    return heading, errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula",
    [
        "add(get('page_parameter.id'), 1)",
        "greater_than(get('page_parameter.id'), 1)",
        "add(get('page_parameter.count'), 1)",
    ],
)
def test_a_numeric_page_parameter_resolves_as_a_number(
    data_fixture, builder_ctx, formula
):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
        query_params=[{"name": "count", "type": "numeric"}],
    )

    heading, errors = _store_on_heading(builder_ctx, data_fixture, page, formula)

    assert errors == []
    assert stored(heading.id, "value")["formula"] == formula


@pytest.mark.django_db
@pytest.mark.parametrize(
    "element_type,kwargs,template",
    [
        (
            "input_text",
            {"validation_type": "integer"},
            "add(get('form_data.{id}'), 1)",
        ),
        ("rating_input", {}, "add(get('form_data.{id}'), 1)"),
        ("checkbox", {}, "equal(get('form_data.{id}'), true)"),
        ("datetime_picker", {}, "day(get('form_data.{id}'))"),
    ],
)
def test_a_form_field_resolves_as_its_type(
    data_fixture, builder_ctx, element_type, kwargs, template
):
    page = builder_ctx["page"]
    field = data_fixture.create_builder_element(
        type(element_type_registry.get(element_type)), page=page, **kwargs
    )

    _, errors = _store_on_heading(
        builder_ctx, data_fixture, page, template.format(id=field.id)
    )

    assert errors == []


@pytest.mark.django_db
def test_a_record_selector_resolves_as_a_number(data_fixture, builder_ctx):
    page = builder_ctx["page"]
    selector = data_fixture.create_builder_record_selector_element(
        page=page, data_source=builder_ctx["data_source"]
    )

    _, errors = _store_on_heading(
        builder_ctx, data_fixture, page, f"add(get('form_data.{selector.id}'), 1)"
    )

    assert errors == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "broken_function", ["page_formula_context", "write_builder_formulas"]
)
def test_an_unexpected_error_is_reported_for_the_item_and_marked(
    data_fixture, builder_ctx, monkeypatch, broken_function
):
    def broken(*args):
        raise RuntimeError("broken")

    monkeypatch.setattr(formulas, broken_function, broken)

    heading, errors = _store_on_heading(
        builder_ctx, data_fixture, builder_ctx["page"], "get('user.email')"
    )

    assert [(e["element_id"], e["field"]) for e in errors] == [(heading.id, "value")]
    assert errors[0]["error"] == "Internal error."
    assert errors[0].can_repair is False
    assert errors[0].permission_denied is False


@pytest.mark.django_db
def test_a_denied_write_is_reported_and_marked(data_fixture, builder_ctx, monkeypatch):
    def denied(*args):
        raise PermissionException()

    monkeypatch.setattr(formulas, "write_builder_formulas", denied)

    _, errors = _store_on_heading(
        builder_ctx, data_fixture, builder_ctx["page"], "get('user.email')"
    )

    assert errors[0].can_repair is False
    assert errors[0].permission_denied is True
