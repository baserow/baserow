"""
Unit tests for the builder assistant tools.

Tests cover pages, data sources, elements, and workflow actions using
the RunContext + FunctionToolset pattern.
"""

import pytest

from baserow_enterprise.assistant.tools.builder.tools import (
    create_actions,
    create_collection_elements,
    create_data_sources,
    create_display_elements,
    create_form_elements,
    create_layout_elements,
    create_pages,
    list_actions,
    list_data_sources,
    list_elements,
    list_pages,
    set_theme,
    update_data_source,
    update_element,
    update_element_style,
    update_page,
)
from baserow_enterprise.assistant.tools.builder.types import (
    ActionCreate,
    ButtonStyleOverride,
    CollectionElementCreate,
    DataSourceCreate,
    DataSourceSort,
    DataSourceUpdate,
    DisplayElementCreate,
    ElementStyleUpdate,
    ElementUpdate,
    FormElementCreate,
    InputStyleOverride,
    LayoutElementCreate,
    LinkStyleOverride,
    MenuItemCreate,
    PageCreate,
    PagePathParam,
    PageUpdate,
    TableFieldConfig,
    TypographyStyleOverride,
)
from baserow_enterprise.assistant.tools.shared.formula_utils import (
    formula_desc,
    literal_or_placeholder,
    needs_formula,
)

from .utils import create_fake_tool_helpers, make_test_ctx


@pytest.fixture(autouse=True)
def mock_formula_generators(monkeypatch):
    """Mock all formula generation to avoid LLM requirement in tests."""

    def noop(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_element_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_data_source_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_workflow_action_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_single_element_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_single_data_source_formulas",
        noop,
    )


# ===========================================================================
# Formula utils tests
# ===========================================================================


class TestFormulaUtils:
    def test_needs_formula_with_prefix(self):
        assert needs_formula("$formula: the product name")
        assert needs_formula("  $formula: upper case test  ")

    def test_needs_formula_with_raw_get(self):
        assert needs_formula("get('page_parameter.id')")
        assert needs_formula("concat('hello', ' ', get('user.name'))")

    def test_needs_formula_with_raw_expressions(self):
        assert needs_formula("if(get('user.is_authenticated'), 'yes', 'no')")
        assert needs_formula("today()")
        assert needs_formula("now()")

    def test_needs_formula_with_literal(self):
        assert not needs_formula("Submit")
        assert not needs_formula("'Hello world'")
        assert not needs_formula(None)
        assert not needs_formula("")

    def test_formula_desc_strips_prefix(self):
        assert formula_desc("$formula: the product name") == "the product name"
        assert formula_desc("  $formula:  spaced  ") == "spaced"

    def test_formula_desc_passes_raw(self):
        assert formula_desc("get('page_parameter.id')") == "get('page_parameter.id')"

    def test_literal_or_placeholder_formula(self):
        assert literal_or_placeholder("$formula: something") == "''"
        assert literal_or_placeholder("get('field')") == "''"

    def test_literal_or_placeholder_literal(self):
        assert literal_or_placeholder("Submit") == "'Submit'"
        assert literal_or_placeholder(None) == "''"


# ===========================================================================
# Page tools tests
# ===========================================================================


@pytest.mark.django_db
def test_list_pages(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = list_pages(ctx, application_id=builder.id, thought="test")

    assert len(result["pages"]) == 1
    assert result["pages"][0]["name"] == "Home"
    assert result["pages"][0]["id"] == page.id


@pytest.mark.django_db(transaction=True)
def test_create_pages(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)

    ctx = make_test_ctx(user, workspace)
    result = create_pages(
        ctx,
        application_id=builder.id,
        pages=[
            PageCreate(name="Home", path="/"),
            PageCreate(
                name="Product Detail",
                path="/products/:id",
                path_params=[PagePathParam(name="id", type="numeric")],
            ),
        ],
        thought="test",
    )

    assert len(result["created_pages"]) == 2
    assert result["created_pages"][0]["name"] == "Home"
    assert result["created_pages"][1]["name"] == "Product Detail"
    assert result["created_pages"][1]["path"] == "/products/:id"


@pytest.mark.django_db(transaction=True)
def test_create_pages_skips_duplicates(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = create_pages(
        ctx,
        application_id=builder.id,
        pages=[
            PageCreate(name="Home", path="/"),
            PageCreate(name="About", path="/about"),
        ],
        thought="test",
    )

    assert len(result["created_pages"]) == 1
    assert result["created_pages"][0]["name"] == "About"
    assert len(result["existing_pages"]) == 1


# ===========================================================================
# Data source tools tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_create_list_rows_data_source(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    field = data_fixture.create_text_field(table=table, name="Name")

    ctx = make_test_ctx(user, workspace)
    result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="products_ds",
                name="Products",
                type="list_rows",
                table_id=table.id,
                sortings=[DataSourceSort(field_id=field.id)],
            ),
        ],
        thought="test",
    )

    assert len(result["created_data_sources"]) == 1
    assert result["created_data_sources"][0]["name"] == "Products"
    assert result["created_data_sources"][0]["type"] == "list_rows"
    assert "products_ds" in result["ref_to_id_map"]


@pytest.mark.django_db(transaction=True)
def test_create_get_row_data_source(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder, name="Detail", path="/detail/:id"
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    ctx = make_test_ctx(user, workspace)
    result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="product_ds",
                name="Product",
                type="get_row",
                table_id=table.id,
                row_id="1",
            ),
        ],
        thought="test",
    )

    assert len(result["created_data_sources"]) == 1
    assert result["created_data_sources"][0]["type"] == "get_row"


