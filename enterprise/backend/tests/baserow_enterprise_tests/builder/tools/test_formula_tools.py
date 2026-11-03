"""The shared formula step for each kind of item, without a model."""

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.graph.types import GraphPointPosition
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
