"""
Kuma's builder tools ask the model for formulas only after their writes commit, and
write each generated value onto a freshly loaded object, so a change made while the
model ran is kept.
"""

from typing import Any, Callable

from django.db import connection

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.actions import UpdateElementActionType
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.formula import BaserowFormulaObject
from baserow_enterprise.assistant.tools.builder.tools import (
    create_actions,
    create_data_sources,
    create_display_elements,
    update_data_source,
    update_element,
)
from baserow_enterprise.assistant.tools.builder.types import (
    ActionCreate,
    DataSourceCreate,
    DataSourceUpdate,
    DisplayElementCreate,
    ElementUpdate,
)
from baserow_enterprise.assistant.tools.builder.types.workflow_action import (
    ParameterMapping,
)

from .utils import make_test_ctx


@pytest.fixture
def site(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True, name="Name")
    return {
        "user": user,
        "workspace": workspace,
        "page": page,
        "table": table,
        "ctx": make_test_ctx(user, workspace),
    }


def use_generator(
    monkeypatch: pytest.MonkeyPatch,
    generate: Callable[[dict[str, str], Any], dict[str, str]],
) -> list[bool]:
    """
    Replace the builder formula generator, recording whether each call ran inside
    a transaction.
    """

    in_atomic: list[bool] = []

    def recording_generate(formulas: dict[str, str], context: Any) -> dict[str, str]:
        in_atomic.append(connection.in_atomic_block)
        return generate(formulas, context)

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.get_formula_generator",
        lambda *args: recording_generate,
    )
    return in_atomic


def generated(value: str) -> Callable[[dict[str, str], Any], dict[str, str]]:
    return lambda formulas, context: {field: value for field in formulas}


def formula(value: Any) -> str:
    return value["formula"] if isinstance(value, dict) else value


@pytest.mark.django_db(transaction=True)
def test_element_formulas_are_generated_outside_the_transaction(site, monkeypatch):
    in_atomic = use_generator(monkeypatch, generated("'Generated'"))

    create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[
            DisplayElementCreate(ref="h", type="heading", value="$formula: a title")
        ],
        thought="test",
    )

    assert in_atomic == [False]
    heading = Element.objects.get(page=site["page"]).specific
    assert formula(heading.value) == "'Generated'"


@pytest.mark.django_db(transaction=True)
def test_data_source_formulas_are_generated_outside_the_transaction(site, monkeypatch):
    in_atomic = use_generator(monkeypatch, generated("get('page_parameter.id')"))

    create_data_sources(
        site["ctx"],
        page_id=site["page"].id,
        data_sources=[
            DataSourceCreate(
                ref="ds",
                name="Item",
                type="get_row",
                table_id=site["table"].id,
                row_id="$formula: the id page parameter",
            )
        ],
        thought="test",
    )

    assert in_atomic == [False]
    data_source = DataSource.objects.get(page=site["page"])
    assert formula(data_source.service.specific.row_id) == "get('page_parameter.id')"


@pytest.mark.django_db(transaction=True)
def test_update_data_source_generates_outside_the_transaction(
    data_fixture, site, monkeypatch
):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
    )
    in_atomic = use_generator(monkeypatch, generated("get('page_parameter.id')"))

    result = update_data_source(
        site["ctx"],
        page_id=site["page"].id,
        data_source=DataSourceUpdate(
            data_source_id=data_source.id, row_id="$formula: the id page parameter"
        ),
        thought="test",
    )

    assert in_atomic == [False]
    assert result["status"] == "ok"
    service = DataSource.objects.get(id=data_source.id).service.specific
    assert formula(service.row_id) == "get('page_parameter.id')"


@pytest.mark.django_db(transaction=True)
def test_update_data_source_keeps_the_old_value_when_generation_fails(
    data_fixture, site, monkeypatch
):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
    )

    def fail(formulas: dict[str, str], context: Any) -> dict[str, str]:
        raise ValueError("no formula")

    use_generator(monkeypatch, fail)

    result = update_data_source(
        site["ctx"],
        page_id=site["page"].id,
        data_source=DataSourceUpdate(
            data_source_id=data_source.id,
            name="Renamed",
            row_id="$formula: the id page parameter",
        ),
        thought="test",
    )

    assert result["status"] == "partial"
    assert "row_id" in result["errors"][0]
    data_source.refresh_from_db()
    assert data_source.name == "Renamed"
    assert formula(data_source.service.specific.row_id) == "'1'"


