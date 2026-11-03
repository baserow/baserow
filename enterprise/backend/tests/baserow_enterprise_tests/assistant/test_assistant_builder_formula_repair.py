"""
Kuma runs the shared formula step, then asks the model for what it left. The value a
data source needs to run is deferred for this, and what the model can't fix is
reported the way Kuma's tools always did.
"""

from typing import Any

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import PermissionException
from baserow.core.tools import ToolContext
from baserow_enterprise.assistant.tools.builder import agents
from baserow_enterprise.assistant.tools.builder.agents import (
    repair_builder_formula_errors,
)
from baserow_enterprise.assistant.tools.builder.tools import (
    create_data_sources,
    create_pages,
    update_data_source,
    update_page,
)
from baserow_enterprise.builder.tools import formulas
from baserow_enterprise.builder.tools.formulas import apply_builder_formulas
from baserow_enterprise.builder.tools.types import (
    ActionCreate,
    DataSourceCreate,
    DataSourceUpdate,
    DisplayElementCreate,
    PageCreate,
    PageUpdate,
)

from .utils import create_fake_tool_helpers, make_test_ctx

GENERATOR = "baserow_enterprise.assistant.tools.builder.agents.get_formula_generator"


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
        "builder": builder,
        "page": page,
        "table": table,
        "ctx": make_test_ctx(user, workspace),
    }


def get_row(site: dict[str, Any], row_id: str = "$formula: the id") -> DataSourceCreate:
    return DataSourceCreate(
        ref="row",
        name="Row",
        type="get_row",
        table_id=site["table"].id,
        row_id=row_id,
    )


def use_generator(monkeypatch, generate) -> list[dict[str, str]]:
    asked: list[dict[str, str]] = []

    def recording(formulas, context):
        asked.append(dict(formulas))
        return generate(formulas, context)

    monkeypatch.setattr(GENERATOR, lambda *args: recording)
    return asked


@pytest.mark.django_db
def test_get_row_with_a_description_is_created_and_its_row_id_filled(site, monkeypatch):
    asked = use_generator(
        monkeypatch, lambda formulas, context: {"row_id": "get('page_parameter.id')"}
    )

    result = create_data_sources(
        site["ctx"], site["page"].id, [get_row(site)], thought="test"
    )

    data_source = DataSource.objects.get(page=site["page"])
    assert asked == [{"row_id": "the id"}]
    assert data_source.service.specific.row_id["formula"] == "get('page_parameter.id')"
    assert result == {
        "created_data_sources": [
            {"id": data_source.id, "ref": "row", "name": "Row", "type": "get_row"}
        ],
        "ref_to_id_map": {"row": data_source.id},
    }


@pytest.mark.django_db
def test_an_explicit_formula_needs_no_model(site, monkeypatch):
    asked = use_generator(monkeypatch, lambda formulas, context: {})

    result = create_data_sources(
        site["ctx"],
        site["page"].id,
        [get_row(site, row_id="get('page_parameter.id')")],
        thought="test",
    )

    data_source = DataSource.objects.get(page=site["page"])
    assert asked == []
    assert data_source.service.specific.row_id["formula"] == "get('page_parameter.id')"
    assert "errors" not in result


@pytest.mark.django_db
def test_a_formula_that_does_not_resolve_goes_to_the_model(site, monkeypatch):
    asked = use_generator(
        monkeypatch, lambda formulas, context: {"row_id": "get('page_parameter.id')"}
    )

    create_data_sources(
        site["ctx"],
        site["page"].id,
        [get_row(site, row_id="get('page_parameter.identifier')")],
        thought="test",
    )

    assert asked == [{"row_id": "get('page_parameter.identifier')"}]
    data_source = DataSource.objects.get(page=site["page"])
    assert data_source.service.specific.row_id["formula"] == "get('page_parameter.id')"


