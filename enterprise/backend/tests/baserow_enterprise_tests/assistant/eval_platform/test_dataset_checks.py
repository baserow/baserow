"""Behavioral regressions for code checks, without calling a model."""

import pytest

from baserow.contrib.builder.pages.models import Page
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFieldMapping,
)
from baserow.core.graph.types import GraphPointPosition
from baserow_enterprise.assistant.evals.datasets.automation import (
    _check_creates_row_with_field_values,
    _check_creates_update_row_workflow,
    _check_creates_weekly_slack_reminder,
    _check_creates_workflow,
    _creates_row_with_field_values_scenario,
    _creates_update_row_workflow_scenario,
    _creates_weekly_slack_reminder_scenario,
    _creates_workflow_scenario,
)
from baserow_enterprise.assistant.evals.datasets.builder import (
    _back_button_on_page_not_header_scenario,
    _check_back_button_on_page_not_header,
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "defect",
    [
        None,
        "interval",
        "day_of_week",
        "hour",
        "minute",
        "timezone",
        "channel",
        "text",
        "blank_text",
        "missing_workflow",
        "missing_slack",
        "missing_call",
    ],
)
def test_slack_reminder_check_uses_saved_schedule_and_message(data_fixture, defect):
    scenario = _creates_weekly_slack_reminder_scenario(data_fixture)
    schedule = {
        "interval": "WEEK",
        "day_of_week": 1,
        "hour": 9,
        "minute": 0,
        "timezone": "UTC",
    }
    wrong_schedule = {
        "interval": "DAY",
        "day_of_week": 2,
        "hour": 10,
        "minute": 30,
        "timezone": "Europe/Rome",
    }
    saved_schedule = schedule.copy()
    if defect in wrong_schedule:
        saved_schedule[defect] = wrong_schedule[defect]
    message = "Is there anything to demo this week?"
    if defect != "missing_workflow":
        workflow = data_fixture.create_automation_workflow(
            automation=scenario.refs["automation"],
            trigger_type="periodic",
            trigger_service_kwargs=saved_schedule,
        )
        if defect != "missing_slack":
            text = "Other demo message" if defect == "text" else message
            if defect == "blank_text":
                text = ""
            data_fixture.create_automation_node(
                workflow=workflow,
                type="slack_write_message",
                service_kwargs={
                    "channel": "general-other" if defect == "channel" else "general",
                    "text": f"'{text}'",
                },
            )

    # The real argument fixer moved `body` to `text` before saving. Keep the
    # original model payload here, as recorded in the eval trace.
    output = _output(
        tool_calls=[] if defect == "missing_call" else ["create_workflows"],
        messages=[]
        if defect == "missing_call"
        else [
            {
                "role": "assistant",
                "tool_name": "create_workflows",
                "args": {
                    "workflows": [
                        {
                            "trigger": {
                                "type": "periodic",
                                "periodic_interval": schedule,
                            },
                            "nodes": [
                                {
                                    "type": "slack_write_message",
                                    "channel": "#general",
                                    "body" if defect is None else "text": message,
                                }
                            ],
                        }
                    ]
                },
            }
        ],
    )
    checks = _check_creates_weekly_slack_reminder(None, scenario, output)
    assert all(check.passed for check in checks) == (defect is None), checks


