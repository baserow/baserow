"""The shared formula step for each kind of item, without a model."""

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.exceptions import PermissionException
from baserow_enterprise.builder.tools import actions, data_sources, elements, formulas
from baserow_enterprise.builder.tools.formulas import apply_builder_formulas
from baserow_enterprise.builder.tools.types import (
    ActionCreate,
    DataSourceCreate,
    DisplayElementCreate,
    ElementChanges,
    ElementItemCreate,
)
from baserow_enterprise.tools.formula_utils import needs_formula


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


# ---------------------------------------------------------------------------
# Plain text with a word before a parenthesis
# ---------------------------------------------------------------------------

SENTENCE = "Order now (today only)"
STORED_SENTENCE = f"'{SENTENCE}'"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "item, field",
    [
        ({"type": "heading", "value": SENTENCE}, "value"),
        ({"type": "text", "value": SENTENCE}, "value"),
        ({"type": "button", "value": SENTENCE}, "value"),
        ({"type": "link", "value": SENTENCE}, "value"),
        ({"type": "image", "alt_text": SENTENCE}, "alt_text"),
        ({"type": "input_text", "default_value": SENTENCE}, "default_value"),
    ],
)
def test_a_sentence_with_a_parenthesis_is_fixed_text_on_an_element(
    builder_ctx, item, field
):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [ElementItemCreate(ref="a", **item)],
    )

    assert "formula_errors" not in result
    assert not result.get("errors")
    assert stored(result["ref_to_id_map"]["a"], field)["formula"] == STORED_SENTENCE


@pytest.mark.django_db
def test_a_sentence_with_a_parenthesis_is_fixed_text_on_an_element_update(
    data_fixture, builder_ctx
):
    heading = data_fixture.create_builder_heading_element(
        page=builder_ctx["page"], value="'Old'"
    )

    result = elements.update_element(
        builder_ctx["ctx"], heading.id, ElementChanges(value=SENTENCE)
    )

    assert "formula_errors" not in result
    assert stored(heading.id, "value")["formula"] == STORED_SENTENCE


@pytest.mark.django_db
def test_a_sentence_with_a_parenthesis_is_fixed_text_on_a_notification(builder_ctx):
    result = actions.create_element_actions(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ActionCreate(
                type="notification",
                element=builder_ctx["button"].id,
                event="click",
                title=SENTENCE,
            )
        ],
    )

    assert "formula_errors" not in result
    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    assert action.title["formula"] == STORED_SENTENCE


@pytest.mark.django_db
def test_a_sentence_with_a_parenthesis_is_fixed_text_as_a_search(builder_ctx):
    table = builder_ctx["data_source"].service.specific.table

    result = data_sources.create_data_sources(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            DataSourceCreate(
                ref="a",
                name="Search",
                type="list_rows",
                table_id=table.id,
                search_query=SENTENCE,
            )
        ],
    )

    assert "formula_errors" not in result
    data_source = DataSource.objects.get(id=result["ref_to_id_map"]["a"])
    assert data_source.service.specific.search_query["formula"] == STORED_SENTENCE


@pytest.mark.parametrize(
    "value",
    [
        "Order now (today only)",
        "Today (only)",
        "Sold today (only)",
        "if (you can)",
        "Call me (concat ('a', 'b'))",
    ],
)
def test_needs_formula_leaves_a_sentence_as_text(value):
    assert not needs_formula(value)