@pytest.mark.django_db
def test_a_failed_write_of_an_explicit_formula_does_not_reach_the_model(
    site, monkeypatch
):
    asked = use_generator(monkeypatch, lambda formulas, context: {"row_id": "'9'"})

    def broken(*args):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(formulas, "write_builder_formulas", broken)

    result = create_data_sources(
        site["ctx"],
        site["page"].id,
        [get_row(site, row_id="get('page_parameter.id')")],
        thought="test",
    )

    assert asked == []
    assert result["created_data_sources"][0]["ref"] == "row"
    assert result["errors"] == [
        "Formula generation failed for data source 'Row': Internal error."
    ]
    service = DataSource.objects.get(page=site["page"]).service.specific
    assert service.row_id["formula"] == "''"


@pytest.mark.django_db
def test_create_reports_a_generation_failure_as_before(site, monkeypatch):
    def fail(formulas, context):
        raise ValueError("no luck")

    use_generator(monkeypatch, fail)

    result = create_data_sources(
        site["ctx"], site["page"].id, [get_row(site)], thought="test"
    )

    assert result["created_data_sources"][0]["ref"] == "row"
    assert result["errors"] == [
        "Formula generation failed for data source 'Row': no luck"
    ]
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_create_reports_a_denied_write_as_before(site, monkeypatch):
    use_generator(
        monkeypatch, lambda formulas, context: {"row_id": "get('page_parameter.id')"}
    )

    def denied(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(DataSourceCreate, "update_with_formulas", denied)

    result = create_data_sources(
        site["ctx"], site["page"].id, [get_row(site)], thought="test"
    )

    assert result["errors"] == [
        "Permission denied while configuring data source 'Row'. It was created, "
        "but its formulas were not applied. Do not retry the denied operation."
    ]


@pytest.mark.django_db
def test_create_skips_a_data_source_that_exists(data_fixture, site):
    existing = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=site["page"], table=site["table"], name="Existing"
    )

    result = create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="same_name",
                name="EXISTING",
                type="get_row",
                table_id=site["table"].id,
                row_id="1",
            ),
            DataSourceCreate(
                ref="same_table",
                name="Another",
                type="list_rows",
                table_id=site["table"].id,
            ),
        ],
        thought="test",
    )

    assert result == {
        "created_data_sources": [],
        "ref_to_id_map": {"same_name": existing.id, "same_table": existing.id},
    }


@pytest.mark.django_db
def test_update_reports_a_generation_failure_as_before(data_fixture, site, monkeypatch):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
    )

    def fail(formulas, context):
        raise ValueError("no luck")

    use_generator(monkeypatch, fail)

    result = update_data_source(
        site["ctx"],
        site["page"].id,
        DataSourceUpdate(
            data_source_id=data_source.id, name="New", row_id="$formula: the id"
        ),
        thought="test",
    )

    assert result == {
        "status": "partial",
        "data_source_id": data_source.id,
        "service_type": "local_baserow_get_row",
        "updated_fields": ["name"],
        "errors": [
            "Formula generation failed for row_id: no luck. "
            "The previous value was kept."
        ],
    }
    service = DataSource.objects.get(id=data_source.id).service.specific
    assert service.row_id["formula"] == "'1'"


@pytest.mark.django_db
def test_update_reports_a_missing_formula_as_before(data_fixture, site, monkeypatch):
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=site["page"], table=site["table"]
    )
    use_generator(
        monkeypatch,
        lambda formulas, context: {"search_query": "get('page_parameter.id')"},
    )

    result = update_data_source(
        site["ctx"],
        site["page"].id,
        DataSourceUpdate(
            data_source_id=data_source.id,
            row_id="$formula: a",
            search_query="$formula: b",
        ),
        thought="test",
    )

    assert result["status"] == "partial"
    assert result["updated_fields"] == ["search_query"]
    assert result["errors"] == [
        "No valid formula was generated for row_id. The previous value was kept."
    ]


