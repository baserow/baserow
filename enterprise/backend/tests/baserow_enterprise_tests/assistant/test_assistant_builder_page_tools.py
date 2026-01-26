from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.builder.pages.models import Page
from baserow_enterprise.assistant.tools.builder.tools import (
    get_page_tool_factory,
)
from baserow_enterprise.assistant.tools.builder.types import (
    PageCreate,
    PagePathParam,
    PageQueryParam,
)

from .utils import fake_tool_helpers


@pytest.mark.django_db
def test_create_pages_tool_factory_returns_callback(data_fixture):
    """Test that the page tool factory returns a valid module callback."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    factory = get_page_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)


@pytest.mark.django_db
def test_create_simple_page(data_fixture):
    """Test creating a simple page without parameters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    factory = get_page_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_pages_tool = next(
        (tool for tool in added_tools if tool.name == "create_pages"), None
    )
    assert create_pages_tool is not None

    result = create_pages_tool.func(
        application_id=builder.id,
        pages=[PageCreate(name="About", path="/about")],
    )

    assert len(result["created_pages"]) == 1
    assert result["created_pages"][0]["name"] == "About"
    assert result["created_pages"][0]["path"] == "/about"
    assert result["created_pages"][0]["id"] is not None

    # Verify page was actually created in the database
    assert Page.objects.filter(builder=builder, name="About", path="/about").exists()


@pytest.mark.django_db
def test_create_page_with_path_params(data_fixture):
    """Test creating a page with path parameters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    factory = get_page_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_pages_tool = next(
        (tool for tool in added_tools if tool.name == "create_pages"), None
    )

    result = create_pages_tool.func(
        application_id=builder.id,
        pages=[
            PageCreate(
                name="Product Detail",
                path="/products/:id",
                path_params=[PagePathParam(name="id", type="numeric")],
            )
        ],
    )

    assert len(result["created_pages"]) == 1
    page = result["created_pages"][0]
    assert page["name"] == "Product Detail"
    assert page["path"] == "/products/:id"
    assert len(page["path_params"]) == 1
    assert page["path_params"][0]["name"] == "id"
    assert page["path_params"][0]["type"] == "numeric"


@pytest.mark.django_db
def test_create_page_with_query_params(data_fixture):
    """Test creating a page with query parameters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    factory = get_page_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_pages_tool = next(
        (tool for tool in added_tools if tool.name == "create_pages"), None
    )

    result = create_pages_tool.func(
        application_id=builder.id,
        pages=[
            PageCreate(
                name="Search",
                path="/search",
                query_params=[
                    PageQueryParam(name="q", type="text"),
                    PageQueryParam(name="page", type="numeric"),
                ],
            )
        ],
    )

    assert len(result["created_pages"]) == 1
    page = result["created_pages"][0]
    assert page["name"] == "Search"
    assert len(page["query_params"]) == 2


@pytest.mark.django_db
def test_create_multiple_pages(data_fixture):
    """Test creating multiple pages in a single call."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    factory = get_page_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_pages_tool = next(
        (tool for tool in added_tools if tool.name == "create_pages"), None
    )

    result = create_pages_tool.func(
        application_id=builder.id,
        pages=[
            PageCreate(name="Home", path="/"),
            PageCreate(name="About", path="/about"),
            PageCreate(name="Contact", path="/contact"),
        ],
    )

    assert len(result["created_pages"]) == 3
    page_names = {p["name"] for p in result["created_pages"]}
    assert page_names == {"Home", "About", "Contact"}


@pytest.mark.django_db
def test_create_pages_empty_list(data_fixture):
    """Test creating pages with empty list returns empty result."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    factory = get_page_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_pages_tool = next(
        (tool for tool in added_tools if tool.name == "create_pages"), None
    )

    result = create_pages_tool.func(
        application_id=builder.id,
        pages=[],
    )

    assert result == {"created_pages": []}