@pytest.mark.django_db
def test_list_data_sources(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = list_data_sources(ctx, page_id=page.id, thought="test")

    assert result["data_sources"] == []


def test_data_source_validation_errors():
    """get_row type requires row_id."""
    with pytest.raises(Exception):
        DataSourceCreate(
            ref="ds",
            name="Test",
            type="get_row",
            table_id=1,
            # Missing row_id
        )


# ===========================================================================
# Element tools tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_create_heading_element(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Welcome", level=1),
        ],
        thought="test",
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "heading"
    assert result["created_elements"][0]["ref"] == "h1"


@pytest.mark.django_db(transaction=True)
def test_create_column_with_children(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    # Create column layout first
    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)
    layout_result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(ref="cols", type="column", column_amount=2),
        ],
        thought="test",
    )

    assert len(layout_result["created_elements"]) == 1
    assert layout_result["created_elements"][0]["type"] == "column"

    # Then add children using display elements
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="left_heading",
                type="heading",
                value="Left",
                parent_element="cols",
                place_in_container="0",
            ),
            DisplayElementCreate(
                ref="right_heading",
                type="heading",
                value="Right",
                parent_element="cols",
                place_in_container="1",
            ),
        ],
        thought="test",
    )

    assert len(result["created_elements"]) == 2
    assert result["created_elements"][0]["type"] == "heading"
    assert result["created_elements"][1]["type"] == "heading"


@pytest.mark.django_db(transaction=True)
def test_create_form_container_with_inputs(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Form", path="/form")

    ctx = make_test_ctx(user, workspace)
    result = create_form_elements(
        ctx,
        page_id=page.id,
        elements=[
            FormElementCreate(
                ref="form",
                type="form_container",
                submit_button_label="Submit",
            ),
            FormElementCreate(
                ref="name_input",
                type="input_text",
                label="Name",
                placeholder="Enter your name",
                required=True,
                parent_element="form",
            ),
            FormElementCreate(
                ref="email_input",
                type="input_text",
                label="Email",
                validation_type="email",
                required=True,
                parent_element="form",
            ),
        ],
        thought="test",
    )

    assert len(result["created_elements"]) == 3
    assert result["created_elements"][0]["type"] == "form_container"
    assert result["created_elements"][1]["type"] == "input_text"
    assert result["created_elements"][2]["type"] == "input_text"


@pytest.mark.django_db
def test_list_elements(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = list_elements(ctx, page_id=page.id, thought="test")

    assert result["elements"] == []


@pytest.mark.django_db(transaction=True)
def test_create_text_and_button(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="txt", type="text", value="Hello world"),
            DisplayElementCreate(ref="btn", type="button", value="Click me"),
        ],
        thought="test",
    )

    assert len(result["created_elements"]) == 2
    assert result["created_elements"][0]["type"] == "text"
    assert result["created_elements"][1]["type"] == "button"


@pytest.mark.django_db(transaction=True)
def test_create_image_element(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="img",
                type="image",
                image_url="https://example.com/img.png",
                alt_text="Example",
            ),
        ],
        thought="test",
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "image"


# ===========================================================================
# Workflow action tools tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_create_notification_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    # Create a button to attach the action to
    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)
    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="btn", type="button", value="Notify"),
        ],
        thought="test",
    )
    assert len(el_result["created_elements"]) == 1

    result = create_actions(
        ctx,
        page_id=page.id,
        actions=[
            ActionCreate(
                type="notification",
                element="btn",
                title="'Success!'",
                description="'Item was created.'",
            ),
        ],
        thought="test",
    )

    assert len(result["created_actions"]) == 1
    assert result["created_actions"][0]["type"] == "notification"


@pytest.mark.django_db(transaction=True)
def test_create_open_page_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    target_page = data_fixture.create_builder_page(
        builder=builder, name="Detail", path="/detail"
    )

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)
    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="link", type="button", value="Go"),
        ],
        thought="test",
    )

    result = create_actions(
        ctx,
        page_id=page.id,
        actions=[
            ActionCreate(
                type="open_page",
                element="link",
                navigate_to_page_id=target_page.id,
            ),
        ],
        thought="test",
    )

    assert len(result["created_actions"]) == 1
    assert result["created_actions"][0]["type"] == "open_page"


def test_open_page_action_extracts_page_param_formulas():
    """open_page actions with $formula: page parameters should produce formulas."""

    from baserow_enterprise.assistant.tools.builder.types.workflow_action import (
        ParameterMapping,
    )

    action = ActionCreate(
        type="open_page",
        element="btn",
        navigate_to_page_id=99,
        page_parameters=[
            ParameterMapping(name="id", value="$formula: the row id"),
        ],
    )
    formulas = action.get_formulas_to_create(None, None)
    assert "page_param_0" in formulas
    assert "row id" in formulas["page_param_0"]


def test_open_page_action_no_formulas_for_static():
    """open_page actions without $formula: should produce no formulas."""

    from baserow_enterprise.assistant.tools.builder.types.workflow_action import (
        ParameterMapping,
    )

    action = ActionCreate(
        type="open_page",
        element="btn",
        navigate_to_page_id=99,
        page_parameters=[
            ParameterMapping(name="id", value="42"),
        ],
    )
    formulas = action.get_formulas_to_create(None, None)
    assert formulas == {}


@pytest.mark.django_db(transaction=True)
def test_create_row_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Form", path="/form")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    field = data_fixture.create_text_field(table=table, name="Name")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create form with submit button
    el_result = create_form_elements(
        ctx,
        page_id=page.id,
        elements=[
            FormElementCreate(ref="form", type="form_container"),
        ],
        thought="test",
    )

    from baserow_enterprise.assistant.tools.builder.types import FieldValueMapping

    result = create_actions(
        ctx,
        page_id=page.id,
        actions=[
            ActionCreate(
                type="create_row",
                element="form",
                event="submit",
                table_id=table.id,
                field_values=[
                    FieldValueMapping(field_id=str(field.id), value="'test value'"),
                ],
            ),
        ],
        thought="test",
    )

    assert len(result["created_actions"]) == 1
    assert result["created_actions"][0]["type"] == "create_row"
    assert result["created_actions"][0]["event"] == "submit"