@pytest.mark.django_db(transaction=True)
def test_update_element_generates_outside_the_transaction(
    data_fixture, site, monkeypatch
):
    heading = data_fixture.create_builder_heading_element(
        page=site["page"], value="'Old'"
    )
    in_atomic = use_generator(monkeypatch, generated("'New'"))

    update_element(
        site["ctx"],
        page_id=site["page"].id,
        element=ElementUpdate(element_id=heading.id, value="$formula: a new title"),
        thought="test",
    )

    assert in_atomic == [False]
    heading.refresh_from_db()
    assert formula(heading.value) == "'New'"


@pytest.mark.django_db(transaction=True)
def test_action_formulas_are_generated_outside_the_transaction(
    data_fixture, site, monkeypatch
):
    button = data_fixture.create_builder_button_element(page=site["page"])
    in_atomic = use_generator(monkeypatch, generated("'Saved'"))

    create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[
            ActionCreate(
                type="notification",
                element=button.id,
                event="click",
                title="$formula: a saved message",
                description="$formula: a saved description",
            )
        ],
        thought="test",
    )

    assert in_atomic == [False]
    action = BuilderWorkflowAction.objects.get(page=site["page"]).specific
    assert formula(action.title) == "'Saved'"
    assert formula(action.description) == "'Saved'"


@pytest.mark.django_db(transaction=True)
def test_element_change_made_while_generating_is_kept(site, monkeypatch):
    def change_level_then_generate(
        formulas: dict[str, str], context: Any
    ) -> dict[str, str]:
        heading = Element.objects.get(page=site["page"]).specific
        UpdateElementActionType.do(site["user"], heading, {"level": 3})
        return {field: "'Generated'" for field in formulas}

    use_generator(monkeypatch, change_level_then_generate)

    create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[
            DisplayElementCreate(
                ref="h", type="heading", value="$formula: a title", level=1
            )
        ],
        thought="test",
    )

    heading = Element.objects.get(page=site["page"]).specific
    assert heading.level == 3
    assert formula(heading.value) == "'Generated'"


@pytest.mark.django_db(transaction=True)
def test_element_update_made_while_generating_is_kept(data_fixture, site, monkeypatch):
    heading = data_fixture.create_builder_heading_element(
        page=site["page"], value="'Old'", level=1
    )

    def change_level_then_generate(
        formulas: dict[str, str], context: Any
    ) -> dict[str, str]:
        fresh = Element.objects.get(id=heading.id).specific
        UpdateElementActionType.do(site["user"], fresh, {"level": 3})
        return {field: "'New'" for field in formulas}

    use_generator(monkeypatch, change_level_then_generate)

    update_element(
        site["ctx"],
        page_id=site["page"].id,
        element=ElementUpdate(element_id=heading.id, value="$formula: a new title"),
        thought="test",
    )

    heading.refresh_from_db()
    assert heading.level == 3
    assert formula(heading.value) == "'New'"


@pytest.mark.django_db(transaction=True)
def test_open_page_change_made_while_generating_is_kept(
    data_fixture, site, monkeypatch
):
    button = data_fixture.create_builder_button_element(page=site["page"])
    query = {"name": "q", "value": BaserowFormulaObject.create("'kept'")}

    def change_query_then_generate(
        formulas: dict[str, str], context: Any
    ) -> dict[str, str]:
        action = BuilderWorkflowAction.objects.get(page=site["page"]).specific
        action.query_parameters = [query]
        action.save(update_fields=["query_parameters"])
        return {field: "get('page_parameter.id')" for field in formulas}

    use_generator(monkeypatch, change_query_then_generate)

    create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[
            ActionCreate(
                type="open_page",
                element=button.id,
                event="click",
                navigate_to_page_id=site["page"].id,
                page_parameters=[
                    ParameterMapping(name="id", value="$formula: the current id")
                ],
            )
        ],
        thought="test",
    )

    action = BuilderWorkflowAction.objects.get(page=site["page"]).specific
    assert [p["name"] for p in action.query_parameters] == ["q"]
    assert formula(action.page_parameters[0]["value"]) == "get('page_parameter.id')"
