"""
Unit tests for the builder assistant tools.

Tests cover pages, data sources, elements, and workflow actions using
the RunContext + FunctionToolset pattern.
"""

import pytest

from baserow_enterprise.assistant.tools.builder.tools import (
    create_actions,
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
    update_page,
)
from baserow_enterprise.assistant.tools.builder.types import (
    ActionCreate,
    DataSourceCreate,
    DataSourceSort,
    DataSourceUpdate,
    DisplayElementCreate,
    ElementUpdate,
    FormElementCreate,
    LayoutElementCreate,
    PageCreate,
    PagePathParam,
    PageUpdate,
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
        pass

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
