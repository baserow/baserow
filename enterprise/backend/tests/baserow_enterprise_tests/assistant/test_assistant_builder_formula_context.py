"""Saved formulas must respect the row rendered by a collection element."""

from types import SimpleNamespace

import pytest

from baserow.contrib.builder.elements.models import Element
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow_enterprise.assistant.tools.builder.agents import BuilderFormulaContext
from baserow_enterprise.assistant.tools.builder.tools import (
    create_collection_elements,
    create_data_sources,
    create_display_elements,
    create_layout_elements,
    update_element,
)
from baserow_enterprise.assistant.tools.builder.types import (
    CollectionElementCreate,
    DataSourceCreate,
    DisplayElementCreate,
    ElementUpdate,
    LayoutElementCreate,
    TableFieldConfig,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.assistant.tools.shared import agents as shared_agents
from baserow_enterprise.assistant.tools.shared.formula_utils import formula_object

from .utils import make_test_ctx


@pytest.fixture
def repeated_rows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Title", primary=True)
    ctx = make_test_ctx(user, workspace)
    result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="rows", name="Rows", type="list_rows", table_id=table.id
            )
        ],
        thought="List the existing rows.",
    )
    data_source_id = result["created_data_sources"][0]["id"]
    create_collection_elements(
        ctx,
        page_id=page.id,
        elements=[
            CollectionElementCreate(ref="repeat", type="repeat", data_source="rows")
        ],
        thought="Render each row.",
    )
    create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(
                ref="card", type="simple_container", parent_element="repeat"
            )
        ],
        thought="Group each card's contents.",
    )
    return ctx, page, field, data_source_id


@pytest.mark.django_db
@pytest.mark.parametrize("element_type", ["heading", "text"])
def test_repeated_display_formula_retries_fixed_first_row_reference(
    repeated_rows, monkeypatch, element_type
):
    ctx, page, field, ds_id = repeated_rows
    fixed = f"get('data_source.{ds_id}.0.field_{field.id}')"
    row_relative = f"get('current_record.field_{field.id}')"
    prompts = []

    def generate(_agent, prompt, **kwargs):
        prompts.append(prompt)
        return SimpleNamespace(
            output=shared_agents.FormulaGeneratorOutput(
                generated_formulas={
                    "value": fixed if len(prompts) == 1 else row_relative
                }
            )
        )

    monkeypatch.setattr(shared_agents, "run_agent_sync_with_model", generate)
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="title",
                type=element_type,
                parent_element="card",
                value="$formula: the Title field from the Rows data source",
            )
        ],
        thought="Show each row's title.",
    )
    saved = Element.objects.get(id=result["created_elements"][0]["id"]).specific
    assert saved.value["formula"] == row_relative
    assert len(prompts) == 2
    assert "current_record" in prompts[1]
    assert "Feedback: None" not in prompts[1]
    assert not result.get("errors")

    context = BuilderFormulaContext(page)
    context.load_page_context()
    context.context[f"data_source.{ds_id}"] = [
        {field.db_column: "First"},
        {field.db_column: "Second"},
    ]
    context.context["current_record"] = context.context[f"data_source.{ds_id}"][1]
    assert (
        resolve_formula(saved.value, formula_runtime_function_registry, context)
        == "Second"
    )


@pytest.mark.django_db
def test_explicit_absolute_formula_inside_collection_is_preserved(
    repeated_rows, monkeypatch
):
    ctx, page, field, ds_id = repeated_rows
    absolute = f"get('data_source.{ds_id}.0.field_{field.id}')"

    def no_generation(*args, **kwargs):
        pytest.fail("An explicit valid expression must not be rewritten by a model")

    monkeypatch.setattr(shared_agents, "run_agent_sync_with_model", no_generation)
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="first",
                type="text",
                parent_element="card",
                value=f"$formula: {absolute}",
            )
        ],
        thought="Display the explicitly requested first row.",
    )
    saved = Element.objects.get(id=result["created_elements"][0]["id"]).specific
    assert saved.value["formula"] == absolute
    assert not result.get("errors")