@pytest.mark.django_db
def test_list_actions(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = list_actions(ctx, page_id=page.id, thought="test")

    assert result["workflow_actions"] == []


# ===========================================================================
# add_action_field_mapping tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_add_action_field_mapping_creates_mapping(data_fixture):
    """add_action_field_mapping should create a field mapping on an existing action."""

    from baserow_enterprise.assistant.tools.builder.tools import (
        add_action_field_mapping,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Form", path="/form")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    email_field = data_fixture.create_text_field(table=table, name="Email")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create a form and create_row action with one field mapping
    from baserow_enterprise.assistant.tools.builder.types import FieldValueMapping

    create_form_elements(
        ctx,
        page_id=page.id,
        elements=[FormElementCreate(ref="form", type="form_container")],
        thought="test",
    )
    action_result = create_actions(
        ctx,
        page_id=page.id,
        actions=[
            ActionCreate(
                type="create_row",
                element="form",
                event="submit",
                table_id=table.id,
                field_values=[
                    FieldValueMapping(field_id=str(name_field.id), value="'Alice'"),
                ],
            ),
        ],
        thought="test",
    )
    action_id = action_result["created_actions"][0]["id"]

    # Now add a second field mapping via add_action_field_mapping
    result = add_action_field_mapping(
        ctx,
        action_id=action_id,
        field_id=email_field.id,
        value_formula="get('form_data.123')",
        thought="test",
    )

    assert result["status"] == "created"
    assert len(result["field_mappings"]) == 2
    mapped_field_ids = {m["field_id"] for m in result["field_mappings"]}
    assert name_field.id in mapped_field_ids
    assert email_field.id in mapped_field_ids


@pytest.mark.django_db(transaction=True)
def test_add_action_field_mapping_updates_existing(data_fixture):
    """add_action_field_mapping should update an existing field mapping."""

    from baserow_enterprise.assistant.tools.builder.tools import (
        add_action_field_mapping,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Form", path="/form")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    from baserow_enterprise.assistant.tools.builder.types import FieldValueMapping

    create_form_elements(
        ctx,
        page_id=page.id,
        elements=[FormElementCreate(ref="form", type="form_container")],
        thought="test",
    )
    action_result = create_actions(
        ctx,
        page_id=page.id,
        actions=[
            ActionCreate(
                type="create_row",
                element="form",
                event="submit",
                table_id=table.id,
                field_values=[
                    FieldValueMapping(field_id=str(name_field.id), value="'Alice'"),
                ],
            ),
        ],
        thought="test",
    )
    action_id = action_result["created_actions"][0]["id"]

    # Update the existing mapping with a new formula
    result = add_action_field_mapping(
        ctx,
        action_id=action_id,
        field_id=name_field.id,
        value_formula="get('form_data.456')",
        thought="test",
    )

    assert result["status"] == "updated"
    assert len(result["field_mappings"]) == 1
    assert result["field_mappings"][0]["field_id"] == name_field.id


# ===========================================================================
# Element ref tracking tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_element_ref_tracking_across_calls(data_fixture):
    """Verify that element refs created in one call are available in the next."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # First call: create a button
    create_display_elements(
        ctx,
        page_id=page.id,
        elements=[DisplayElementCreate(ref="btn", type="button", value="Click")],
        thought="test",
    )

    # Second call: create an action referencing the button from the first call
    result = create_actions(
        ctx,
        page_id=page.id,
        actions=[
            ActionCreate(type="notification", element="btn", title="'Hello'"),
        ],
        thought="test",
    )

    assert len(result["created_actions"]) == 1


# ===========================================================================
# Theme tests
# ===========================================================================


@pytest.mark.django_db
def test_set_theme(data_fixture, monkeypatch):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    ctx = make_test_ctx(user, workspace)

    applied = {}

    def fake_apply_theme(builder_instance, theme_name, user=None):
        applied["builder"] = builder_instance
        applied["theme"] = theme_name
        applied["user"] = user
        return True

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.tools.apply_theme",
        fake_apply_theme,
    )

    result = set_theme(
        ctx,
        application_id=builder.id,
        theme_name="eclipse",
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["application_id"] == builder.id
    assert result["theme"] == "eclipse"
    assert applied["theme"] == "eclipse"
    assert applied["builder"].id == builder.id


@pytest.mark.django_db
def test_apply_theme_function(data_fixture):
    """apply_theme should update theme properties on an existing builder."""

    from baserow_enterprise.assistant.tools.builder.themes import apply_theme

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)

    # Before: default color
    original_color = builder.colorthemeconfigblock.primary_color

    applied = apply_theme(builder, "lavender", user)
    assert applied is not None

    builder.colorthemeconfigblock.refresh_from_db()
    assert builder.colorthemeconfigblock.primary_color != original_color


# ===========================================================================
# Element update tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_update_heading_value(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create a heading first
    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Old Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    # Update the heading value
    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(element_id=element_id, value="New Title"),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["element_id"] == element_id
    assert result["element_type"] == "heading"
    assert "value" in result["updated_fields"]

    # Verify the update persisted
    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    assert el.specific.value["formula"] == "'New Title'"


@pytest.mark.django_db(transaction=True)
def test_update_input_text_label(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Form", path="/form")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_form_elements(
        ctx,
        page_id=page.id,
        elements=[
            FormElementCreate(
                ref="name_input",
                type="input_text",
                label="Old Label",
                required=False,
            ),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(element_id=element_id, label="New Label", required=True),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["element_type"] == "input_text"
    assert "label" in result["updated_fields"]
    assert "required" in result["updated_fields"]

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id).specific
    assert el.label["formula"] == "'New Label'"
    assert el.required is True


@pytest.mark.django_db(transaction=True)
def test_update_column_amount(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(ref="cols", type="column", column_amount=2),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(element_id=element_id, column_amount=3),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["element_type"] == "column"
    assert "column_amount" in result["updated_fields"]

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id).specific
    assert el.column_amount == 3


@pytest.mark.django_db(transaction=True)
def test_update_ignores_irrelevant_fields(data_fixture):
    """Update a heading with column_amount — should be dropped by extract_allowed."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    # column_amount is irrelevant for heading — should not cause an error
    result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=element_id, value="Updated Title", column_amount=3
        ),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["element_type"] == "heading"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id).specific
    assert el.value["formula"] == "'Updated Title'"


@pytest.mark.django_db(transaction=True)
def test_update_with_formula_prefix(data_fixture):
    """Verify $formula: triggers placeholder + formula generation."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Static"),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    # The formula prefix should cause a placeholder to be set initially
    el_update = ElementUpdate(element_id=element_id, value="$formula: the product name")

    # Check that to_update_kwargs uses placeholder for formula values
    kwargs = el_update.to_update_kwargs("heading")
    assert kwargs["value"]["formula"] == "''"

    # Check that get_formulas_to_update returns the formula description
    formulas = el_update.get_formulas_to_update(None, None, "heading")
    assert "value" in formulas
    assert "product name" in formulas["value"]


def test_update_datetime_picker_formula_detected():
    """datetime_picker with $formula: default_value should trigger formula generation."""

    el_update = ElementUpdate(
        element_id=1, default_value="$formula: get('current_record.field_1439')"
    )

    # to_update_kwargs should set a placeholder for datetime_picker
    kwargs = el_update.to_update_kwargs("datetime_picker")
    assert "default_value" in kwargs
    assert kwargs["default_value"]["formula"] == "''"

    # get_formulas_to_update should detect the formula for datetime_picker
    formulas = el_update.get_formulas_to_update(None, None, "datetime_picker")
    assert "default_value" in formulas


# ===========================================================================
# Page update tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_update_page_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = update_page(
        ctx,
        page=PageUpdate(page_id=page.id, name="Dashboard"),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["page"]["name"] == "Dashboard"
    assert result["page"]["path"] == "/home"
    assert "name" in result["updated_fields"]
    assert "path" not in result["updated_fields"]


@pytest.mark.django_db(transaction=True)
def test_update_page_path_and_params(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder, name="Detail", path="/detail"
    )

    ctx = make_test_ctx(user, workspace)
    result = update_page(
        ctx,
        page=PageUpdate(
            page_id=page.id,
            path="/detail/:id",
            path_params=[PagePathParam(name="id", type="numeric")],
        ),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["page"]["path"] == "/detail/:id"
    assert len(result["page"]["path_params"]) == 1
    assert result["page"]["path_params"][0]["name"] == "id"
    assert "path" in result["updated_fields"]
    assert "path_params" in result["updated_fields"]


@pytest.mark.django_db(transaction=True)
def test_update_page_visibility(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace)
    result = update_page(
        ctx,
        page=PageUpdate(page_id=page.id, visibility="logged-in"),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["page"]["visibility"] == "logged-in"
    assert "visibility" in result["updated_fields"]


# ===========================================================================
# Data source update tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_update_data_source_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create a data source first
    ds_result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="ds1", name="Old Name", type="list_rows", table_id=table.id
            ),
        ],
        thought="test",
    )
    ds_id = ds_result["created_data_sources"][0]["id"]

    result = update_data_source(
        ctx,
        page_id=page.id,
        data_source=DataSourceUpdate(data_source_id=ds_id, name="New Name"),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["data_source_id"] == ds_id
    assert "name" in result["updated_fields"]

    from baserow.contrib.builder.data_sources.handler import DataSourceHandler

    ds = DataSourceHandler().get_data_source(ds_id)
    assert ds.name == "New Name"


@pytest.mark.django_db(transaction=True)
def test_update_data_source_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table1 = data_fixture.create_database_table(user=user, database=database)
    table2 = data_fixture.create_database_table(user=user, database=database)

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    ds_result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="ds1", name="Products", type="list_rows", table_id=table1.id
            ),
        ],
        thought="test",
    )
    ds_id = ds_result["created_data_sources"][0]["id"]

    result = update_data_source(
        ctx,
        page_id=page.id,
        data_source=DataSourceUpdate(data_source_id=ds_id, table_id=table2.id),
        thought="test",
    )

    assert result["status"] == "ok"
    assert "table_id" in result["updated_fields"]

    from baserow.contrib.builder.data_sources.handler import DataSourceHandler

    ds = DataSourceHandler().get_data_source(ds_id)
    assert ds.service.specific.table_id == table2.id


def test_update_data_source_formula_detected():
    """$formula: row_id should trigger formula generation."""

    ds_update = DataSourceUpdate(
        data_source_id=1, row_id="$formula: the id from the page parameter"
    )

    formulas = ds_update.get_formulas_to_update(None, None)
    assert "row_id" in formulas
    assert "page parameter" in formulas["row_id"]


def test_update_data_source_search_query_formula():
    """$formula: search_query should trigger formula generation."""

    ds_update = DataSourceUpdate(
        data_source_id=1, search_query="$formula: the search input text"
    )

    formulas = ds_update.get_formulas_to_update(None, None)
    assert "search_query" in formulas


# ---------------------------------------------------------------------------
# Shared element tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_create_menu_with_items(data_fixture):
    """Creating a menu element with menu_items should produce MenuItemElement rows."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/")
    page2 = data_fixture.create_builder_page(
        builder=builder, name="About", path="/about"
    )

    ctx = make_test_ctx(user, workspace)
    result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(
                ref="hdr",
                type="header",
            ),
            LayoutElementCreate(
                ref="nav",
                type="menu",
                parent_element="hdr",
                menu_items=[
                    MenuItemCreate(name="Home", page_id=page.id),
                    MenuItemCreate(name="About", page_id=page2.id),
                ],
            ),
        ],
        thought="test",
    )

    assert len(result["created_elements"]) == 2

    # Menu should be on the shared page (child of header)
    from baserow.contrib.builder.elements.handler import ElementHandler

    menu_id = result["ref_to_id_map"]["nav"]
    menu_el = ElementHandler().get_element(menu_id).specific
    assert menu_el.page.shared, "Menu should be on the shared page"

    items = list(menu_el.menu_items.all().order_by("menu_item_order"))
    assert len(items) == 2
    assert items[0].name == "Home"
    assert items[0].navigate_to_page_id == page.id
    assert items[1].name == "About"
    assert items[1].navigate_to_page_id == page2.id


