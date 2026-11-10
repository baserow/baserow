from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.groups import (
    GROUP_BUILDER_EDIT,
    GROUP_BUILDER_READ,
    mcp_tool_group_registry,
)
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError, tool_error_message
from baserow_enterprise.assistant.tools.builder import tools as kuma
from baserow_enterprise.assistant.tools.core import tools as kuma_core
from baserow_enterprise.builder.tools import (
    actions,
    applications,
    data_sources,
    elements,
    pages,
)
from baserow_enterprise.builder.tools.types import DataSourceCreate, ElementItemCreate
from baserow_enterprise_tests.assistant.utils import make_test_ctx

READ_TOOLS = [
    "list_builders",
    "list_pages",
    "list_data_sources",
    "list_elements",
    "list_element_actions",
]


@pytest.mark.django_db
def test_list_builders_lists_only_builders(data_fixture, builder_ctx):
    ctx = builder_ctx["ctx"]
    data_fixture.create_database_application(workspace=ctx.workspace)

    result = applications.list_builders(ctx)

    assert result["applications"] == [
        {
            "id": builder_ctx["builder"].id,
            "name": builder_ctx["builder"].name,
            "type": "builder",
        }
    ]
    assert result["total"] == 1
    assert result["has_more"] is False


@pytest.mark.django_db
def test_list_builders_pages(data_fixture, builder_ctx):
    ctx = builder_ctx["ctx"]
    data_fixture.create_builder_application(workspace=ctx.workspace)

    result = applications.list_builders(ctx, page=2, size=1)

    assert len(result["applications"]) == 1
    assert result["total"] == 2
    assert result["has_more"] is False


@pytest.mark.django_db
def test_list_pages(builder_ctx):
    builder = builder_ctx["builder"]

    result = pages.list_pages(builder_ctx["ctx"], builder.id)

    assert result["application_id"] == builder.id
    assert [p["name"] for p in result["pages"]] == ["Home", "About"]
    assert result["login_page_id"] is None
    assert result["user_sources"] == []
    assert result["available_roles"] == []


@pytest.mark.django_db
def test_list_elements_includes_shared_elements(builder_ctx):
    result = elements.list_elements(builder_ctx["ctx"], builder_ctx["page"].id)

    ids = [el["id"] for el in result["elements"]]
    assert builder_ctx["footer"].id in ids
    assert builder_ctx["button"].id in ids
    assert ids.index(builder_ctx["footer"].id) < ids.index(builder_ctx["button"].id)


@pytest.mark.django_db
def test_list_elements_query_count_does_not_grow_with_the_elements(
    data_fixture, builder_ctx
):
    def count_queries():
        # The first call after a change fills the caches.
        elements.list_elements(builder_ctx["ctx"], builder_ctx["page"].id)
        with CaptureQueriesContext(connection) as queries:
            elements.list_elements(builder_ctx["ctx"], builder_ctx["page"].id)
        return len(queries)

    data_fixture.create_builder_heading_element(page=builder_ctx["page"])
    few = count_queries()
    for _ in range(20):
        data_fixture.create_builder_heading_element(page=builder_ctx["page"])
        data_fixture.create_builder_heading_element(
            page=builder_ctx["builder"].shared_page
        )

    assert count_queries() == few


@pytest.mark.django_db
def test_list_actions(builder_ctx):
    result = actions.list_element_actions(builder_ctx["ctx"], builder_ctx["page"].id)

    assert [a["id"] for a in result["workflow_actions"]] == [builder_ctx["action"].id]
    assert result["workflow_actions"][0]["element_id"] == builder_ctx["button"].id


@pytest.mark.django_db
def test_kuma_tools_return_what_the_shared_tools_return(builder_ctx):
    ctx = builder_ctx["ctx"]
    kuma_ctx = make_test_ctx(builder_ctx["user"], builder_ctx["workspace"])
    builder_id = builder_ctx["builder"].id
    page_id = builder_ctx["page"].id

    listed = kuma.list_pages(kuma_ctx, builder_id, "t")
    listed.pop("next_steps")
    assert listed == pages.list_pages(ctx, builder_id)
    assert kuma.list_data_sources(kuma_ctx, page_id, "t") == (
        data_sources.list_data_sources(ctx, page_id)
    )
    assert kuma.list_elements(kuma_ctx, page_id, "t") == (
        elements.list_elements(ctx, page_id)
    )
    assert kuma.list_element_actions(kuma_ctx, page_id, "t") == (
        actions.list_element_actions(ctx, page_id)
    )
    assert kuma_core.list_builders(kuma_ctx, ["application"], "t") == {
        "application": [
            {
                "id": builder_id,
                "name": builder_ctx["builder"].name,
                "type": "application",
            }
        ]
    }


@pytest.mark.django_db
def test_read_tools_hide_other_workspaces(data_fixture, builder_ctx):
    user = builder_ctx["user"]
    other = data_fixture.create_workspace(user=user)
    ctx = ToolContext(user=user, workspace=other)
    builder_id = builder_ctx["builder"].id
    page_id = builder_ctx["page"].id

    calls = [
        (lambda: pages.list_pages(ctx, builder_id), ApplicationDoesNotExist),
        (lambda: data_sources.list_data_sources(ctx, page_id), PageDoesNotExist),
        (lambda: elements.list_elements(ctx, page_id), PageDoesNotExist),
        (lambda: actions.list_element_actions(ctx, page_id), PageDoesNotExist),
    ]
    for call, exception in calls:
        with pytest.raises(exception) as error:
            call()
        assert tool_error_message(error.value) == "Not found in this workspace."