@pytest.mark.django_db
def test_collection_formula_can_reference_another_data_source(
    repeated_rows, data_fixture, monkeypatch
):
    ctx, page, field, ds_id = repeated_rows
    source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=field.table
    )
    absolute = f"get('data_source.{source.id}.0.id')"

    def generate(_agent, prompt, **kwargs):
        assert f"'data_source.{source.id}':" in prompt
        assert f"'data_source.{ds_id}':" not in prompt
        return SimpleNamespace(
            output=shared_agents.FormulaGeneratorOutput(
                generated_formulas={"value": absolute}
            )
        )

    monkeypatch.setattr(shared_agents, "run_agent_sync_with_model", generate)
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="other",
                type="text",
                parent_element="card",
                value="$formula: the first ID from the other source",
            )
        ],
        thought="Show the shared reference next to each row.",
    )
    saved = Element.objects.get(id=result["created_elements"][0]["id"]).specific
    assert saved.value["formula"] == absolute
    assert not result.get("errors")


@pytest.mark.django_db
def test_collection_scope_is_removed_for_page_level_formula(repeated_rows, monkeypatch):
    ctx, page, field, ds_id = repeated_rows
    formulas = iter(
        [
            f"get('current_record.field_{field.id}')",
            f"get('data_source.{ds_id}.0.field_{field.id}')",
        ]
    )
    prompts = []

    def generate(_agent, prompt, **kwargs):
        prompts.append(prompt)
        return SimpleNamespace(
            output=shared_agents.FormulaGeneratorOutput(
                generated_formulas={"value": next(formulas)}
            )
        )

    monkeypatch.setattr(shared_agents, "run_agent_sync_with_model", generate)
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="row",
                type="text",
                parent_element="card",
                value="$formula: the row title",
            ),
            DisplayElementCreate(
                ref="first", type="text", value="$formula: the first title on the page"
            ),
        ],
        thought="Show each row and a page-level summary.",
    )
    assert len(result["created_elements"]) == 2
    assert not result.get("errors")
    assert f"'data_source.{ds_id}':" not in prompts[0]
    assert f"'data_source.{ds_id}':" in prompts[1]
    assert "'current_record':" not in prompts[1]


@pytest.mark.django_db
@pytest.mark.parametrize("with_static_change", [False, True])
def test_failed_collection_formula_update_preserves_value_and_reports_error(
    repeated_rows, monkeypatch, with_static_change
):
    ctx, page, field, ds_id = repeated_rows
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="title", type="text", parent_element="card", value="Original"
            )
        ],
        thought="Create a caption.",
    )
    element_id = result["created_elements"][0]["id"]
    monkeypatch.setattr(
        shared_agents,
        "run_agent_sync_with_model",
        lambda *a, **kw: SimpleNamespace(
            output=shared_agents.FormulaGeneratorOutput(
                generated_formulas={
                    "value": f"get('data_source.{ds_id}.0.field_{field.id}')"
                }
            )
        ),
    )
    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=element_id,
            value="$formula: the Title from this row",
            visibility="logged-in" if with_static_change else None,
        ),
        thought="Update the caption to the current row.",
    )
    saved = Element.objects.get(id=element_id).specific
    assert saved.value["formula"] == "'Original'"
    assert saved.visibility == ("logged-in" if with_static_change else "all")
    assert result["updated_fields"] == (["visibility"] if with_static_change else [])
    assert result["status"] == ("partial" if with_static_change else "error")
    assert result["errors"]
    assert "current_record" in result["errors"][0]