@pytest.mark.django_db(transaction=True)
def test_update_menu_items(data_fixture):
    """update_element with menu_items should replace the menu's items."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/")
    page2 = data_fixture.create_builder_page(
        builder=builder, name="About", path="/about"
    )
    page3 = data_fixture.create_builder_page(
        builder=builder, name="Contact", path="/contact"
    )

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create header + menu with 1 item
    result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(ref="hdr", type="header"),
            LayoutElementCreate(
                ref="nav",
                type="menu",
                parent_element="hdr",
                menu_items=[MenuItemCreate(name="Home", page_id=page.id)],
            ),
        ],
        thought="test",
    )
    menu_id = result["ref_to_id_map"]["nav"]

    # Update to 3 items
    update_result = update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=menu_id,
            menu_items=[
                MenuItemCreate(name="Home", page_id=page.id),
                MenuItemCreate(name="About", page_id=page2.id),
                MenuItemCreate(name="Contact", page_id=page3.id),
            ],
        ),
        thought="test",
    )

    assert update_result["status"] == "ok"
    assert "menu_items" in update_result["updated_fields"]

    from baserow.contrib.builder.elements.handler import ElementHandler

    menu_el = ElementHandler().get_element(menu_id).specific
    items = list(menu_el.menu_items.all().order_by("menu_item_order"))
    assert len(items) == 3
    assert items[0].name == "Home"
    assert items[1].name == "About"
    assert items[1].navigate_to_page_id == page2.id
    assert items[2].name == "Contact"
    assert items[2].navigate_to_page_id == page3.id


# ===========================================================================
# Element style tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_update_element_style_box_model(data_fixture):
    """Set border, padding, margin, background, width — all sides uniform."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            border_color="#ff0000",
            border_size=2,
            padding=30,
            margin=10,
            border_radius=8,
            background="color",
            background_color="#00ff00",
            width="full",
        ),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["element_type"] == "heading"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    for side in ("top", "bottom", "left", "right"):
        assert getattr(el, f"style_border_{side}_color") == "#ff0000"
        assert getattr(el, f"style_border_{side}_size") == 2
        assert getattr(el, f"style_padding_{side}") == 30
        assert getattr(el, f"style_margin_{side}") == 10
    assert el.style_border_radius == 8
    assert el.style_background == "color"
    assert el.style_background_color == "#00ff00"
    assert el.style_width == "full"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_reset(data_fixture):
    """Apply custom styles, then reset to defaults."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    # Apply custom styles
    update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            padding=50,
            border_size=5,
            background="color",
            background_color="#123456",
        ),
        thought="test",
    )

    # Reset
    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(element_id=element_id, reset=True),
        thought="test",
    )

    assert result["status"] == "ok"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    assert el.style_padding_top == 10
    assert el.style_padding_left == 20
    assert el.style_border_top_size == 0
    assert el.style_background == "none"
    assert el.style_background_color == "#ffffffff"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_reset_with_overrides(data_fixture):
    """reset=True + padding=50 → padding=50 all sides, rest at defaults."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(element_id=element_id, reset=True, padding=50),
        thought="test",
    )

    assert result["status"] == "ok"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    for side in ("top", "bottom", "left", "right"):
        assert getattr(el, f"style_padding_{side}") == 50
    # Other fields at defaults
    assert el.style_border_top_size == 0
    assert el.style_background == "none"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_partial(data_fixture):
    """Only set background_color — other fields untouched."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    from baserow.contrib.builder.elements.handler import ElementHandler

    el_before = ElementHandler().get_element(element_id)
    padding_before = el_before.style_padding_top

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            background_color="#abcdef",
        ),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["updated_fields"] == ["style_background_color"]

    el = ElementHandler().get_element(element_id)
    assert el.style_background_color == "#abcdef"
    assert el.style_padding_top == padding_before  # unchanged


@pytest.mark.django_db(transaction=True)
def test_update_element_style_button_overrides(data_fixture):
    """Button element with button style overrides → styles JSON."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="btn", type="button", value="Click me"),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            button=ButtonStyleOverride(
                background_color="#ff0000",
                text_color="#ffffff",
            ),
        ),
        thought="test",
    )

    assert result["status"] == "ok"
    assert result["element_type"] == "button"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    styles = el.styles
    assert styles["button"]["button_background_color"] == "#ff0000"
    assert styles["button"]["button_text_color"] == "#ffffff"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_typography_overrides(data_fixture):
    """Heading element with typography overrides → styles JSON."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            typography=TypographyStyleOverride(
                heading_1_text_color="#333333",
                heading_1_font_size=32,
                heading_1_text_alignment="center",
            ),
        ),
        thought="test",
    )

    assert result["status"] == "ok"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    styles = el.styles
    assert styles["typography"]["heading_1_text_color"] == "#333333"
    assert styles["typography"]["heading_1_font_size"] == 32
    assert styles["typography"]["heading_1_text_alignment"] == "center"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_input_overrides(data_fixture):
    """Input text element with input overrides → styles JSON."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Form", path="/form")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_form_elements(
        ctx,
        page_id=page.id,
        elements=[
            FormElementCreate(ref="inp", type="input_text", label="Name"),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            input=InputStyleOverride(
                input_background_color="#f0f0f0",
                input_border_color="#cccccc",
                label_text_color="#666666",
            ),
        ),
        thought="test",
    )

    assert result["status"] == "ok"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    styles = el.styles
    assert styles["input"]["input_background_color"] == "#f0f0f0"
    assert styles["input"]["input_border_color"] == "#cccccc"
    assert styles["input"]["label_text_color"] == "#666666"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_ignores_wrong_block(data_fixture):
    """On a heading, button overrides should be ignored (wrong type)."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Title", level=1),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            button=ButtonStyleOverride(background_color="#ff0000"),
        ),
        thought="test",
    )

    # Button overrides on a heading should be silently ignored, returning a warning
    assert result["status"] == "warning"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    # styles should not contain button block
    assert "button" not in (el.styles or {})


@pytest.mark.django_db(transaction=True)
def test_update_element_style_combined(data_fixture):
    """Box model + theme overrides in one call."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="btn", type="button", value="Go"),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            padding=20,
            border_color="#000000",
            border_size=1,
            button=ButtonStyleOverride(
                background_color="#0000ff",
                text_color="#ffffff",
            ),
        ),
        thought="test",
    )

    assert result["status"] == "ok"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    # Box model
    assert el.style_padding_top == 20
    assert el.style_border_top_color == "#000000"
    assert el.style_border_top_size == 1
    # Theme overrides
    assert el.styles["button"]["button_background_color"] == "#0000ff"
    assert el.styles["button"]["button_text_color"] == "#ffffff"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_merges_existing_overrides(data_fixture):
    """Second style call should merge with existing overrides, not wipe them."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    el_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="btn", type="button", value="Go"),
        ],
        thought="test",
    )
    element_id = el_result["created_elements"][0]["id"]

    # First call: set font_size and background_color
    update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            button=ButtonStyleOverride(
                font_size=18,
                background_color="#0000ff",
            ),
        ),
        thought="test",
    )

    # Second call: only change text_color
    update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=element_id,
            button=ButtonStyleOverride(text_color="#ffffff"),
        ),
        thought="test",
    )

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(element_id)
    btn = el.styles["button"]
    # First call's values should still be present
    assert btn["button_font_size"] == 18
    assert btn["button_background_color"] == "#0000ff"
    # Second call's value should be added
    assert btn["button_text_color"] == "#ffffff"


@pytest.mark.django_db(transaction=True)
def test_update_element_style_menu_link_color(data_fixture):
    """Menu element link overrides should store under 'menu' key, not 'link'."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create header + menu
    result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(ref="hdr", type="header"),
            LayoutElementCreate(
                ref="nav",
                type="menu",
                parent_element="hdr",
                menu_items=[MenuItemCreate(name="Home", page_id=page.id)],
            ),
        ],
        thought="test",
    )
    menu_id = result["ref_to_id_map"]["nav"]

    # Set link color to red on menu
    style_result = update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=menu_id,
            link=LinkStyleOverride(text_color="#ff0000"),
        ),
        thought="test",
    )

    assert style_result["status"] == "ok"
    assert style_result["element_type"] == "menu"

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(menu_id)
    # Link props go under "menu" key for menu elements
    assert "menu" in el.styles
    assert el.styles["menu"]["link_text_color"] == "#ff0000"
    # Should NOT have a separate "link" key
    assert "link" not in el.styles


