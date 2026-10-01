import pytest

from baserow.core.graph.types import GraphPointPosition
from baserow_enterprise.assistant.evals.datasets.builder import (
    _changes_theme_scenario,
    _check_changes_theme,
    _check_creates_data_source_with_repeat,
    _check_creates_new_page_not_modifies_existing,
    _creates_data_source_with_repeat_scenario,
    _creates_new_page_not_modifies_existing_scenario,
)
from baserow_enterprise.assistant.evals.types import EvalRunOutput
from baserow_enterprise.assistant.tools.builder.themes import apply_theme


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
