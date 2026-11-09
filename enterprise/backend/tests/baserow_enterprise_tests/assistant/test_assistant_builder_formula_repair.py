"""
Kuma runs the shared formula step, then asks the model for what it left. The value a
data source needs to run is deferred for this, and what the model can't fix is
reported the way Kuma's tools always did.
"""

from typing import Any

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.exceptions import PermissionException
from baserow.core.tools import ToolContext
from baserow.core.user_sources.models import UserSource
from baserow_enterprise.assistant.tools.builder import agents
from baserow_enterprise.assistant.tools.builder.agents import (
    repair_builder_formula_errors,
)
from baserow_enterprise.assistant.tools.builder.tools import (
    create_actions,
    create_collection_elements,
    create_data_sources,
    create_display_elements,
    create_layout_elements,
    create_pages,
    set_theme,
    setup_page,
    setup_user_source,
    update_action,
    update_data_source,
    update_element,
    update_page,
)
from baserow_enterprise.builder.tools import formulas
from baserow_enterprise.builder.tools.formulas import apply_builder_formulas
from baserow_enterprise.builder.tools.types import (
    ActionChanges,
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
from baserow_enterprise.builder.tools.types.user_source import UserSourceSetup

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
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
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
def test_the_model_gets_a_description_of_text_mixed_with_a_marker(site, monkeypatch):
    asked = use_generator(monkeypatch, lambda formulas, context: {})

    create_display_elements(
        site["ctx"],
        page_id=site["page"].id,
        elements=[heading(value="New deal: $formula: the deal name")],
        thought="test",
    )

    [formulas] = asked
    assert formulas["value"].startswith("Text mixing static parts")
    assert formulas["value"].endswith("New deal: $formula: the deal name")


@pytest.mark.django_db
def test_the_model_gets_a_description_of_an_empty_table_column(listed, monkeypatch):
    asked = use_generator(monkeypatch, lambda formulas, context: {})

    create_collection_elements(
        listed["ctx"],
        page_id=listed["page"].id,
        elements=[
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=listed["data_source"].id,
                fields=[TableFieldConfig(name="Total")],
            )
        ],
        thought="test",
    )

    assert asked == [{"fields.0.value": "the Total value from the current record"}]


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
def test_a_row_field_named_by_its_name_goes_to_the_model(listed, monkeypatch):
    by_name = "get('current_record.Name')"
    field_id = listed["table"].field_set.get(name="Name").id
    by_id = f"get('current_record.field_{field_id}')"
    asked = use_generator(monkeypatch, lambda formulas, context: {"value": by_id})

    result = create_display_elements(
        listed["ctx"],
        page_id=listed["page"].id,
        elements=[
            heading(value=f"$formula: {by_name}", parent_element=listed["repeat"].id)
        ],
        thought="test",
    )

    assert asked == [{"value": by_name}]
    element = ElementHandler().get_element(result["ref_to_id_map"]["h"])
    assert element.value["formula"] == by_id


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


# ---------------------------------------------------------------------------
# Actions and setup_page
# ---------------------------------------------------------------------------


@pytest.fixture
def button(data_fixture, site):
    return data_fixture.create_builder_button_element(page=site["page"])


def update_row(site, element, row_id="$formula: the id"):
    field = site["table"].field_set.first()
    return ActionCreate(
        type="update_row",
        element=element,
        table_id=site["table"].id,
        row_id=row_id,
        field_values=[{"field_id": str(field.id), "value": "'x'"}],
    )


@pytest.mark.django_db
def test_update_row_with_a_description_is_created_and_its_row_id_filled(
    site, button, monkeypatch
):
    asked = use_generator(
        monkeypatch, lambda formulas, context: {"row_id": "get('previous_action.1.id')"}
    )

    result = create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[update_row(site, button.id)],
        thought="test",
    )

    assert asked == [{"row_id": "the id"}]
    assert "errors" not in result
    assert "formula_errors" not in result
    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    assert action.service.specific.row_id["formula"] == "get('previous_action.1.id')"


@pytest.mark.django_db
def test_plain_field_value_is_stored_as_fixed_text_with_no_model_call(
    site, button, monkeypatch
):
    def fail(formulas, context):
        raise AssertionError("the model must not be called")

    asked = use_generator(monkeypatch, fail)
    field = site["table"].field_set.first()

    result = create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[
            ActionCreate(
                type="create_row",
                element=button.id,
                event="click",
                table_id=site["table"].id,
                field_values=[{"field_id": str(field.id), "value": "New"}],
            )
        ],
        thought="test",
    )

    assert asked == []
    assert "errors" not in result
    assert "formula_errors" not in result
    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    assert action.service.specific.field_mappings.get().value["formula"] == "'New'"


