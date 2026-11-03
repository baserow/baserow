"""The shared formula step for each kind of item, without a model."""

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.core.exceptions import PermissionException
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.graph.types import GraphPointPosition
from baserow_enterprise.builder.tools import formulas
from baserow_enterprise.builder.tools.formulas import apply_builder_formulas
from baserow_enterprise.builder.tools.types import (
    ActionCreate,
    DisplayElementCreate,
    ElementUpdate,
)


def stored(element_id, field):
    element = ElementHandler().get_element(element_id).specific
    return getattr(element, field)


@pytest.mark.django_db
def test_element_explicit_formula_is_stored_and_a_description_reported(
    data_fixture, builder_ctx
):
    page = builder_ctx["page"]
    explicit = data_fixture.create_builder_heading_element(page=page, value="''")
    described = data_fixture.create_builder_heading_element(page=page, value="''")

    errors = apply_builder_formulas(
        builder_ctx["ctx"],
        page,
        [
            (
                explicit,
                DisplayElementCreate(
                    ref="a", type="heading", value="get('user.email')"
                ).to_element_item_create(),
            ),
            (
                described,
                DisplayElementCreate(
                    ref="b", type="heading", value="$formula: the page title"
                ).to_element_item_create(),
            ),
        ],
        "element",
    )

    assert stored(explicit.id, "value")["formula"] == "get('user.email')"
    assert stored(explicit.id, "value")["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert stored(described.id, "value")["formula"] == "''"
    assert [(e["element_id"], e["field"]) for e in errors] == [(described.id, "value")]
    assert set(errors[0]) == {"element_id", "field", "formula", "error"}


@pytest.mark.django_db
def test_element_update_stores_an_explicit_formula(data_fixture, builder_ctx):
    page = builder_ctx["page"]
    heading = data_fixture.create_builder_heading_element(page=page, value="'Old'")

    errors = apply_builder_formulas(
        builder_ctx["ctx"],
        page,
        [(heading, ElementUpdate(element_id=heading.id, value="get('user.email')"))],
        "element",
    )

    assert errors == []
    assert stored(heading.id, "value")["formula"] == "get('user.email')"


@pytest.mark.django_db
def test_element_inside_a_repeat_resolves_against_the_current_record(
    data_fixture, builder_ctx
):
    page = builder_ctx["page"]
    data_source = builder_ctx["data_source"]
    repeat = data_fixture.create_builder_repeat_element(
        page=page, data_source=data_source
    )
    heading = data_fixture.create_builder_heading_element(
        page=page,
        value="''",
        reference_element=repeat,
        position=GraphPointPosition.CHILD,
    )
    field = data_source.service.specific.table.field_set.first()

    errors = apply_builder_formulas(
        builder_ctx["ctx"],
        page,
        [
            (
                heading,
                DisplayElementCreate(
                    ref="a",
                    type="heading",
                    value=f"get('current_record.field_{field.id}')",
                ).to_element_item_create(),
            )
        ],
        "element",
    )

    assert errors == []
    assert stored(heading.id, "value")["formula"] == (
        f"get('current_record.field_{field.id}')"
    )


@pytest.mark.django_db
def test_action_explicit_formula_is_stored_and_a_description_reported(builder_ctx):
    page = builder_ctx["page"]
    action = builder_ctx["action"]

    errors = apply_builder_formulas(
        builder_ctx["ctx"],
        page,
        [
            (
                action,
                ActionCreate(
                    element=builder_ctx["button"].id,
                    type="notification",
                    title="get('user.email')",
                    description="$formula: a friendly thanks",
                ),
            )
        ],
        "action",
    )

    action.refresh_from_db()
    assert action.specific.title["formula"] == "get('user.email')"
    assert action.specific.title["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert [(e["action_id"], e["field"]) for e in errors] == [
        (action.id, "description")
    ]


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
def test_a_text_page_parameter_is_not_a_number(data_fixture, builder_ctx):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        path="/item/:slug",
        path_params=[{"name": "slug", "type": "text"}],
    )

    _, errors = _store_on_heading(
        builder_ctx, data_fixture, page, "add(get('page_parameter.slug'), 1)"
    )

    assert len(errors) == 1


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
def test_an_unexpected_error_while_checking_is_reported_for_the_item(
    data_fixture, builder_ctx, monkeypatch
):
    def broken(page):
        raise RuntimeError("broken")

    monkeypatch.setattr(formulas, "page_formula_context", broken)

    heading, errors = _store_on_heading(
        builder_ctx, data_fixture, builder_ctx["page"], "get('user.email')"
    )

    assert [(e["element_id"], e["field"]) for e in errors] == [(heading.id, "value")]
    assert errors[0]["error"] == "Internal error."
    assert errors[0].can_repair is False


@pytest.mark.django_db
def test_a_failed_write_is_reported_and_marked(data_fixture, builder_ctx, monkeypatch):
    def broken(*args):
        raise RuntimeError("broken")

    monkeypatch.setattr(formulas, "write_builder_formulas", broken)

    _, errors = _store_on_heading(
        builder_ctx, data_fixture, builder_ctx["page"], "get('user.email')"
    )

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
