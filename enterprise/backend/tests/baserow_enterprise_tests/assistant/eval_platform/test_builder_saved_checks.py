from typing import Any

import pytest

from baserow.contrib.builder.elements.actions import UpdateElementActionType
from baserow.core.graph.types import GraphPointPosition
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.datasets.builder import (
    _changes_theme_scenario,
    _check_changes_theme,
    _check_creates_data_source_with_repeat,
    _check_creates_new_page_not_modifies_existing,
    _check_menu_adds_link_keeps_button,
    _check_menu_adds_pages_one_by_one,
    _check_menu_button_opens_page,
    _check_menu_removes_sub_link,
    _check_menu_renames_button,
    _creates_data_source_with_repeat_scenario,
    _creates_new_page_not_modifies_existing_scenario,
    _site_header_menu_scenario,
)
from baserow_enterprise.assistant.evals.types import EvalRunOutput, EvalScenario
from baserow_enterprise.assistant.tools.builder import helpers
from baserow_enterprise.assistant.tools.builder.themes import apply_theme
from baserow_enterprise.assistant.tools.builder.types import (
    ActionCreate,
    ElementUpdate,
    MenuItemAdd,
    MenuItemUpdate,
)
from baserow_enterprise.assistant.tools.builder.types.menu_items import new_menu_link


def _output(*calls):
    return EvalRunOutput(
        answer="Done",
        tool_calls=[name for name, _ in calls],
        messages=[
            {"role": "assistant", "tool_name": name, "args": args}
            for name, args in calls
        ],
        tool_error_count=0,
        tool_error_hint="",
        sources=[],
        request_count=1,
        duration_s=0,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "defect",
    [
        None,
        "wrong_source",
        "wrong_table",
        "other_page",
        "no_service",
        "heading_outside",
    ],
)
def test_repeat_check_uses_saved_binding_after_argument_repair(data_fixture, defect):
    scenario = _creates_data_source_with_repeat_scenario(data_fixture)
    builder, table = scenario.refs["builder"], scenario.refs["table"]
    page = data_fixture.create_builder_page(
        builder=builder, name="Products", path="/products"
    )
    other_page = data_fixture.create_builder_page(builder=builder, path="/other")
    other_table = data_fixture.create_database_table(database=table.database)
    source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=other_page if defect == "other_page" else page,
        name="All Products",
        table=other_table if defect == "wrong_table" else table,
    )
    if defect == "no_service":
        source.service.delete()
    binding = source
    if defect == "wrong_source":
        binding = data_fixture.create_builder_local_baserow_list_rows_data_source(
            page=page,
            table=other_table,
        )
    repeat = data_fixture.create_builder_repeat_element(page=page, data_source=binding)
    data_fixture.create_builder_heading_element(
        page=page,
        value="'Product'",
        reference_element=repeat,
        position=GraphPointPosition.SOUTH
        if defect == "heading_outside"
        else GraphPointPosition.CHILD,
    )
    # Rejected/repaired requests are not a description of what was actually saved.
    output = _output(
        ("create_pages", {}),
        ("create_collection_elements", {"elements": None}),
        ("setup_page", []),
    )
    checks = _check_creates_data_source_with_repeat(None, scenario, output)
    assert all(check.passed for check in checks) == (defect is None), checks


@pytest.mark.django_db
@pytest.mark.parametrize("saved_theme", ["midnight", "eclipse"])
def test_theme_check_uses_saved_theme_after_argument_repair(data_fixture, saved_theme):
    scenario = _changes_theme_scenario(data_fixture)
    apply_theme(scenario.refs["builder"], saved_theme, scenario.user)
    checks = _check_changes_theme(None, scenario, _output(("set_theme", [])))
    assert all(check.passed for check in checks) == (saved_theme == "midnight"), checks


@pytest.mark.django_db
def test_new_page_check_tolerates_repaired_argument_root(data_fixture):
    scenario = _creates_new_page_not_modifies_existing_scenario(data_fixture)
    page = data_fixture.create_builder_page(
        builder=scenario.refs["builder"], path="/new"
    )
    data_fixture.create_builder_heading_element(page=page)
    data_fixture.create_builder_text_element(page=page)
    checks = _check_creates_new_page_not_modifies_existing(
        None, scenario, _output(("create_pages", {}), ("setup_page", []))
    )
    assert all(check.passed for check in checks), checks


def _update_menu(scenario: EvalScenario, **changes: Any) -> None:
    helpers.update_element(
        scenario.user,
        ElementUpdate(element_id=scenario.refs["menu"].id, **changes),
    )


def _rebuild_as_page_links(scenario: EvalScenario, *names: str) -> None:
    """Replace the menu the way Kuma did before items kept their uid."""

    page = scenario.refs["pages"]["Home"]
    UpdateElementActionType.do(
        scenario.user,
        scenario.refs["menu"],
        {"menu_items": [new_menu_link(name, page.id) for name in names]},
    )


def _add_contact_link(scenario: EvalScenario, fx: Fixtures) -> None:
    contact = scenario.refs["pages"]["Contact"]
    _update_menu(
        scenario, add_menu_items=[MenuItemAdd(name="Contact", page_id=contact.id)]
    )


def _rename_help(scenario: EvalScenario, fx: Fixtures) -> None:
    help_uid = scenario.pre_state["uids"]["Help"]
    _update_menu(
        scenario, update_menu_items=[MenuItemUpdate(uid=help_uid, name="Support")]
    )


def _remove_pricing(scenario: EvalScenario, fx: Fixtures) -> None:
    _update_menu(scenario, remove_menu_items=[scenario.pre_state["uids"]["Pricing"]])


def _open_about_on_help_click(scenario: EvalScenario, fx: Fixtures) -> None:
    helpers.create_workflow_action(
        scenario.user,
        scenario.refs["pages"]["Home"],
        ActionCreate(
            type="open_page",
            element=scenario.refs["menu"].id,
            event=f"{scenario.pre_state['uids']['Help']}_click",
            navigate_to_page_id=scenario.refs["pages"]["About"].id,
        ),
        {},
        {},
    )


def _add_blog_then_careers(scenario: EvalScenario, fx: Fixtures) -> None:
    builder = scenario.refs["builder"]
    for name, path in (("Blog", "/blog"), ("Careers", "/careers")):
        page = fx.create_builder_page(builder=builder, name=name, path=path)
        _update_menu(scenario, add_menu_items=[MenuItemAdd(name=name, page_id=page.id)])


MENU_CASES = {
    "adds link": (_check_menu_adds_link_keeps_button, _add_contact_link),
    "renames button": (_check_menu_renames_button, _rename_help),
    "removes sub-link": (_check_menu_removes_sub_link, _remove_pricing),
    "button opens page": (_check_menu_button_opens_page, _open_about_on_help_click),
    "adds pages one by one": (
        _check_menu_adds_pages_one_by_one,
        _add_blog_then_careers,
    ),
}


@pytest.mark.django_db
@pytest.mark.parametrize("case", MENU_CASES)
@pytest.mark.parametrize("outcome", ["unchanged", "edited", "rebuilt"])
def test_menu_checks_pass_only_when_the_edit_keeps_the_items(
    data_fixture, case: str, outcome: str
):
    check, edit = MENU_CASES[case]
    scenario = _site_header_menu_scenario(data_fixture)
    if outcome == "edited":
        edit(scenario, data_fixture)
    elif outcome == "rebuilt":
        edit(scenario, data_fixture)
        _rebuild_as_page_links(scenario, "Home", "Products", "Divider", "Help")

    checks = check(None, scenario, _output())

    assert all(result.passed for result in checks) == (outcome == "edited"), checks