@pytest.mark.django_db
@pytest.mark.parametrize("generated", [{}, {"field": "'Fixed'"}])
def test_a_field_value_is_written_only_once_the_model_gives_it(
    site, button, monkeypatch, generated
):
    field = site["table"].field_set.first()
    key = f"field_{field.id}"
    use_generator(
        monkeypatch,
        lambda formulas, context: {key: f for f in generated.values()},
    )

    result = create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[
            ActionCreate(
                type="create_row",
                element=button.id,
                table_id=site["table"].id,
                field_values=[{"field_id": str(field.id), "value": "$formula: a name"}],
            )
        ],
        thought="test",
    )

    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    mappings = action.service.specific.field_mappings.all()
    assert [(m.value["formula"], m.enabled) for m in mappings] == [
        (formula, True) for formula in generated.values()
    ]


@pytest.mark.django_db
def test_create_actions_reports_a_generation_failure_as_before(
    site, button, monkeypatch
):
    def fail(formulas, context):
        raise RuntimeError("the model is down")

    use_generator(monkeypatch, fail)

    result = create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[update_row(site, button.id)],
        thought="test",
    )

    assert len(result["created_actions"]) == 1
    assert result["errors"] == [
        f"Formula generation failed for action on 'element_{button.id}': "
        "the model is down"
    ]


@pytest.mark.django_db
def test_create_actions_keeps_refs_from_earlier_calls(site, monkeypatch):
    use_generator(monkeypatch, lambda formulas, context: {})
    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(site["user"], site["workspace"], tool_helpers)
    create_display_elements(
        ctx,
        page_id=site["page"].id,
        elements=[DisplayElementCreate(ref="btn", type="button", value="Go")],
        thought="test",
    )

    result = create_actions(
        ctx,
        page_id=site["page"].id,
        actions=[
            ActionCreate(type="notification", element="btn", title="Hi"),
            ActionCreate(type="notification", element="nope", title="Hi"),
        ],
        thought="test",
    )

    assert [a["element"] for a in result["created_actions"]] == ["btn"]
    assert result["errors"] == ["notification on nope: Element ref 'nope' not found."]


@pytest.mark.django_db
def test_setup_page_creates_and_repairs_a_get_row_description(site, monkeypatch):
    asked = use_generator(
        monkeypatch,
        lambda formulas, context: {
            field: "get('page_parameter.id')" for field in formulas
        },
    )
    site["page"].path = "/product/:id"
    site["page"].path_params = [{"name": "id", "type": "text"}]
    site["page"].save()

    result = setup_page(
        site["ctx"],
        page_id=site["page"].id,
        data_sources=[get_row(site)],
        thought="test",
    )

    assert asked == [{"row_id": "the id"}]
    assert "errors" not in result
    assert "formula_errors" not in result
    data_source = DataSource.objects.get(id=result["created_data_sources"][0]["id"])
    assert data_source.service.specific.row_id["formula"] == "get('page_parameter.id')"


@pytest.mark.django_db
def test_setup_page_repairs_each_phase_before_the_next_one(site, monkeypatch):
    order = []
    real = agents.repair_builder_formula_errors

    def recording(tool_context, tool_helpers, page, entries):
        order.append(
            (
                {entry.kind for entry in entries},
                DataSource.objects.filter(page=page).count(),
                BuilderWorkflowAction.objects.filter(page=page).count(),
            )
        )
        return real(tool_context, tool_helpers, page, entries)

    monkeypatch.setattr(agents, "repair_builder_formula_errors", recording)
    use_generator(
        monkeypatch, lambda formulas, context: {field: "'x'" for field in formulas}
    )

    result = setup_page(
        site["ctx"],
        page_id=site["page"].id,
        data_sources=[
            DataSourceCreate(
                ref="rows",
                name="Rows",
                type="list_rows",
                table_id=site["table"].id,
                search_query="$formula: the query",
            )
        ],
        elements=[ElementItemCreate(ref="b", type="button", value="$formula: label")],
        actions=[ActionCreate(type="notification", element="b", title="$formula: t")],
        thought="test",
    )

    assert order == [
        ({"data_source"}, 1, 0),
        ({"element"}, 1, 0),
        ({"action"}, 1, 1),
    ]
    assert "errors" not in result
    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    assert action.title["formula"] == "'x'"


