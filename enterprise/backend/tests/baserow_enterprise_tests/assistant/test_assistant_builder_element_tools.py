from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.builder.elements.models import (
    ButtonElement,
    ChoiceElement,
    ColumnElement,
    FormContainerElement,
    HeadingElement,
    InputTextElement,
    RepeatElement,
    TableElement,
    TextElement,
)
from baserow_enterprise.assistant.tools.builder.tools import get_page_content_tool_factory
from baserow_enterprise.assistant.tools.builder.types import (
    ButtonElementCreate,
    ChoiceElementCreate,
    ChoiceOption,
    ColumnElementCreate,
    FormContainerElementCreate,
    HeadingElementCreate,
    InputTextElementCreate,
    RepeatElementCreate,
    TableElementCreate,
    TextElementCreate,
)

from .utils import fake_tool_helpers


@pytest.mark.django_db
def test_element_tool_factory_returns_callback(data_fixture):
    """Test that the element tool factory returns a valid module callback."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)


@pytest.mark.django_db
def test_create_heading_element(data_fixture):
    """Test creating a simple heading element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )
    assert create_elements_tool is not None

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            HeadingElementCreate(
                ref="heading1",
                value="'Welcome to the App'",
                level=1,
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["ref"] == "heading1"
    assert result["created_elements"][0]["type"] == "heading"
    assert result["created_elements"][0]["id"] is not None

    # Verify element was created in database
    assert HeadingElement.objects.filter(
        page=page, id=result["created_elements"][0]["id"]
    ).exists()


@pytest.mark.django_db
def test_create_text_element(data_fixture):
    """Test creating a text element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            TextElementCreate(
                ref="text1",
                value="'This is some paragraph text.'",
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "text"

    # Verify element was created
    assert TextElement.objects.filter(page=page).exists()


@pytest.mark.django_db
def test_create_button_element(data_fixture):
    """Test creating a button element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            ButtonElementCreate(
                ref="btn1",
                value="'Click Me'",
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "button"
    assert ButtonElement.objects.filter(page=page).exists()


@pytest.mark.django_db
def test_create_column_layout(data_fixture):
    """Test creating a column layout element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            ColumnElementCreate(
                ref="cols1",
                column_amount=3,
                column_gap=20,
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "column"

    column = ColumnElement.objects.get(page=page)
    assert column.column_amount == 3
    assert column.column_gap == 20


@pytest.mark.django_db
def test_create_nested_elements(data_fixture):
    """Test creating elements nested inside a container."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            ColumnElementCreate(ref="cols", column_amount=2),
            HeadingElementCreate(
                ref="h1",
                value="'Column 1 Heading'",
                parent_element_ref="cols",
                place_in_container="0",
            ),
            HeadingElementCreate(
                ref="h2",
                value="'Column 2 Heading'",
                parent_element_ref="cols",
                place_in_container="1",
            ),
        ],
    )

    assert len(result["created_elements"]) == 3
    assert "cols" in result["ref_to_id_map"]
    assert "h1" in result["ref_to_id_map"]
    assert "h2" in result["ref_to_id_map"]

    # Verify nested structure
    column = ColumnElement.objects.get(page=page)
    h1 = HeadingElement.objects.get(page=page, id=result["ref_to_id_map"]["h1"])
    h2 = HeadingElement.objects.get(page=page, id=result["ref_to_id_map"]["h2"])

    assert h1.parent_element_id == column.id
    assert h2.parent_element_id == column.id


@pytest.mark.django_db
def test_create_form_with_inputs(data_fixture):
    """Test creating a form container with input elements."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            FormContainerElementCreate(
                ref="form",
                submit_button_label="Submit",
            ),
            InputTextElementCreate(
                ref="name_input",
                label="Name",
                placeholder="Enter your name",
                required=True,
                parent_element_ref="form",
            ),
            InputTextElementCreate(
                ref="email_input",
                label="Email",
                placeholder="Enter your email",
                validation_type="email",
                parent_element_ref="form",
            ),
        ],
    )

    assert len(result["created_elements"]) == 3

    # Verify form structure
    form = FormContainerElement.objects.get(page=page)
    name_input = InputTextElement.objects.get(
        page=page, id=result["ref_to_id_map"]["name_input"]
    )
    email_input = InputTextElement.objects.get(
        page=page, id=result["ref_to_id_map"]["email_input"]
    )

    assert name_input.parent_element_id == form.id
    assert email_input.parent_element_id == form.id
    assert name_input.required is True
    assert email_input.validation_type == "email"


@pytest.mark.django_db
def test_create_choice_element_with_options(data_fixture):
    """Test creating a choice element with options."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            ChoiceElementCreate(
                ref="status_choice",
                label="Status",
                options=[
                    ChoiceOption(name="Pending", value="pending"),
                    ChoiceOption(name="Active", value="active"),
                    ChoiceOption(name="Completed", value="completed"),
                ],
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "choice"

    # Verify options were created
    choice = ChoiceElement.objects.get(page=page)
    options = choice.choiceelementoption_set.all()
    assert options.count() == 3
    option_values = {opt.value for opt in options}
    assert option_values == {"pending", "active", "completed"}


