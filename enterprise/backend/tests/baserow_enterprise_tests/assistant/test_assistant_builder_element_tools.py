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
from baserow_enterprise.assistant.tools.builder.tools import get_element_tool_factory
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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

    factory = get_element_tool_factory(user, workspace, fake_tool_helpers)
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
