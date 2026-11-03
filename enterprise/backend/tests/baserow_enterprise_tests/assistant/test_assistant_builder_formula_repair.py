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
    create_collection_elements,
    create_data_sources,
    create_display_elements,
    create_layout_elements,
    create_pages,
    update_data_source,
    update_element,
    update_page,
)
from baserow_enterprise.builder.tools import formulas
from baserow_enterprise.builder.tools.formulas import apply_builder_formulas
from baserow_enterprise.builder.tools.types import (
    ActionCreate,
    CollectionElementCreate,
    DataSourceCreate,
    DataSourceUpdate,
    DisplayElementCreate,
    ElementItemCreate,
    ElementUpdate,
    LayoutElementCreate,
    PageCreate,
    PageUpdate,
    TableFieldConfig,
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


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------


@pytest.fixture
def listed(data_fixture, site):
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=site["page"], table=site["table"], name="People"
    )
    repeat = data_fixture.create_builder_repeat_element(
        page=site["page"], data_source=data_source
    )
    return {**site, "data_source": data_source, "repeat": repeat}


def heading(ref="h", value="Hi", **kwargs):
    return DisplayElementCreate(ref=ref, type="heading", value=value, **kwargs)


@pytest.mark.django_db
def test_an_explicit_element_formula_needs_no_model(site, monkeypatch):
    asked = use_generator(monkeypatch, lambda formulas, context: {})

    result = create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[heading(value="$formula: get('page_parameter.id')")],
        thought="test",
    )

    assert asked == []
    element = ElementHandler().get_element(result["ref_to_id_map"]["h"])
    assert element.value["formula"] == "get('page_parameter.id')"


@pytest.mark.django_db
def test_a_refused_explicit_formula_in_a_repeat_goes_to_the_model(listed, monkeypatch):
    missing = "get('data_source.999999.0.id')"
    asked = use_generator(
        monkeypatch, lambda formulas, context: {"value": "get('current_record.id')"}
    )

    result = create_display_elements(
        listed["ctx"],
        page_id=listed["page"].id,
        elements=[heading(value=missing, parent_element=listed["repeat"].id)],
        thought="test",
    )

    assert asked == [{"value": missing}]
    assert "errors" not in result
    element = ElementHandler().get_element(result["ref_to_id_map"]["h"])
    assert element.value["formula"] == "get('current_record.id')"


@pytest.mark.django_db
def test_create_elements_reports_a_generation_failure_once_per_element(
    site, monkeypatch
):
    def fail(formulas, context):
        raise ValueError("no luck")

    use_generator(monkeypatch, fail)

    result = create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[
            DisplayElementCreate(
                ref="img",
                type="image",
                image_url="$formula: the url",
                alt_text="$formula: the alt text",
            )
        ],
        thought="test",
    )

    assert result["errors"] == ["Formula generation failed for 'img': no luck"]
    assert [item["ref"] for item in result["created_elements"]] == ["img"]


@pytest.mark.django_db
def test_create_elements_stays_silent_on_a_value_the_model_left_out(site, monkeypatch):
    use_generator(monkeypatch, lambda formulas, context: {})

    result = create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[heading(value="$formula: a title")],
        thought="test",
    )

    assert "errors" not in result


@pytest.mark.django_db
def test_created_elements_are_reported_when_generation_can_not_start(site, monkeypatch):
    def broken(*args):
        raise ValueError("no model")

    monkeypatch.setattr(GENERATOR, broken)

    result = create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[heading(value="$formula: a title")],
        thought="test",
    )

    assert [item["ref"] for item in result["created_elements"]] == ["h"]
    assert result["errors"] == ["Formula generation failed for 'h': no model"]


@pytest.mark.django_db
def test_kuma_remembers_element_refs_across_calls(site):
    ctx = site["ctx"]
    first = create_layout_elements(
        ctx,
        page_id=site["page"].id,
        elements=[LayoutElementCreate(ref="box", type="simple_container")],
        thought="test",
    )

    second = create_display_elements(
        ctx,
        page_id=site["page"].id,
        elements=[heading(parent_element="box")],
        thought="test",
    )

    box = first["ref_to_id_map"]["box"]
    assert first["empty_containers"][0]["ref"] == "box"
    assert "empty_containers have no child elements" in first["next_steps"]
    assert second["ref_to_id_map"]["box"] == box
    element = ElementHandler().get_element(second["ref_to_id_map"]["h"])
    assert element.parent_element_id == box