@pytest.mark.django_db
def test_setup_page_keeps_refs_and_reuses_data_sources(site, monkeypatch):
    use_generator(monkeypatch, lambda formulas, context: {})
    existing = DataSource.objects.get(
        id=create_data_sources(
            site["ctx"],
            page_id=site["page"].id,
            data_sources=[
                DataSourceCreate(
                    ref="rows", name="Rows", type="list_rows", table_id=site["table"].id
                )
            ],
            thought="test",
        )["ref_to_id_map"]["rows"]
    )

    first = setup_page(
        site["ctx"],
        page_id=site["page"].id,
        data_sources=[
            DataSourceCreate(
                ref="again", name="ROWS", type="list_rows", table_id=site["table"].id
            )
        ],
        elements=[ElementItemCreate(ref="box", type="simple_container")],
        thought="test",
    )
    second = setup_page(
        site["ctx"],
        page_id=site["page"].id,
        elements=[
            ElementItemCreate(
                ref="child", type="heading", value="Hi", parent_element="box"
            ),
            ElementItemCreate(
                ref="list",
                type="table",
                data_source="again",
                fields=[TableFieldConfig(name="Name")],
            ),
        ],
        thought="test",
    )

    assert "created_data_sources" not in first
    assert "errors" not in second
    elements = {e["ref"]: e["id"] for e in second["created_elements"]}
    assert (
        Element.objects.get(id=elements["child"]).parent_element_id
        == first["created_elements"][0]["id"]
    )
    assert Element.objects.get(id=elements["list"]).specific.data_source_id == (
        existing.id
    )


@pytest.mark.django_db
def test_setup_page_words_what_the_repair_could_not_fill_as_before(site, monkeypatch):
    def fail(formulas, context):
        raise RuntimeError("the model is down")

    use_generator(monkeypatch, fail)

    result = setup_page(
        site["ctx"],
        page_id=site["page"].id,
        data_sources=[get_row(site)],
        elements=[ElementItemCreate(ref="b", type="button", value="$formula: label")],
        actions=[ActionCreate(type="notification", element="b", title="$formula: t")],
        thought="test",
    )

    assert result["errors"] == [
        "Formula generation failed for data source 'Row': the model is down",
        "Formula generation failed for 'b': the model is down",
        "Formula generation failed for action on 'b': the model is down",
    ]
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_setup_page_fills_a_link_page_parameter_description(site, monkeypatch):
    asked = use_generator(
        monkeypatch, lambda formulas, context: {"page_param_0": "'7'"}
    )
    target = Page.objects.create(
        builder=site["builder"],
        name="Target",
        order=100,
        path="/target/:id",
        path_params=[{"name": "id", "type": "text"}],
    )

    result = setup_page(
        site["ctx"],
        page_id=site["page"].id,
        elements=[
            ElementItemCreate(
                ref="go",
                type="link",
                value="Go",
                navigation_type="page",
                navigate_to_page_id=target.id,
                link_page_parameters=[{"name": "id", "value": "$formula: the id"}],
            )
        ],
        thought="test",
    )

    assert asked == [{"page_param_0": "the id"}]
    assert "errors" not in result
    element = Element.objects.get(id=result["created_elements"][0]["id"]).specific
    assert element.page_parameters[0]["value"]["formula"] == "'7'"


@pytest.mark.django_db
def test_setup_user_source_keeps_its_shape_and_reuses_on_the_same_table(
    data_fixture, site
):
    data_fixture.create_email_field(table=site["table"], name="Email")
    arguments = dict(
        application_id=site["builder"].id,
        setup=UserSourceSetup(name="People", table_id=site["table"].id),
        thought="test",
    )

    first = setup_user_source(site["ctx"], **arguments)
    second = setup_user_source(site["ctx"], **arguments)

    assert set(first) == {"user_source_id", "table_id", "roles", "login_page_id"}
    assert second["user_source_id"] == first["user_source_id"]
    assert UserSource.objects.filter(application=site["builder"]).count() == 1


