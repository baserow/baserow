"""Behavioral regressions for code checks, without calling a model."""

import pytest

from baserow.core.graph.types import GraphPointPosition
from baserow_enterprise.assistant.evals.datasets.builder import (
    _check_creates_app_when_table_exists,
    _check_creates_contact_form,
    _check_creates_landing_page,
    _check_filtered_data_source_via_view,
    _creates_app_when_table_exists_scenario,
    _creates_contact_form_scenario,
    _creates_landing_page_scenario,
    _filtered_data_source_via_view_scenario,
)
from baserow_enterprise.assistant.evals.datasets.docs import _make_docs_checks
from baserow_enterprise.assistant.evals.types import EvalRunOutput


def _output(**overrides):
    values = {
        "answer": "",
        "messages": [],
        "tool_calls": [],
        "tool_error_count": 0,
        "tool_error_hint": "",
        "sources": [],
        "request_count": 1,
        "duration_s": 0,
    }
    return EvalRunOutput(**(values | overrides))


@pytest.mark.parametrize("space", [" ", "\u202f", "\u00a0", "\n", "\t"])
def test_documentation_keywords_accept_equivalent_whitespace(space):
    output = _output(
        answer=f"Row history is retained for 14{space}days.",
        tool_calls=["search_user_docs"],
        sources=["https://baserow.io/user-docs/row-history"],
    )
    checks = _make_docs_checks(["row-history"], ["14 days"])(None, None, output)
    assert all(check.passed for check in checks)


def test_documentation_whitespace_normalization_preserves_other_requirements():
    checks = _make_docs_checks([], ["14 days"])(
        None, None, _output(answer="History is retained for 90\u202fdays.")
    )
    assert [check.passed for check in checks[:3]] == [False, False, False]


def _element_call(elements):
    return {
        "role": "assistant",
        "tool_name": "create_display_elements",
        "args": {"elements": elements},
    }


@pytest.mark.django_db
@pytest.mark.parametrize("navigation_type", ["page", "custom"])
def test_landing_checks_accept_interleaved_page_creation(data_fixture, navigation_type):
    scenario, home, button, output = _landing_page(data_fixture)
    contact = data_fixture.create_builder_page(
        builder=scenario.refs["builder"], name="Contact", path="/contact"
    )
    data_fixture.create_open_page_workflow_action(
        page=home,
        element=button,
        event="click",
        navigation_type=navigation_type,
        navigate_to_page=contact if navigation_type == "page" else None,
        navigate_to_url="'/contact'" if navigation_type == "custom" else "''",
    )
    # Home and its elements can be created before the Contact destination.
    output.tool_calls += ["create_pages", "create_actions"]
    checks = _check_creates_landing_page(None, scenario, output)
    assert all(check.passed for check in checks), checks


def _landing_page(fx, link_variant=None):
    scenario = _creates_landing_page_scenario(fx)
    home = fx.create_builder_page(
        builder=scenario.refs["builder"], name="Home", path="/"
    )
    fx.create_builder_heading_element(page=home, value="'Welcome'")
    fx.create_builder_text_element(page=home, value="'This is our landing page'")
    button = (
        fx.create_builder_link_element(
            page=home,
            value="'Get Started'",
            variant=link_variant,
            navigation_type="custom",
            navigate_to_url="'/contact'",
        )
        if link_variant
        else fx.create_builder_button_element(page=home, value="'Get Started'")
    )
    output = _output(
        tool_calls=["create_pages", "create_display_elements"],
        messages=[
            _element_call(
                [
                    {"type": "heading", "value": "Welcome"},
                    {"type": "text", "value": "This is our landing page"},
                    {
                        "type": "button",
                        "value": "Get Started",
                        "navigation_type": "custom",
                        "navigate_to_url": "/contact",
                    },
                ]
            )
        ],
    )
    return scenario, home, button, output