@pytest.mark.django_db
def test_partial_generated_update_reports_only_saved_fields(repeated_rows, monkeypatch):
    ctx, page, field, ds_id = repeated_rows
    created = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="link",
                type="link",
                parent_element="card",
                value="Original",
                navigation_type="custom",
                navigate_to_url="/original",
            )
        ],
        thought="Create a navigable link.",
    )
    element_id = created["created_elements"][0]["id"]
    row_relative = f"get('current_record.field_{field.id}')"
    monkeypatch.setattr(
        shared_agents,
        "run_agent_sync_with_model",
        lambda *a, **kw: SimpleNamespace(
            output=shared_agents.FormulaGeneratorOutput(
                generated_formulas={"value": row_relative}
            )
        ),
    )
    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=element_id,
            value="$formula: this row's Title",
            navigate_to_url="$formula: this row's URL",
        ),
        thought="Update the text and destination.",
    )
    saved = Element.objects.get(id=element_id).specific
    assert saved.value["formula"] == row_relative
    assert saved.navigate_to_url["formula"] == "'/original'"
    assert result["status"] == "partial"
    assert result["updated_fields"] == ["value"]
    assert "navigate_to_url" in result["errors"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("succeeds", [True, False])
def test_button_formula_label_alias_reports_saved_value(
    repeated_rows, monkeypatch, succeeds
):
    ctx, page, field, ds_id = repeated_rows
    created = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="button", type="button", parent_element="card", value="Original"
            )
        ],
        thought="Create a button.",
    )
    element_id = created["created_elements"][0]["id"]
    generated = (
        f"get('current_record.field_{field.id}')"
        if succeeds
        else f"get('data_source.{ds_id}.0.field_{field.id}')"
    )
    monkeypatch.setattr(
        shared_agents,
        "run_agent_sync_with_model",
        lambda *a, **kw: SimpleNamespace(
            output=shared_agents.FormulaGeneratorOutput(
                generated_formulas={"value": generated}
            )
        ),
    )
    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=element_id, label="$formula: this row's Title"
        ),
        thought="Update the button's caption.",
    )
    saved = Element.objects.get(id=element_id).specific
    assert saved.value["formula"] == (generated if succeeds else "'Original'")
    assert result["updated_fields"] == (["label"] if succeeds else [])
    assert bool(result.get("errors")) is not succeeds


@pytest.mark.django_db
@pytest.mark.parametrize("succeeds", [True, False])
def test_record_selector_default_formula_reports_saved_value(
    repeated_rows, data_fixture, monkeypatch, succeeds
):
    ctx, page, field, ds_id = repeated_rows
    element = data_fixture.create_builder_record_selector_element(
        page=page, default_value=formula_object("'Original'")
    )
    generated = "get('user.id')" if succeeds else "get('missing.id')"
    monkeypatch.setattr(
        shared_agents,
        "run_agent_sync_with_model",
        lambda *a, **kw: SimpleNamespace(
            output=shared_agents.FormulaGeneratorOutput(
                generated_formulas={"default_value": generated}
            )
        ),
    )
    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=element.id, default_value="$formula: the selected record ID"
        ),
        thought="Update the record selector's default.",
    )
    element.refresh_from_db()
    assert element.default_value["formula"] == (generated if succeeds else "'Original'")
    assert result["updated_fields"] == (["default_value"] if succeeds else [])
    assert bool(result.get("errors")) is not succeeds


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["text", "button"])
def test_table_field_update_rejects_implicit_generation_before_changes(
    repeated_rows, field_type
):
    ctx, page, field, ds_id = repeated_rows
    created = create_collection_elements(
        ctx,
        page_id=page.id,
        elements=[
            CollectionElementCreate(
                ref="table",
                type="table",
                data_source=ds_id,
                fields=[TableFieldConfig(name="Title", type="text")],
            )
        ],
        thought="Show a table.",
    )
    table = Element.objects.get(id=created["created_elements"][0]["id"]).specific
    original_fields = list(table.fields.values("id", "name", "config"))
    original_page_size = table.items_per_page
    value_field = "label" if field_type == "button" else "value"
    with pytest.raises(ToolInputError, match="explicit formula"):
        update_element(
            ctx,
            page_id=page.id,
            element=ElementUpdate(
                element_id=table.id,
                items_per_page=2,
                fields=[
                    TableFieldConfig(
                        name="Computed",
                        type=field_type,
                        **{value_field: "$formula: combine the values from this row"},
                    )
                ],
            ),
            thought="Change the table.",
        )
    table.refresh_from_db()
    assert table.items_per_page == original_page_size
    assert list(table.fields.values("id", "name", "config")) == original_fields

    formula = f"get('current_record.field_{field.id}')"
    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=table.id,
            fields=[
                TableFieldConfig(
                    name="Computed",
                    type=field_type,
                    **{value_field: f"$formula: {formula}"},
                )
            ],
        ),
        thought="Apply the explicit row expression.",
    )
    assert result["updated_fields"] == ["fields"]
    assert table.fields.get().config[value_field]["formula"] == formula
