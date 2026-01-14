from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow_enterprise.assistant.tools.builder.tools import (
    get_workflow_action_tool_factory,
)
from baserow_enterprise.assistant.tools.builder.types import (
    CreateRowActionCreate,
    DeleteRowActionCreate,
    NotificationActionCreate,
    OpenPageActionCreate,
    RefreshDataSourceActionCreate,
    UpdateRowActionCreate,
)

from .utils import fake_tool_helpers


@pytest.mark.django_db
def test_workflow_action_tool_factory_returns_callback(data_fixture):
    """Test that the workflow action tool factory returns a valid module callback."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)


@pytest.mark.django_db
def test_create_notification_action(data_fixture):
    """Test creating a notification workflow action."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    button = data_fixture.create_builder_button_element(page=page)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )
    assert create_actions_tool is not None

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[
            NotificationActionCreate(
                element_ref="btn1",
                event="click",
                title="'Success!'",
                description="'Item created successfully.'",
            )
        ],
        element_refs={"btn1": button.id},
    )

    assert len(result["created_workflow_actions"]) == 1
    action = result["created_workflow_actions"][0]
    assert action["type"] == "notification"
    assert action["element_ref"] == "btn1"
    assert action["event"] == "click"

    # Verify action was created in database
    db_action = BuilderWorkflowAction.objects.get(id=action["id"])
    assert db_action.element_id == button.id


@pytest.mark.django_db
def test_create_open_page_action(data_fixture):
    """Test creating an open_page workflow action."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    target_page = data_fixture.create_builder_page(
        builder=builder,
        name="Detail",
        path="/detail/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    link = data_fixture.create_builder_link_element(page=page)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[
            OpenPageActionCreate(
                element_ref="link1",
                event="click",
                navigate_to_page_id=target_page.id,
                page_parameters=[{"name": "id", "value": "get('current_record.id')"}],
            )
        ],
        element_refs={"link1": link.id},
    )

    assert len(result["created_workflow_actions"]) == 1
    action = result["created_workflow_actions"][0]
    assert action["type"] == "open_page"


@pytest.mark.django_db
def test_create_row_action(data_fixture):
    """Test creating a create_row workflow action."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    form = data_fixture.create_builder_form_container_element(page=page)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[
            CreateRowActionCreate(
                element_ref="form1",
                event="submit",
                table_id=table.id,
                field_values={name_field.id: "get('form_data.name_input')"},
            )
        ],
        element_refs={"form1": form.id},
    )

    assert len(result["created_workflow_actions"]) == 1
    action = result["created_workflow_actions"][0]
    assert action["type"] == "create_row"
    assert action["event"] == "submit"


@pytest.mark.django_db
def test_update_row_action(data_fixture):
    """Test creating an update_row workflow action."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    form = data_fixture.create_builder_form_container_element(page=page)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[
            UpdateRowActionCreate(
                element_ref="form1",
                event="submit",
                table_id=table.id,
                row_id="get('page_parameter.id')",
                field_values={name_field.id: "get('form_data.name_input')"},
            )
        ],
        element_refs={"form1": form.id},
    )

    assert len(result["created_workflow_actions"]) == 1
    action = result["created_workflow_actions"][0]
    assert action["type"] == "update_row"


@pytest.mark.django_db
def test_delete_row_action(data_fixture):
    """Test creating a delete_row workflow action."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    button = data_fixture.create_builder_button_element(page=page)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[
            DeleteRowActionCreate(
                element_ref="delete_btn",
                event="click",
                table_id=table.id,
                row_id="get('current_record.id')",
            )
        ],
        element_refs={"delete_btn": button.id},
    )

    assert len(result["created_workflow_actions"]) == 1
    action = result["created_workflow_actions"][0]
    assert action["type"] == "delete_row"


@pytest.mark.django_db
def test_refresh_data_source_action(data_fixture):
    """Test creating a refresh_data_source workflow action."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    button = data_fixture.create_builder_button_element(page=page)
    ds = data_fixture.create_builder_local_baserow_list_rows_data_source(page=page)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[
            RefreshDataSourceActionCreate(
                element_ref="refresh_btn",
                event="click",
                data_source_id=ds.id,
            )
        ],
        element_refs={"refresh_btn": button.id},
    )

    assert len(result["created_workflow_actions"]) == 1
    action = result["created_workflow_actions"][0]
    assert action["type"] == "refresh_data_source"


@pytest.mark.django_db
def test_multiple_actions_same_element(data_fixture):
    """Test creating multiple actions attached to the same element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    ds = data_fixture.create_builder_local_baserow_list_rows_data_source(page=page)
    form = data_fixture.create_builder_form_container_element(page=page)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[
            CreateRowActionCreate(
                element_ref="form1",
                event="submit",
                table_id=table.id,
                field_values={name_field.id: "get('form_data.name_input')"},
            ),
            RefreshDataSourceActionCreate(
                element_ref="form1",
                event="submit",
                data_source_id=ds.id,
            ),
            NotificationActionCreate(
                element_ref="form1",
                event="submit",
                title="'Success!'",
                description="'Item created.'",
            ),
        ],
        element_refs={"form1": form.id},
    )

    assert len(result["created_workflow_actions"]) == 3

    # All actions should be attached to the same element
    action_element_refs = {a["element_ref"] for a in result["created_workflow_actions"]}
    assert action_element_refs == {"form1"}


@pytest.mark.django_db
def test_element_ref_not_found_error(data_fixture):
    """Test error when referencing a non-existent element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    with pytest.raises(ValueError, match="Element ref 'nonexistent' not found"):
        create_actions_tool.func(
            page_id=page.id,
            workflow_actions=[
                NotificationActionCreate(
                    element_ref="nonexistent",
                    event="click",
                    title="'Test'",
                )
            ],
            element_refs={},
        )


@pytest.mark.django_db
def test_create_workflow_actions_empty_list(data_fixture):
    """Test creating workflow actions with empty list returns empty result."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_workflow_action_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_actions_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflow_actions"), None
    )

    result = create_actions_tool.func(
        page_id=page.id,
        workflow_actions=[],
    )

    assert result == {"created_workflow_actions": []}