@pytest.mark.django_db
def test_kuma_keeps_its_wording_for_an_unknown_ref(site):
    result = create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[heading(parent_element="nope")],
        thought="test",
    )

    assert result["errors"] == [
        "h: Parent ref 'nope' not found. Define parent elements before children."
    ]
    assert "next_steps" not in result


@pytest.mark.django_db
def test_kuma_children_of_a_remembered_header_stay_on_the_shared_page(site):
    ctx = site["ctx"]
    create_layout_elements(
        ctx,
        page_id=site["page"].id,
        elements=[LayoutElementCreate(ref="top", type="header")],
        thought="test",
    )

    result = create_display_elements(
        ctx,
        page_id=site["page"].id,
        elements=[heading(parent_element="top")],
        thought="test",
    )

    element = ElementHandler().get_element(result["ref_to_id_map"]["h"])
    assert element.page == site["builder"].shared_page


@pytest.mark.django_db
def test_kuma_column_named_like_a_field_shows_that_field(listed, monkeypatch):
    asked = use_generator(monkeypatch, lambda formulas, context: {})

    result = create_collection_elements(
        listed["ctx"],
        page_id=listed["page"].id,
        elements=[
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=listed["data_source"].id,
                fields=[TableFieldConfig(name="Name", value="$formula: the name")],
            )
        ],
        thought="test",
    )

    assert asked == []
    table = ElementHandler().get_element(result["ref_to_id_map"]["t"])
    assert "field_" in table.fields.get().config["value"]["formula"]


@pytest.mark.django_db
def test_kuma_table_columns_are_repaired_by_their_path(listed, monkeypatch):
    asked = use_generator(
        monkeypatch,
        lambda formulas, context: {"fields.0.value": "get('current_record.id')"},
    )

    result = create_collection_elements(
        listed["ctx"],
        page_id=listed["page"].id,
        elements=[
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=listed["data_source"].id,
                fields=[TableFieldConfig(name="Id", value="$formula: the id")],
            )
        ],
        thought="test",
    )

    assert asked == [{"fields.0.value": "the id"}]
    table = ElementHandler().get_element(result["ref_to_id_map"]["t"])
    assert table.fields.get().config["value"]["formula"] == "get('current_record.id')"


@pytest.mark.django_db
def test_kuma_repairs_a_table_button_action_with_its_own_wording(
    data_fixture, listed, monkeypatch
):
    def with_action(self, user, orm_element, page):
        action = data_fixture.create_notification_workflow_action(
            page=page, element=orm_element, event="x_click"
        )
        return [
            (
                action,
                ActionCreate(
                    type="notification",
                    element=self.ref,
                    title="$formula: the title",
                ),
            )
        ]

    def fail(formulas, context):
        raise ValueError("no luck")

    monkeypatch.setattr(ElementItemCreate, "post_create", with_action)
    use_generator(monkeypatch, fail)

    result = create_collection_elements(
        listed["ctx"],
        page_id=listed["page"].id,
        elements=[
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=listed["data_source"].id,
                fields=[TableFieldConfig(name="Go", type="button", label="Go")],
            )
        ],
        thought="test",
    )

    assert result["errors"] == ["Formula generation failed for action on 't': no luck"]
    assert "created_actions" not in result


@pytest.mark.django_db
def test_kuma_update_stores_an_explicit_formula_and_repairs_a_description(
    data_fixture, site, monkeypatch
):
    image = data_fixture.create_builder_image_element(page=site["page"])
    asked = use_generator(monkeypatch, lambda formulas, context: {})

    result = update_element(
        site["ctx"],
        page_id=site["page"].id,
        element=ElementUpdate(
            element_id=image.id,
            image_url="get('page_parameter.id')",
            alt_text="$formula: the alt text",
        ),
        thought="test",
    )

    assert asked == [{"alt_text": "the alt text"}]
    assert result["status"] == "partial"
    assert result["updated_fields"] == ["image_url"]
    assert result["errors"] == [
        "No valid formula was generated for: alt_text. Previous values were retained."
    ]