@pytest.mark.django_db
def test_setup_user_source_reports_a_bad_table_as_before(data_fixture, site):
    result = setup_user_source(
        site["ctx"],
        application_id=site["builder"].id,
        setup=UserSourceSetup(name="People", table_id=site["table"].id),
        thought="test",
    )

    assert "missing required fields: email" in result["error"]


@pytest.mark.django_db
def test_set_theme_keeps_its_shape(site):
    result = set_theme(
        site["ctx"],
        application_id=site["builder"].id,
        theme_name="eclipse",
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["application_id"] == site["builder"].id
    assert result["theme"] == "eclipse"
    assert result["description"]


@pytest.mark.django_db
def test_set_theme_reports_a_theme_it_can_not_load_as_before(site, monkeypatch):
    monkeypatch.setattr(
        "baserow_enterprise.builder.tools.themes._load_theme_data", lambda name: None
    )

    result = set_theme(
        site["ctx"],
        application_id=site["builder"].id,
        theme_name="eclipse",
        thought="test",
    )

    assert result == {
        "status": "error",
        "application_id": site["builder"].id,
        "theme": "eclipse",
        "error": "Theme template 'eclipse' could not be loaded.",
    }


# ---------------------------------------------------------------------------
# What the repair reads, and a shared page data source
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_button(data_fixture, site):
    return data_fixture.create_builder_button_element(page=site["builder"].shared_page)


@pytest.mark.django_db
def test_the_repair_reads_the_shared_page_for_a_shared_page_action(
    site, button, shared_button, monkeypatch
):
    pages = {}

    def generate(formulas, context):
        pages[next(iter(formulas.values()))] = context.page
        return {}

    use_generator(monkeypatch, generate)

    create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[
            ActionCreate(
                type="notification", element=shared_button.id, title="$formula: header"
            ),
            ActionCreate(
                type="notification", element=button.id, title="$formula: body"
            ),
        ],
        thought="test",
    )

    assert pages == {
        "header": site["builder"].shared_page,
        "body": site["page"],
    }


@pytest.mark.django_db
def test_kuma_keeps_a_shared_page_action_off_a_data_source_of_one_page(
    data_fixture, site, shared_button
):
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=site["page"], table=site["table"], name="Rows"
    )
    tool_helpers = site["ctx"].deps.tool_helpers
    tool_helpers.request_context[f"builder_page_{site['page'].id}"] = {
        "element_refs": {},
        "data_source_refs": {"rows": data_source.id},
    }

    result = create_actions(
        site["ctx"],
        page_id=site["page"].id,
        actions=[
            ActionCreate(
                type="refresh_data_source",
                element=shared_button.id,
                data_source=data_source.id,
            ),
            ActionCreate(
                type="refresh_data_source",
                element=shared_button.id,
                data_source="rows",
            ),
        ],
        thought="test",
    )

    assert result["created_actions"] == []
    assert len(result["errors"]) == 2
    assert all("shared page" in error for error in result["errors"])


@pytest.mark.django_db
def test_kuma_update_action_fills_a_description(site, button, monkeypatch):
    action = BuilderWorkflowAction.objects.get(
        id=create_actions(
            site["ctx"],
            page_id=site["page"].id,
            actions=[ActionCreate(type="notification", element=button.id, title="Old")],
            thought="test",
        )["created_actions"][0]["id"]
    )
    asked = use_generator(
        monkeypatch, lambda formulas, context: {"title": "get('page_parameter.id')"}
    )

    result = update_action(
        site["ctx"],
        action_id=action.id,
        changes=ActionChanges(title="$formula: the id"),
        thought="test",
    )

    assert asked == [{"title": "the id"}]
    assert result["updated_action"]["id"] == action.id
    assert "errors" not in result
    assert action.specific.title["formula"] == "get('page_parameter.id')"


@pytest.mark.django_db
def test_kuma_update_action_says_the_old_value_was_kept(site, button, monkeypatch):
    action = BuilderWorkflowAction.objects.get(
        id=create_actions(
            site["ctx"],
            page_id=site["page"].id,
            actions=[ActionCreate(type="notification", element=button.id, title="Old")],
            thought="test",
        )["created_actions"][0]["id"]
    )
    use_generator(monkeypatch, lambda formulas, context: {})

    result = update_action(
        site["ctx"],
        action_id=action.id,
        changes=ActionChanges(title="$formula: the id"),
        thought="test",
    )

    assert result["errors"] == [
        "No valid formula was generated for title. The previous value was kept."
    ]
    assert action.specific.title["formula"] == "'Old'"