@pytest.mark.django_db
def test_update_raises_a_denied_write(data_fixture, site, monkeypatch):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
    )
    use_generator(
        monkeypatch, lambda formulas, context: {"row_id": "get('page_parameter.id')"}
    )

    def denied(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(agents, "write_builder_formulas", denied)

    with pytest.raises(PermissionException):
        update_data_source(
            site["ctx"],
            site["page"].id,
            DataSourceUpdate(data_source_id=data_source.id, row_id="$formula: the id"),
            thought="test",
        )


@pytest.mark.django_db
def test_update_data_source_stays_scoped_to_the_given_page(data_fixture, site):
    other_page = data_fixture.create_builder_page(builder=site["builder"])
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=other_page, table=site["table"]
    )

    with pytest.raises(Exception, match="not found"):
        update_data_source(
            site["ctx"],
            site["page"].id,
            DataSourceUpdate(data_source_id=data_source.id, name="New"),
            thought="test",
        )


@pytest.mark.django_db
def test_repair_fills_an_element_and_keeps_what_it_cannot_fix(
    data_fixture, site, monkeypatch
):
    page = site["page"]
    fixed = data_fixture.create_builder_heading_element(page=page, value="''")
    unfixed = data_fixture.create_builder_heading_element(page=page, value="''")
    context = ToolContext(user=site["user"], workspace=site["workspace"])
    formula_errors = apply_builder_formulas(
        context,
        page,
        [
            (
                fixed,
                DisplayElementCreate(
                    ref="a", type="heading", value="$formula: fix me"
                ).to_element_item_create(),
            ),
            (
                unfixed,
                DisplayElementCreate(
                    ref="b", type="heading", value="$formula: impossible"
                ).to_element_item_create(),
            ),
        ],
        "element",
    )

    def generate(formulas, context):
        if "impossible" in formulas.values():
            raise ValueError("no luck")
        return {"value": "'Fixed'"}

    use_generator(monkeypatch, generate)

    remaining = repair_builder_formula_errors(
        context, create_fake_tool_helpers(), page, formula_errors
    )

    heading = ElementHandler().get_element(fixed.id).specific
    assert heading.value["formula"] == "'Fixed'"
    assert [(e["element_id"], e["error"]) for e in remaining] == [
        (unfixed.id, "no luck")
    ]


@pytest.mark.django_db
def test_repair_fills_an_action(data_fixture, site, monkeypatch):
    page = site["page"]
    button = data_fixture.create_builder_button_element(page=page, value="'Go'")
    action = data_fixture.create_notification_workflow_action(
        page=page, element=button, event="click"
    )
    context = ToolContext(user=site["user"], workspace=site["workspace"])
    formula_errors = apply_builder_formulas(
        context,
        page,
        [
            (
                action,
                ActionCreate(
                    element=button.id, type="notification", title="$formula: a title"
                ),
            )
        ],
        "action",
    )
    use_generator(monkeypatch, lambda formulas, context: {"title": "'Hello'"})

    remaining = repair_builder_formula_errors(
        context, create_fake_tool_helpers(), page, formula_errors
    )

    action.refresh_from_db()
    assert remaining == []
    assert action.specific.title["formula"] == "'Hello'"


@pytest.mark.django_db
def test_create_pages_keeps_its_result_shape_and_skips_by_name(data_fixture, site):
    existing = data_fixture.create_builder_page(
        builder=site["builder"], name="Existing", path="/existing"
    )

    result = create_pages(
        site["ctx"],
        site["builder"].id,
        [
            PageCreate(name="existing", path="/other"),
            PageCreate(name="New", path="/new"),
        ],
        thought="test",
    )

    assert [p["name"] for p in result["created_pages"]] == ["New"]
    assert [p["id"] for p in result["existing_pages"]] == [existing.id]
    assert "next_steps" in result
    assert Page.objects.filter(builder=site["builder"], name="New").exists()


@pytest.mark.django_db
def test_update_page_keeps_its_result_shape(site):
    result = update_page(
        site["ctx"],
        PageUpdate(page_id=site["page"].id, name="Renamed"),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["page"]["name"] == "Renamed"
    assert result["updated_fields"] == ["name"]