@pytest.mark.django_db(transaction=True)
def test_update_element_style_menu_button_and_link(data_fixture):
    """Menu element: both button and link overrides merge under 'menu' key."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(ref="hdr", type="header"),
            LayoutElementCreate(
                ref="nav",
                type="menu",
                parent_element="hdr",
                menu_items=[MenuItemCreate(name="Home", page_id=page.id)],
            ),
        ],
        thought="test",
    )
    menu_id = result["ref_to_id_map"]["nav"]

    update_element_style(
        ctx,
        page_id=page.id,
        style=ElementStyleUpdate(
            element_id=menu_id,
            button=ButtonStyleOverride(background_color="#0000ff"),
            link=LinkStyleOverride(text_color="#ff0000"),
        ),
        thought="test",
    )

    from baserow.contrib.builder.elements.handler import ElementHandler

    el = ElementHandler().get_element(menu_id)
    menu_styles = el.styles["menu"]
    assert menu_styles["button_background_color"] == "#0000ff"
    assert menu_styles["link_text_color"] == "#ff0000"


# ===========================================================================
# Table element property options tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_table_element_auto_enables_filter_sort_search(data_fixture):
    """Table text columns referencing real fields get filter/sort/search enabled."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    email_field = data_fixture.create_text_field(table=table, name="Email")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create a data source first
    ds_result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="ds1",
                name="People",
                type="list_rows",
                table_id=table.id,
            ),
        ],
        thought="test",
    )
    ds_id = ds_result["ref_to_id_map"]["ds1"]

    # Create a table with 2 text columns + 1 button column
    result = create_collection_elements(
        ctx,
        page_id=page.id,
        elements=[
            CollectionElementCreate(
                ref="tbl",
                type="table",
                data_source=ds_id,
                fields=[
                    TableFieldConfig(name="Name", type="text"),
                    TableFieldConfig(name="Email", type="text"),
                    TableFieldConfig(name="Actions", type="button", label="Edit"),
                ],
            ),
        ],
        thought="test",
    )

    table_element_id = result["ref_to_id_map"]["tbl"]

    from baserow.contrib.builder.elements.models import CollectionElementPropertyOptions

    options = list(
        CollectionElementPropertyOptions.objects.filter(
            element_id=table_element_id
        ).order_by("schema_property")
    )

    # Should have options for both text columns, not for the button column
    assert len(options) == 2

    schema_props = {o.schema_property for o in options}
    assert f"field_{name_field.id}" in schema_props
    assert f"field_{email_field.id}" in schema_props

    for opt in options:
        assert opt.filterable is True
        assert opt.sortable is True
        assert opt.searchable is True