@pytest.mark.django_db
def test_list_pages_rejects_a_database_id(data_fixture, builder_ctx):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )

    with pytest.raises(ApplicationDoesNotExist) as error:
        pages.list_pages(builder_ctx["ctx"], database.id)

    assert tool_error_message(error.value) == "Not found in this workspace."


@pytest.mark.django_db
def test_kuma_tools_explain_a_missing_builder_or_page(data_fixture, builder_ctx):
    user = builder_ctx["user"]
    other = data_fixture.create_workspace(user=user)
    kuma_ctx = make_test_ctx(user, other)
    builder_id = builder_ctx["builder"].id
    page_id = builder_ctx["page"].id

    with pytest.raises(ToolInputError) as error:
        kuma.list_pages(kuma_ctx, builder_id, "t")
    assert str(error.value) == (
        f"Application with ID {builder_id} not found in this workspace. "
        "Use list_builders to find valid application IDs."
    )
    for tool in (kuma.list_data_sources, kuma.list_elements, kuma.list_element_actions):
        with pytest.raises(ToolInputError) as error:
            tool(kuma_ctx, page_id, "t")
        assert str(error.value) == (
            f"Page with ID {page_id} not found or not accessible. "
            "Use list_pages to find valid page IDs."
        )


@pytest.mark.parametrize("name", READ_TOOLS)
def test_read_tools_are_read_only_builder_read_tools(name):
    tool = mcp_tool_registry.get(name)

    assert tool.group == GROUP_BUILDER_READ
    assert tool.read_only is True
    assert tool.function.__doc__


@pytest.mark.django_db
def test_endpoints_from_before_the_groups_list_no_builder_tools(data_fixture):
    explicit = data_fixture.create_mcp_endpoint(allowed_tools=["list_tables"])
    legacy = data_fixture.create_mcp_endpoint(allowed_tools=None)

    for endpoint in (explicit, legacy):
        names = {tool.name for tool in mcp_tool_registry.get_allowed_tools(endpoint)}
        assert not names & set(READ_TOOLS)
        for name in READ_TOOLS:
            assert mcp_tool_registry.get_allowed_tool(endpoint, name) is None
    assert not set(READ_TOOLS) & set(LEGACY_DEFAULT_TOOLS)


@pytest.mark.django_db
def test_read_only_preset_lists_the_read_tools_and_no_write_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    preset_groups = {
        group.type
        for group in mcp_tool_group_registry.get_all()
        if group.read_only_preset
    }
    preset = [
        tool.name
        for tool in mcp_tool_registry.get_enabled_tools()
        if tool.group in preset_groups
    ]
    assert GROUP_BUILDER_EDIT not in preset_groups

    endpoint, _ = MCPEndpointHandler().grant_oauth_client(
        user, workspace, "client", "App", preset
    )

    allowed = {tool.name for tool in mcp_tool_registry.get_allowed_tools(endpoint)}
    assert set(READ_TOOLS) <= allowed
    assert not any(
        not mcp_tool_registry.get(name).read_only for name in allowed if name in preset
    )
    builder_tools = {
        tool.name
        for tool in mcp_tool_registry.get_enabled_tools()
        if tool.group in (GROUP_BUILDER_READ, GROUP_BUILDER_EDIT)
    }
    assert allowed & builder_tools == set(READ_TOOLS)


@pytest.mark.django_db
def test_new_connection_starts_with_the_read_tools(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    endpoint = MCPEndpointHandler().create_endpoint(user, workspace, "Key")

    assert set(READ_TOOLS) <= set(endpoint.allowed_tools)


@pytest.mark.django_db
def test_list_data_sources_includes_the_shared_page(data_fixture, builder_ctx):
    page = builder_ctx["page"]
    shared_page = builder_ctx["builder"].shared_page
    shared = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=shared_page,
        table=builder_ctx["data_source"].service.specific.table,
        name="Shared",
    )

    listed = data_sources.list_data_sources(builder_ctx["ctx"], page.id)["data_sources"]

    assert [(ds["id"], ds.get("page_name")) for ds in listed] == [
        (shared.id, "[shared]"),
        (builder_ctx["data_source"].id, "Home"),
    ]
    only_shared = data_sources.list_data_sources(builder_ctx["ctx"], shared_page.id)
    assert [ds["id"] for ds in only_shared["data_sources"]] == [shared.id]


@pytest.mark.django_db
def test_list_pages_gives_the_shared_page_to_create_a_data_source_on(builder_ctx):
    builder = builder_ctx["builder"]

    listed = pages.list_pages(builder_ctx["ctx"], builder.id)

    assert listed["shared_page_id"] == builder.shared_page.id
    assert builder.shared_page.id not in [page["id"] for page in listed["pages"]]


@pytest.mark.django_db
def test_a_header_can_use_a_data_source_made_on_the_page_list_pages_gives(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    shared_page_id = pages.list_pages(ctx, builder_ctx["builder"].id)["shared_page_id"]
    data_source = data_sources.create_data_sources(
        ctx,
        shared_page_id,
        [
            DataSourceCreate(
                ref="d",
                name="Shared",
                type="list_rows",
                table_id=builder_ctx["data_source"].service.specific.table_id,
            )
        ],
    )["ref_to_id_map"]["d"]

    result = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="top", type="header"),
            ElementItemCreate(
                ref="list", type="repeat", parent_element="top", data_source=data_source
            ),
        ],
    )

    assert not result.get("errors")
