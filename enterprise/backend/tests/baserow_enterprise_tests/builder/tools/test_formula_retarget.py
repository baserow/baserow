"""
Formulas are written after the structural update, in a transaction of their own.
An editor can change a link or an open page action in between, so each formula goes
to the parameter it was given for, and none is written when the target changed.
"""

import pytest

from baserow.contrib.builder.elements.models import LinkElement
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import OpenPageWorkflowAction
from baserow_enterprise.builder.tools import actions, elements, formulas
from baserow_enterprise.builder.tools.types import (
    ActionChanges,
    ElementChanges,
    ElementItemCreate,
)

ASKED = [
    {"name": "a", "value": "upper('aa')"},
    {"name": "b", "value": "upper('bb')"},
]


@pytest.fixture
def target(data_fixture, builder_ctx):
    return data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Pair",
        path="/pair/:a/:b",
        path_params=[{"name": "a", "type": "text"}, {"name": "b", "type": "text"}],
    )


def _params(*names):
    return [{"name": name, "value": "'x'"} for name in names]


def _between_phases(monkeypatch, edit):
    """Run ``edit`` after the structural update, before the formulas are written."""

    write = formulas.write_builder_formulas

    def edited_first(*args, **kwargs):
        edit()
        return write(*args, **kwargs)

    monkeypatch.setattr(formulas, "write_builder_formulas", edited_first)


def _reorder(page, model, item_id):
    # What the editor saves when the page's parameters swap places.
    Page.objects.filter(id=page.id).update(
        path="/pair/:b/:a",
        path_params=[{"name": "b", "type": "text"}, {"name": "a", "type": "text"}],
    )
    item = model.objects.get(id=item_id)
    by_name = {param["name"]: param for param in item.page_parameters}
    model.objects.filter(id=item_id).update(
        page_parameters=[by_name["b"], by_name["a"]]
    )


def _stored(model, item_id):
    return {
        param["name"]: param["value"]["formula"]
        for param in model.objects.get(id=item_id).page_parameters
    }


@pytest.fixture
def link(data_fixture, builder_ctx, target):
    return data_fixture.create_builder_link_element(
        page=builder_ctx["page"],
        navigation_type="page",
        navigate_to_page_id=target.id,
        page_parameters=_params("a", "b"),
    )


@pytest.fixture
def opens_pair(data_fixture, builder_ctx, target):
    return data_fixture.create_open_page_workflow_action(
        page=builder_ctx["page"],
        element=builder_ctx["button"],
        event="click",
        navigation_type="page",
        navigate_to_page_id=target.id,
        page_parameters=_params("a", "b"),
    )


@pytest.mark.django_db
def test_a_link_formula_goes_to_its_parameter_after_a_reorder(
    builder_ctx, target, link, monkeypatch
):
    _between_phases(monkeypatch, lambda: _reorder(target, LinkElement, link.id))

    result = elements.update_element(
        builder_ctx["ctx"], link.id, ElementChanges(link_page_parameters=ASKED)
    )

    assert "formula_errors" not in result
    assert _stored(LinkElement, link.id) == {"a": "upper('aa')", "b": "upper('bb')"}


@pytest.mark.django_db
def test_no_link_formula_is_written_after_a_retarget(
    data_fixture, builder_ctx, target, link, monkeypatch
):
    other = data_fixture.create_builder_page(
        builder=builder_ctx["builder"], name="Other", path="/other/:a/:b"
    )

    def retarget():
        LinkElement.objects.filter(id=link.id).update(navigate_to_page_id=other.id)

    _between_phases(monkeypatch, retarget)

    result = elements.update_element(
        builder_ctx["ctx"], link.id, ElementChanges(link_page_parameters=ASKED)
    )

    assert {entry["field"] for entry in result["formula_errors"]} == {
        "page_param_0",
        "page_param_1",
    }
    assert all(
        "opens another page" in entry["error"] for entry in result["formula_errors"]
    )
    assert "upper" not in str(_stored(LinkElement, link.id))


@pytest.mark.django_db
def test_an_open_page_formula_goes_to_its_parameter_after_a_reorder(
    builder_ctx, target, opens_pair, monkeypatch
):
    _between_phases(
        monkeypatch, lambda: _reorder(target, OpenPageWorkflowAction, opens_pair.id)
    )

    result = actions.update_element_action(
        builder_ctx["ctx"], opens_pair.id, ActionChanges(page_parameters=ASKED)
    )

    assert "formula_errors" not in result
    assert _stored(OpenPageWorkflowAction, opens_pair.id) == {
        "a": "upper('aa')",
        "b": "upper('bb')",
    }


@pytest.mark.django_db
def test_no_open_page_formula_is_written_after_a_retarget(
    data_fixture, builder_ctx, target, opens_pair, monkeypatch
):
    other = data_fixture.create_builder_page(
        builder=builder_ctx["builder"], name="Other", path="/other/:a/:b"
    )

    def retarget():
        OpenPageWorkflowAction.objects.filter(id=opens_pair.id).update(
            navigate_to_page_id=other.id
        )

    _between_phases(monkeypatch, retarget)

    result = actions.update_element_action(
        builder_ctx["ctx"], opens_pair.id, ActionChanges(page_parameters=ASKED)
    )

    assert all(
        "opens another page" in entry["error"] for entry in result["formula_errors"]
    )
    assert "upper" not in str(_stored(OpenPageWorkflowAction, opens_pair.id))


@pytest.mark.django_db
def test_no_link_formula_is_written_for_a_parameter_since_removed(
    builder_ctx, target, link, monkeypatch
):
    def rename():
        Page.objects.filter(id=target.id).update(path="/pair/:a/:c")
        LinkElement.objects.filter(id=link.id).update(page_parameters=_params("a", "c"))

    _between_phases(monkeypatch, rename)

    result = elements.update_element(
        builder_ctx["ctx"], link.id, ElementChanges(link_page_parameters=ASKED)
    )

    assert "b is no longer set" in result["formula_errors"][0]["error"]
    assert "upper" not in str(_stored(LinkElement, link.id))


@pytest.mark.django_db
def test_a_new_link_formula_goes_to_its_parameter_after_a_reorder(
    builder_ctx, target, monkeypatch
):
    created = {}
    write = formulas.write_builder_formulas

    def reorder_first(user, kind, source, item, pending):
        created["id"] = source.id
        _reorder(target, LinkElement, source.id)
        return write(user, kind, source, item, pending)

    monkeypatch.setattr(formulas, "write_builder_formulas", reorder_first)

    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="pair",
                type="link",
                value="Pair",
                navigate_to_page_id=target.id,
                link_page_parameters=ASKED,
            )
        ],
    )

    assert "formula_errors" not in result
    assert _stored(LinkElement, created["id"]) == {
        "a": "upper('aa')",
        "b": "upper('bb')",
    }