@pytest.mark.django_db(transaction=True)
def test_update_table_element_replace_columns(data_fixture):
    """Updating a table element's fields replaces all columns."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    email_field = data_fixture.create_text_field(table=table, name="Email")
    phone_field = data_fixture.create_text_field(table=table, name="Phone")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create data source
    ds_result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="ds1", name="People", type="list_rows", table_id=table.id
            ),
        ],
        thought="test",
    )
    ds_id = ds_result["ref_to_id_map"]["ds1"]

    # Create table with 2 columns
    el_result = create_collection_elements(
        ctx,
        page_id=page.id,
        elements=[
            CollectionElementCreate(
                ref="tbl",
                type="table",
                data_source=ds_id,
                fields=[
                    TableFieldConfig(name="Name", type="text"),
                    TableFieldConfig(name="Email", type="text"),
                ],
            ),
        ],
        thought="test",
    )
    table_element_id = el_result["ref_to_id_map"]["tbl"]

    from baserow.contrib.builder.elements.handler import ElementHandler

    element = ElementHandler().get_element(table_element_id).specific

    # Verify initial state: 2 columns
    fields_before = list(element.fields.order_by("order"))
    assert len(fields_before) == 2
    assert fields_before[0].name == "Name"
    assert fields_before[1].name == "Email"

    # Update: replace with 3 columns (add Phone, remove Email)
    update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=table_element_id,
            fields=[
                TableFieldConfig(name="Name", type="text"),
                TableFieldConfig(name="Phone", type="text"),
                TableFieldConfig(name="Actions", type="button", label="Edit"),
            ],
        ),
        thought="test",
    )

    element = ElementHandler().get_element(table_element_id).specific
    fields_after = list(element.fields.order_by("order"))
    assert len(fields_after) == 3
    assert fields_after[0].name == "Name"
    assert fields_after[1].name == "Phone"
    assert fields_after[2].name == "Actions"
    assert fields_after[2].type == "button"


@pytest.mark.django_db(transaction=True)
def test_update_table_element_add_fields(data_fixture):
    """add_fields appends columns without touching existing ones."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name")
    data_fixture.create_text_field(table=table, name="Email")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    ds_result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="ds1", name="People", type="list_rows", table_id=table.id
            ),
        ],
        thought="test",
    )
    ds_id = ds_result["ref_to_id_map"]["ds1"]

    # Create table with 1 column
    el_result = create_collection_elements(
        ctx,
        page_id=page.id,
        elements=[
            CollectionElementCreate(
                ref="tbl",
                type="table",
                data_source=ds_id,
                fields=[TableFieldConfig(name="Name", type="text")],
            ),
        ],
        thought="test",
    )
    table_element_id = el_result["ref_to_id_map"]["tbl"]

    from baserow.contrib.builder.elements.handler import ElementHandler

    element = ElementHandler().get_element(table_element_id).specific
    assert element.fields.count() == 1

    # Add Email column — Name should be preserved
    update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=table_element_id,
            add_fields=[TableFieldConfig(name="Email", type="text")],
        ),
        thought="test",
    )

    element = ElementHandler().get_element(table_element_id).specific
    fields = list(element.fields.order_by("order"))
    assert len(fields) == 2
    assert fields[0].name == "Name"
    assert fields[1].name == "Email"