@pytest.mark.django_db
def test_create_table_element(data_fixture):
    """Test creating a table element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            TableElementCreate(
                ref="products_table",
                items_per_page=10,
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "table"

    table = TableElement.objects.get(page=page)
    assert table.items_per_page == 10


@pytest.mark.django_db
def test_create_repeat_element(data_fixture):
    """Test creating a repeat element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            RepeatElementCreate(
                ref="cards_repeater",
                orientation="horizontal",
                items_per_page=12,
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    assert result["created_elements"][0]["type"] == "repeat"

    repeat = RepeatElement.objects.get(page=page)
    assert repeat.orientation == "horizontal"
    assert repeat.items_per_page == 12


@pytest.mark.django_db
def test_element_ref_not_found_error(data_fixture):
    """Test error when referencing a non-existent parent element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    with pytest.raises(ValueError, match="Parent element ref 'nonexistent' not found"):
        create_elements_tool.func(
            page_id=page.id,
            elements=[
                HeadingElementCreate(
                    ref="orphan",
                    value="'Orphaned heading'",
                    parent_element_ref="nonexistent",
                )
            ],
        )


@pytest.mark.django_db
def test_create_elements_empty_list(data_fixture):
    """Test creating elements with empty list returns empty result."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[],
    )

    assert result == {"created_elements": []}


@pytest.mark.django_db
def test_create_elements_with_data_source_ref(data_fixture):
    """Test creating elements that reference data sources by ref."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    # Create a data source to reference
    ds = data_fixture.create_builder_local_baserow_list_rows_data_source(page=page)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )

    result = create_elements_tool.func(
        page_id=page.id,
        elements=[
            TableElementCreate(ref="table1"),
        ],
        data_source_refs={"products_ds": ds.id},
    )

    assert len(result["created_elements"]) == 1


@pytest.mark.django_db
def test_add_element_to_existing_container_by_id(data_fixture):
    """Test adding elements to an existing container using parent_element_id."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )
    list_elements_tool = next(
        (tool for tool in added_tools if tool.name == "list_elements"), None
    )

    # First, create a form container
    result1 = create_elements_tool.func(
        page_id=page.id,
        elements=[
            FormContainerElementCreate(
                ref="contact_form",
                submit_button_label="Submit",
            ),
        ],
    )

    form_id = result1["ref_to_id_map"]["contact_form"]

    # Verify the form exists and list_elements shows it as a container
    list_result = list_elements_tool.func(page_id=page.id)
    form_item = next(
        (el for el in list_result["elements"] if el["id"] == form_id), None
    )
    assert form_item is not None
    assert form_item["is_container"] is True

    # Now add an input to the existing form using parent_element_id
    result2 = create_elements_tool.func(
        page_id=page.id,
        elements=[
            InputTextElementCreate(
                ref="phone_input",
                label="Phone",
                placeholder="Enter your phone",
                parent_element_id=form_id,  # Reference existing form by ID
            ),
        ],
    )

    assert len(result2["created_elements"]) == 1
    assert result2["created_elements"][0]["type"] == "input_text"

    # Verify the input is inside the form
    phone_input = InputTextElement.objects.get(
        page=page, id=result2["ref_to_id_map"]["phone_input"]
    )
    assert phone_input.parent_element_id == form_id


@pytest.mark.django_db
def test_list_elements_shows_container_types(data_fixture):
    """Test that list_elements correctly identifies container elements."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_elements_tool = next(
        (tool for tool in added_tools if tool.name == "create_elements"), None
    )
    list_elements_tool = next(
        (tool for tool in added_tools if tool.name == "list_elements"), None
    )

    # Create various element types
    create_elements_tool.func(
        page_id=page.id,
        elements=[
            ColumnElementCreate(ref="cols", column_amount=2),
            FormContainerElementCreate(ref="form"),
            HeadingElementCreate(ref="heading", value="'Title'"),
            TextElementCreate(ref="text", value="'Content'"),
        ],
    )

    # List elements and check is_container flag
    result = list_elements_tool.func(page_id=page.id)

    elements_by_type = {el["type"]: el for el in result["elements"]}

    # Containers should have is_container=True
    assert elements_by_type["column"]["is_container"] is True
    assert elements_by_type["form_container"]["is_container"] is True

    # Non-containers should have is_container=False
    assert elements_by_type["heading"]["is_container"] is False
    assert elements_by_type["text"]["is_container"] is False


@pytest.mark.django_db
def test_list_workflow_actions_returns_actions_with_field_mappings(data_fixture):
    """Test that list_workflow_actions returns actions with field_mappings for create/update row actions."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Name")

    # Create a form with a submit action that creates a row
    form = data_fixture.create_builder_form_container_element(page=page)
    input_el = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form
    )

    # Create integration and service with the table
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration, table=table
    )

    # Create workflow action with the service
    create_row_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        element=form,
        event="submit",
        service=service,
    )

    # Add field mapping
    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableServiceFieldMapping,
    )
    from baserow.core.formula.types import BaserowFormulaObject

    LocalBaserowTableServiceFieldMapping.objects.create(
        service=create_row_action.service,
        field=field,
        value=BaserowFormulaObject.create(f"get('form_data.{input_el.id}')"),
        enabled=True,
    )

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    list_workflow_actions_tool = next(
        (tool for tool in added_tools if tool.name == "list_workflow_actions"), None
    )
    assert list_workflow_actions_tool is not None

    result = list_workflow_actions_tool.func(page_id=page.id)

    assert "workflow_actions" in result
    assert len(result["workflow_actions"]) == 1

    action = result["workflow_actions"][0]
    assert action["id"] == create_row_action.id
    assert action["type"] == "create_row"
    assert action["element_id"] == form.id
    assert action["event"] == "submit"
    assert action["table_id"] == table.id
    assert action["field_mappings"] is not None
    assert len(action["field_mappings"]) == 1
    assert action["field_mappings"][0]["field_id"] == field.id
    assert action["field_mappings"][0]["field_name"] == "Name"
    assert f"form_data.{input_el.id}" in action["field_mappings"][0]["value"]