@pytest.mark.django_db
@pytest.mark.parametrize("node_type", ["create_row", "local_baserow_create_row"])
@pytest.mark.parametrize(
    "defect",
    [
        None,
        "wrong_trigger_table",
        "wrong_target_table",
        "update_row",
        "disabled",
        "constant_name",
        "wrong_source",
        "swapped_fields",
    ],
)
def test_automation_row_check_uses_saved_configuration(data_fixture, defect, node_type):
    scenario = _creates_row_with_field_values_scenario(data_fixture)
    source, log = scenario.refs["source_table"], scenario.refs["log_table"]
    workflow = data_fixture.create_automation_workflow(
        automation=scenario.refs["automation"],
        trigger_type="rows_created",
        trigger_service_kwargs={
            "table": log if defect == "wrong_trigger_table" else source
        },
    )
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type="create_row",
        service_kwargs={"table": source if defect == "wrong_target_table" else log},
    )
    service = node.service.specific
    if defect == "update_row":
        service.row_id = "1"
        service.save()
    name_field = source.field_set.get(name="Name")
    entry_field = log.field_set.get(name="Entry")
    source_field = log.field_set.get(name="Source")
    name_formula = f"get('previous_node.{trigger.id}[0].{name_field.db_column}')"
    LocalBaserowTableServiceFieldMapping.objects.create(
        service=service,
        field=source_field if defect == "swapped_fields" else entry_field,
        enabled=defect != "disabled",
        value="'Contact'" if defect == "constant_name" else name_formula,
    )
    LocalBaserowTableServiceFieldMapping.objects.create(
        service=service,
        field=entry_field if defect == "swapped_fields" else source_field,
        value="'manual'" if defect == "wrong_source" else "'automation'",
    )
    # The tool accepts registered aliases. The raw payload alone cannot prove
    # that a formula or field mapping was saved correctly.
    output = _output(
        tool_calls=["create_workflows"],
        messages=[
            {
                "role": "assistant",
                "tool_name": "create_workflows",
                "args": {
                    "workflows": [
                        {
                            "trigger": {
                                "type": "rows_created",
                                "rows_triggers_settings": {"table_id": source.id},
                            },
                            "nodes": [
                                {
                                    "type": node_type,
                                    "table_id": log.id,
                                    "values": [
                                        {
                                            "field_id": entry_field.id,
                                            "value": "$formula: trigger Name",
                                        },
                                        {
                                            "field_id": source_field.id,
                                            "value": "automation",
                                        },
                                    ],
                                }
                            ],
                        }
                    ]
                },
            }
        ],
    )
    checks = _check_creates_row_with_field_values(None, scenario, output)
    assert all(check.passed for check in checks) == (defect is None), checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_type", ["update_row", "local_baserow_update_row", "unsupported"]
)
@pytest.mark.parametrize(
    "factory, check, trigger_type, status",
    [
        (
            _creates_workflow_scenario,
            _check_creates_workflow,
            "rows_created",
            "Processing",
        ),
        (
            _creates_update_row_workflow_scenario,
            _check_creates_update_row_workflow,
            "rows_updated",
            "Reviewed",
        ),
    ],
)
def test_update_workflow_checks_accept_production_aliases(
    data_fixture, node_type, factory, check, trigger_type, status
):
    scenario = factory(data_fixture)
    table = scenario.refs["table"]
    workflow = data_fixture.create_automation_workflow(
        automation=scenario.refs["automation"],
        trigger_type=trigger_type,
        trigger_service_kwargs={"table": table},
    )
    trigger = workflow.get_trigger()
    row_id = f"get('previous_node.{trigger.id}[0].id')"
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type="update_row",
        service_kwargs={"table": table, "row_id": row_id},
    )
    values = [{"field_id": table.field_set.get(name="Status").id, "value": status}]
    if trigger_type == "rows_updated":
        values.append(
            {
                "field_id": table.field_set.get(name="Notes").id,
                "value": "Automatically reviewed by automation",
            }
        )
    for value in values:
        LocalBaserowTableServiceFieldMapping.objects.create(
            service=node.service, field_id=value["field_id"], value=repr(value["value"])
        )
    output = _output(
        tool_calls=["create_workflows"],
        messages=[
            {
                "role": "assistant",
                "tool_name": "create_workflows",
                "args": {
                    "workflows": [
                        {
                            "trigger": {
                                "type": "local_baserow_" + trigger_type,
                                "rows_triggers_settings": {"table_id": table.id},
                            },
                            "nodes": [
                                {
                                    "type": node_type,
                                    "table_id": table.id,
                                    "row_id": row_id,
                                    "values": values,
                                }
                            ],
                        }
                    ]
                },
            }
        ],
    )
    checks = check(None, scenario, output)
    assert all(result.passed for result in checks) == (node_type != "unsupported"), (
        checks
    )
    assert output.messages[0]["args"]["workflows"][0]["nodes"][0]["type"] == node_type


@pytest.mark.parametrize("space", [" ", "\u202f", "\u00a0", "\n", "\t"])
def test_documentation_keywords_accept_equivalent_whitespace(space):
    output = _output(
        answer=f"Row history is retained for 14{space}days.",
        tool_calls=["search_user_docs"],
        sources=["https://baserow.io/user-docs/row-history"],
    )
    checks = _make_docs_checks(["row-history"], ["14 days"])(None, None, output)
    assert all(check.passed for check in checks)


@pytest.mark.parametrize("apostrophe", ["'", "\u2018", "\u2019"])
def test_documentation_keywords_accept_typographic_apostrophes(apostrophe):
    checks = _make_docs_checks([], ["doesn't"])(
        None,
        None,
        _output(
            answer=f"The documentation doesn{apostrophe}t establish that feature.",
            tool_calls=["search_user_docs"],
            sources=["https://baserow.io/user-docs/example"],
        ),
    )
    assert all(check.passed for check in checks)


def test_documentation_apostrophe_normalization_preserves_negation():
    checks = _make_docs_checks([], ["doesn't"])(
        None,
        None,
        _output(
            answer="The documentation does establish that feature.",
            tool_calls=["search_user_docs"],
            sources=["https://baserow.io/user-docs/example"],
        ),
    )
    assert not next(c for c in checks if c.name.startswith("answer mentions")).passed


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
@pytest.mark.parametrize("kind", ["button", "link"])
@pytest.mark.parametrize(
    "defect", [None, "inert", "wrong_target", "shared", "wrong_label", "text_link"]
)
def test_back_button_checks_saved_navigation(data_fixture, kind, defect):
    scenario = _back_button_on_page_not_header_scenario(data_fixture)
    builder = scenario.refs["builder"]
    detail = scenario.refs["detail_page"]
    page = builder.shared_page if defect == "shared" else detail
    target = (
        detail
        if defect == "wrong_target"
        else Page.objects.get(builder=builder, path="/list")
    )
    value = "'Go elsewhere'" if defect == "wrong_label" else "'Back to List'"
    if kind == "link":
        data_fixture.create_builder_link_element(
            page=page,
            value=value,
            variant="link" if defect == "text_link" else "button",
            navigation_type="page",
            navigate_to_page_id=None if defect == "inert" else target.id,
        )
    else:
        button = data_fixture.create_builder_button_element(page=page, value=value)
        if defect != "inert":
            data_fixture.create_open_page_workflow_action(
                page=page,
                element=button,
                event="click",
                navigation_type="page",
                navigate_to_page=target,
            )
    output = _output(
        tool_calls=["create_display_elements"],
        messages=[_element_call([{"type": kind, "value": "Back to List"}])],
    )
    checks = _check_back_button_on_page_not_header(None, scenario, output)
    expected = defect is None or (kind == "button" and defect == "text_link")
    assert all(check.passed for check in checks) == expected, checks


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