@pytest.mark.django_db(transaction=True)
def test_update_table_element_remove_fields(data_fixture):
    """remove_fields removes columns by name, preserving the rest."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name")
    data_fixture.create_text_field(table=table, name="Email")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    ds_result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="ds1", name="People", type="list_rows", table_id=table.id
            ),
        ],
        thought="test",
    )
    ds_id = ds_result["ref_to_id_map"]["ds1"]

    # Create table with 2 columns
    el_result = create_collection_elements(
        ctx,
        page_id=page.id,
        elements=[
            CollectionElementCreate(
                ref="tbl",
                type="table",
                data_source=ds_id,
                fields=[
                    TableFieldConfig(name="Name", type="text"),
                    TableFieldConfig(name="Email", type="text"),
                ],
            ),
        ],
        thought="test",
    )
    table_element_id = el_result["ref_to_id_map"]["tbl"]

    from baserow.contrib.builder.elements.handler import ElementHandler

    element = ElementHandler().get_element(table_element_id).specific
    assert element.fields.count() == 2

    # Remove Email by name — Name should be preserved
    update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=table_element_id,
            remove_fields=["Email"],
        ),
        thought="test",
    )

    element = ElementHandler().get_element(table_element_id).specific
    fields = list(element.fields.order_by("order"))
    assert len(fields) == 1
    assert fields[0].name == "Name"


@pytest.mark.django_db(transaction=True)
def test_update_table_element_add_and_remove_fields(data_fixture):
    """add_fields and remove_fields can be combined in a single update."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name")
    data_fixture.create_text_field(table=table, name="Email")
    data_fixture.create_text_field(table=table, name="Phone")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    ds_result = create_data_sources(
        ctx,
        page_id=page.id,
        data_sources=[
            DataSourceCreate(
                ref="ds1", name="People", type="list_rows", table_id=table.id
            ),
        ],
        thought="test",
    )
    ds_id = ds_result["ref_to_id_map"]["ds1"]

    el_result = create_collection_elements(
        ctx,
        page_id=page.id,
        elements=[
            CollectionElementCreate(
                ref="tbl",
                type="table",
                data_source=ds_id,
                fields=[
                    TableFieldConfig(name="Name", type="text"),
                    TableFieldConfig(name="Email", type="text"),
                ],
            ),
        ],
        thought="test",
    )
    table_element_id = el_result["ref_to_id_map"]["tbl"]

    # Remove Email, add Phone + button — in one call
    update_element(
        ctx,
        page_id=page.id,
        element=ElementUpdate(
            element_id=table_element_id,
            remove_fields=["Email"],
            add_fields=[
                TableFieldConfig(name="Phone", type="text"),
                TableFieldConfig(name="Actions", type="button", label="Edit"),
            ],
        ),
        thought="test",
    )

    from baserow.contrib.builder.elements.handler import ElementHandler

    element = ElementHandler().get_element(table_element_id).specific
    fields = list(element.fields.order_by("order"))
    assert len(fields) == 3
    assert fields[0].name == "Name"
    assert fields[1].name == "Phone"
    assert fields[2].name == "Actions"
    assert fields[2].type == "button"