@pytest.mark.django_db
def test_add_field_mapping_to_create_row_action(data_fixture):
    """Test adding a field mapping to an existing create_row action."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table, name="Name")
    field2 = data_fixture.create_text_field(table=table, name="Email")

    # Create a form with existing create_row action
    form = data_fixture.create_builder_form_container_element(page=page)
    input1 = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form
    )

    # Create integration and service with the table
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration, table=table
    )

    # Create workflow action
    create_row_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        element=form,
        event="submit",
        service=service,
    )

    # Add initial field mapping
    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableServiceFieldMapping,
    )
    from baserow.core.formula.types import BaserowFormulaObject

    LocalBaserowTableServiceFieldMapping.objects.create(
        service=create_row_action.service,
        field=field1,
        value=BaserowFormulaObject.create(f"get('form_data.{input1.id}')"),
        enabled=True,
    )

    # Now add a new input and we want to map it too
    input2 = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form
    )

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    add_field_mapping_tool = next(
        (tool for tool in added_tools if tool.name == "add_field_mapping"), None
    )
    assert add_field_mapping_tool is not None

    # Add mapping for the new field
    result = add_field_mapping_tool.func(
        action_id=create_row_action.id,
        field_id=field2.id,
        value_formula=f"get('form_data.{input2.id}')",
    )

    assert result["status"] == "created"
    assert len(result["field_mappings"]) == 2

    # Verify both mappings exist
    field_ids = {fm["field_id"] for fm in result["field_mappings"]}
    assert field_ids == {field1.id, field2.id}


@pytest.mark.django_db
def test_add_field_mapping_updates_existing(data_fixture):
    """Test that add_field_mapping updates an existing mapping for the same field."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Name")

    # Create a form with existing create_row action and mapping
    form = data_fixture.create_builder_form_container_element(page=page)
    old_input = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form
    )

    # Create integration and service with the table
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration, table=table
    )

    create_row_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        element=form,
        event="submit",
        service=service,
    )

    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableServiceFieldMapping,
    )
    from baserow.core.formula.types import BaserowFormulaObject

    LocalBaserowTableServiceFieldMapping.objects.create(
        service=create_row_action.service,
        field=field,
        value=BaserowFormulaObject.create(f"get('form_data.{old_input.id}')"),
        enabled=True,
    )

    # Create a new input to replace the old one
    new_input = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form
    )

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    add_field_mapping_tool = next(
        (tool for tool in added_tools if tool.name == "add_field_mapping"), None
    )

    # Update the existing mapping to point to the new input
    result = add_field_mapping_tool.func(
        action_id=create_row_action.id,
        field_id=field.id,
        value_formula=f"get('form_data.{new_input.id}')",
    )

    assert result["status"] == "updated"
    assert len(result["field_mappings"]) == 1  # Still just one mapping
    assert f"form_data.{new_input.id}" in result["field_mappings"][0]["value"]


@pytest.mark.django_db
def test_add_field_mapping_fails_for_non_upsert_actions(data_fixture):
    """Test that add_field_mapping fails for actions that don't support field mappings."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    # Create a notification action (doesn't support field mappings)
    button = data_fixture.create_builder_button_element(page=page)
    notification_action = data_fixture.create_notification_workflow_action(
        page=page,
        element=button,
        event="click",
    )

    factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    add_field_mapping_tool = next(
        (tool for tool in added_tools if tool.name == "add_field_mapping"), None
    )

    with pytest.raises(ValueError, match="Cannot add field mappings to action type"):
        add_field_mapping_tool.func(
            action_id=notification_action.id,
            field_id=123,
            value_formula="get('form_data.456')",
        )
