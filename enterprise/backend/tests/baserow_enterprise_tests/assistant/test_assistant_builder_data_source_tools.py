from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowGetRow,
    LocalBaserowListRows,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceSort,
)
from baserow_enterprise.assistant.tools.builder.tools import (
    get_data_source_tool_factory,
)
from baserow_enterprise.assistant.tools.builder.types import (
    DataSourceFilter,
    DataSourceSort,
    GetRowDataSourceCreate,
    ListRowsDataSourceCreate,
)

from .utils import fake_tool_helpers


@pytest.mark.django_db
def test_data_source_tool_factory_returns_callback(data_fixture):
    """Test that the data source tool factory returns a valid module callback."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)


@pytest.mark.django_db
def test_create_list_rows_data_source(data_fixture):
    """Test creating a list_rows data source."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_data_sources_tool = next(
        (tool for tool in added_tools if tool.name == "create_data_sources"), None
    )
    assert create_data_sources_tool is not None

    result = create_data_sources_tool.func(
        page_id=page.id,
        data_sources=[
            ListRowsDataSourceCreate(
                ref="products_ds",
                name="Products",
                table_id=table.id,
            )
        ],
    )

    assert len(result["created_data_sources"]) == 1
    ds = result["created_data_sources"][0]
    assert ds["ref"] == "products_ds"
    assert ds["name"] == "Products"
    assert ds["type"] == "list_rows"

    # Verify ref_to_id_map is returned
    assert "products_ds" in result["ref_to_id_map"]
    assert result["ref_to_id_map"]["products_ds"] == ds["id"]

    # Verify data source was created in database
    data_source = DataSource.objects.get(id=ds["id"])
    assert data_source.name == "Products"
    assert isinstance(data_source.service.specific, LocalBaserowListRows)


@pytest.mark.django_db
def test_create_get_row_data_source(data_fixture):
    """Test creating a get_row data source."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/products/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_data_sources_tool = next(
        (tool for tool in added_tools if tool.name == "create_data_sources"), None
    )

    result = create_data_sources_tool.func(
        page_id=page.id,
        data_sources=[
            GetRowDataSourceCreate(
                ref="product_detail_ds",
                name="Product Detail",
                table_id=table.id,
                row_id="get('page_parameter.id')",
            )
        ],
    )

    assert len(result["created_data_sources"]) == 1
    ds = result["created_data_sources"][0]
    assert ds["ref"] == "product_detail_ds"
    assert ds["name"] == "Product Detail"
    assert ds["type"] == "get_row"

    # Verify data source was created with correct service
    data_source = DataSource.objects.get(id=ds["id"])
    assert isinstance(data_source.service.specific, LocalBaserowGetRow)


@pytest.mark.django_db
def test_create_data_source_with_filters(data_fixture):
    """Test creating a data source with filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Status")
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_data_sources_tool = next(
        (tool for tool in added_tools if tool.name == "create_data_sources"), None
    )

    result = create_data_sources_tool.func(
        page_id=page.id,
        data_sources=[
            ListRowsDataSourceCreate(
                ref="active_products",
                name="Active Products",
                table_id=table.id,
                filters=[
                    DataSourceFilter(
                        field_id=field.id,
                        type="equal",
                        value="'Active'",
                    )
                ],
            )
        ],
    )

    assert len(result["created_data_sources"]) == 1
    ds = result["created_data_sources"][0]

    # Verify filter was created
    data_source = DataSource.objects.get(id=ds["id"])
    filters = LocalBaserowTableServiceFilter.objects.filter(service=data_source.service)
    assert filters.count() == 1
    assert filters[0].field_id == field.id
    assert filters[0].type == "equal"


@pytest.mark.django_db
def test_create_data_source_with_sorting(data_fixture):
    """Test creating a data source with sorting."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table, name="Created At")
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_data_sources_tool = next(
        (tool for tool in added_tools if tool.name == "create_data_sources"), None
    )

    result = create_data_sources_tool.func(
        page_id=page.id,
        data_sources=[
            ListRowsDataSourceCreate(
                ref="sorted_products",
                name="Sorted Products",
                table_id=table.id,
                sortings=[
                    DataSourceSort(
                        field_id=field.id,
                        direction="DESC",
                    )
                ],
            )
        ],
    )

    assert len(result["created_data_sources"]) == 1
    ds = result["created_data_sources"][0]

    # Verify sorting was created
    data_source = DataSource.objects.get(id=ds["id"])
    sortings = LocalBaserowTableServiceSort.objects.filter(service=data_source.service)
    assert sortings.count() == 1
    assert sortings[0].field_id == field.id
    assert sortings[0].order_by == "DESC"


@pytest.mark.django_db
def test_create_data_source_with_search_query(data_fixture):
    """Test creating a data source with search query."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_data_sources_tool = next(
        (tool for tool in added_tools if tool.name == "create_data_sources"), None
    )

    result = create_data_sources_tool.func(
        page_id=page.id,
        data_sources=[
            ListRowsDataSourceCreate(
                ref="searched_products",
                name="Searched Products",
                table_id=table.id,
                search_query="get('form_data.search_input')",
            )
        ],
    )

    assert len(result["created_data_sources"]) == 1


@pytest.mark.django_db
def test_create_multiple_data_sources(data_fixture):
    """Test creating multiple data sources at once."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    products_table = data_fixture.create_database_table(
        database=database, name="Products"
    )
    categories_table = data_fixture.create_database_table(
        database=database, name="Categories"
    )
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_data_sources_tool = next(
        (tool for tool in added_tools if tool.name == "create_data_sources"), None
    )

    result = create_data_sources_tool.func(
        page_id=page.id,
        data_sources=[
            ListRowsDataSourceCreate(
                ref="products_ds",
                name="Products",
                table_id=products_table.id,
            ),
            ListRowsDataSourceCreate(
                ref="categories_ds",
                name="Categories",
                table_id=categories_table.id,
            ),
        ],
    )

    assert len(result["created_data_sources"]) == 2
    assert "products_ds" in result["ref_to_id_map"]
    assert "categories_ds" in result["ref_to_id_map"]


@pytest.mark.django_db
def test_create_data_sources_empty_list(data_fixture):
    """Test creating data sources with empty list returns empty result."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    factory = get_data_source_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_data_sources_tool = next(
        (tool for tool in added_tools if tool.name == "create_data_sources"), None
    )

    result = create_data_sources_tool.func(
        page_id=page.id,
        data_sources=[],
    )

    assert result == {"created_data_sources": [], "ref_to_id_map": {}}