# ===========================================================================
# User source tools tests
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_setup_user_source_new_table(data_fixture):
    """Create a user source with a brand-new users table."""

    from baserow.contrib.database.fields.models import Field
    from baserow.core.db import specific_iterator
    from baserow_enterprise.assistant.tools.builder.tools import setup_user_source
    from baserow_enterprise.assistant.tools.builder.types.user_source import (
        UserSourceSetup,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    database = data_fixture.create_database_application(user=user, workspace=workspace)

    ctx = make_test_ctx(user, workspace)
    result = setup_user_source(
        ctx,
        application_id=builder.id,
        setup=UserSourceSetup(
            name="App Users",
            database_id=database.id,
            roles=["Admin", "Editor"],
        ),
        thought="test",
    )

    assert "user_source_id" in result
    assert "table_id" in result
    assert "Admin" in result["roles"]
    assert "Editor" in result["roles"]

    # Verify table fields
    table_fields = list(
        specific_iterator(
            Field.objects.filter(table_id=result["table_id"])
            .order_by("order")
            .select_related("content_type")
        )
    )
    field_names = [f.name for f in table_fields]
    assert "Name" in field_names
    assert "Email" in field_names
    assert "Password" in field_names
    assert "Role" in field_names

    # Verify example rows (one per role)
    from baserow.contrib.database.table.models import Table

    table = Table.objects.get(id=result["table_id"])
    model = table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 2  # Admin + Editor

    # Verify user source has auth provider
    from baserow.core.user_sources.handler import UserSourceHandler

    us = UserSourceHandler().get_user_source(result["user_source_id"])
    assert us.table_id == result["table_id"]
    providers = list(us.auth_providers.all())
    assert len(providers) == 1

    # Verify login page was created with auth_form element
    assert "login_page_id" in result
    builder.refresh_from_db()
    assert builder.login_page_id == result["login_page_id"]

    from baserow.contrib.builder.elements.handler import ElementHandler
    from baserow.contrib.builder.pages.handler import PageHandler

    login_page = PageHandler().get_page(result["login_page_id"])
    elements = ElementHandler().get_elements(login_page)
    auth_forms = [e for e in elements if e.get_type().type == "auth_form"]
    assert len(auth_forms) == 1
    assert auth_forms[0].specific.user_source_id == result["user_source_id"]


@pytest.mark.django_db(transaction=True)
def test_setup_user_source_existing_table(data_fixture):
    """Use an existing table that has the required fields."""

    from baserow_enterprise.assistant.tools.builder.tools import setup_user_source
    from baserow_enterprise.assistant.tools.builder.types.user_source import (
        UserSourceSetup,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Members")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_email_field(table=table, name="Email")
    data_fixture.create_password_field(table=table, name="Password")

    ctx = make_test_ctx(user, workspace)
    result = setup_user_source(
        ctx,
        application_id=builder.id,
        setup=UserSourceSetup(name="Members Source", table_id=table.id),
        thought="test",
    )

    assert result["table_id"] == table.id
    assert "user_source_id" in result

    from baserow.core.user_sources.handler import UserSourceHandler

    us = UserSourceHandler().get_user_source(result["user_source_id"])
    assert us.table_id == table.id


@pytest.mark.django_db(transaction=True)
def test_setup_user_source_existing_table_creates_password_field(data_fixture):
    """If the existing table lacks a password field, one is created."""

    from baserow.contrib.database.fields.models import Field
    from baserow.core.db import specific_iterator
    from baserow_enterprise.assistant.tools.builder.tools import setup_user_source
    from baserow_enterprise.assistant.tools.builder.types.user_source import (
        UserSourceSetup,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="People")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_email_field(table=table, name="Email")
    # No password field

    ctx = make_test_ctx(user, workspace)
    result = setup_user_source(
        ctx,
        application_id=builder.id,
        setup=UserSourceSetup(name="People Source", table_id=table.id),
        thought="test",
    )

    assert result["table_id"] == table.id

    # Verify password field was created
    table_fields = list(
        specific_iterator(
            Field.objects.filter(table=table)
            .order_by("order")
            .select_related("content_type")
        )
    )
    from baserow.contrib.database.fields.models import PasswordField

    password_fields = [f for f in table_fields if isinstance(f, PasswordField)]
    assert len(password_fields) == 1
    assert password_fields[0].name == "Password"