@pytest.mark.django_db
@pytest.mark.parametrize(
    "variant, target, valid",
    [
        ("button", "/contact", True),
        ("link", "/contact", False),
        ("button", "/wrong", False),
    ],
)
def test_landing_accepts_working_link_button_without_action(
    data_fixture, variant, target, valid
):
    scenario, _, link, output = _landing_page(data_fixture, link_variant=variant)
    link.navigate_to_url = f"'{target}'"
    link.save()
    checks = _check_creates_landing_page(None, scenario, output)
    assert all(check.passed for check in checks) is valid, checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "defect", ["missing", "wrong_target", "wrong_event", "wrong_button"]
)
def test_landing_checks_reject_inert_or_wrong_cta(data_fixture, defect):
    scenario, home, button, output = _landing_page(data_fixture)
    if defect != "missing":
        if defect == "wrong_button":
            button = data_fixture.create_builder_button_element(
                page=home, value="'Other button'"
            )
        data_fixture.create_open_page_workflow_action(
            page=home,
            element=button,
            event="submit" if defect == "wrong_event" else "click",
            navigation_type="custom",
            navigate_to_url="'/wrong'" if defect == "wrong_target" else "'/contact'",
        )
    checks = _check_creates_landing_page(None, scenario, output)
    assert not all(check.passed for check in checks), checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "source",
    ["current_record", "first_row", "mixed", "outside_repeat", "nested_repeat"],
)
def test_project_cards_resolve_both_fields_for_each_record(data_fixture, source):
    scenario = _creates_app_when_table_exists_scenario(data_fixture)
    table = scenario.refs["projects_table"]
    page = data_fixture.create_builder_page(builder=scenario.refs["builder"])
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table
    )
    repeat = data_fixture.create_builder_repeat_element(
        page=page, data_source=data_source
    )
    container = data_fixture.create_builder_column_element(
        page=page, reference_element=repeat, position=GraphPointPosition.CHILD
    )
    if source == "nested_repeat":
        container = data_fixture.create_builder_repeat_element(
            page=page,
            data_source=data_source,
            reference_element=container,
            position=GraphPointPosition.CHILD,
        )
    for name, factory in [
        ("Name", data_fixture.create_builder_heading_element),
        ("Status", data_fixture.create_builder_text_element),
    ]:
        field = table.field_set.get(name=name)
        root = (
            f"data_source.{data_source.id}.0"
            if source == "first_row" or (source == "mixed" and name == "Name")
            else "current_record"
        )
        placement = (
            {"reference_element": repeat, "position": GraphPointPosition.SOUTH}
            if source == "outside_repeat"
            else {"reference_element": container, "position": GraphPointPosition.CHILD}
        )
        factory(page=page, value=f"get('{root}.{field.db_column}')", **placement)
    output = _output(
        tool_calls=["create_pages", "create_data_sources", "create_display_elements"],
        messages=[
            {
                "role": "assistant",
                "tool_name": "create_data_sources",
                "args": {"data_sources": [{"table_id": table.id}]},
            },
            _element_call([{"type": "heading"}, {"type": "text"}]),
        ],
    )
    checks = _check_creates_app_when_table_exists(None, scenario, output)
    assert all(check.passed for check in checks) is (source == "current_record"), checks


@pytest.mark.django_db
def test_contact_form_accepts_primitive_tools_and_requires_submit_action(data_fixture):
    scenario = _creates_contact_form_scenario(data_fixture)
    page = data_fixture.create_builder_page(
        builder=scenario.refs["builder"], name="Contact", path="/contact"
    )
    form = data_fixture.create_builder_form_container_element(page=page)
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=scenario.refs["table"]
    )
    for name in ["name", "email"]:
        element = data_fixture.create_builder_input_text_element(
            page=page, reference_element=form, position=GraphPointPosition.CHILD
        )
        service.field_mappings.create(
            field=scenario.refs[f"{name}_field"],
            value=f"get('form_data.{element.id}')",
            enabled=True,
        )
    action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=form, event="submit", service=service
    )
    output = _output(
        tool_calls=["create_pages", "create_form_elements", "create_actions"]
    )
    checks = _check_creates_contact_form(None, scenario, output)
    assert all(check.passed for check in checks), checks

    action.event = "click"
    action.save()
    assert not all(
        check.passed for check in _check_creates_contact_form(None, scenario, output)
    )


@pytest.mark.django_db
def test_filtered_source_accepts_automatic_routing_and_requires_matching_view(
    data_fixture,
):
    scenario = _filtered_data_source_via_view_scenario(data_fixture)
    table = scenario.refs["table"]
    field = scenario.refs["status_field"]
    pending = field.select_options.get(value="Pending")
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=view, field=field, type="single_select_equal", value=str(pending.id)
    )
    page = data_fixture.create_builder_page(builder=scenario.refs["builder"])
    source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, view=view
    )
    output = _output(
        tool_calls=[
            "create_views",
            "create_view_filters",
            "create_pages",
            "create_data_sources",
        ]
    )
    checks = _check_filtered_data_source_via_view(None, scenario, output)
    assert all(check.passed for check in checks), checks

    source.service.specific.view = data_fixture.create_grid_view(table=table)
    source.service.specific.save()
    assert not all(
        check.passed
        for check in _check_filtered_data_source_via_view(None, scenario, output)
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "group_type,disabled,valid",
    [("AND", False, True), ("OR", False, False), ("AND", True, True)],
)
def test_filtered_source_check_matches_service_group_and_disabled_semantics(
    data_fixture, group_type, disabled, valid
):
    from baserow.contrib.integrations.local_baserow.service_types import (
        LocalBaserowListRowsUserServiceType,
    )
    from baserow.test_utils.pytest_conftest import FakeDispatchContext

    scenario = _filtered_data_source_via_view_scenario(data_fixture)
    table, field = scenario.refs["table"], scenario.refs["status_field"]
    pending = field.select_options.get(value="Pending")
    done = field.select_options.get(value="Done")
    view = data_fixture.create_grid_view(table=table, filters_disabled=disabled)
    group = data_fixture.create_view_filter_group(view=view, filter_type=group_type)
    for option_ids in [str(pending.id), f"{pending.id},{done.id}"]:
        data_fixture.create_view_filter(
            view=view,
            field=field,
            type="single_select_is_any_of",
            value=option_ids,
            group=group,
        )
    page = data_fixture.create_builder_page(builder=scenario.refs["builder"])
    source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, view=view
    )
    model = table.get_model()
    rows = [
        model.objects.create(**{f"{field.db_column}_id": option_id})
        for option_id in [pending.id, done.id, None]
    ]
    actual = LocalBaserowListRowsUserServiceType().get_dispatch_filters(
        source.service.specific, model.objects.all(), model, FakeDispatchContext()
    )
    assert set(actual.values_list("id", flat=True)) == {
        row.id for row in (rows[:1] if valid else rows[:2])
    }
    checks = _check_filtered_data_source_via_view(None, scenario, _output())
    assert all(check.passed for check in checks) is valid, checks
