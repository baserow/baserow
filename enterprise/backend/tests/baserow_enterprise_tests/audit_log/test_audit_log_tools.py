"""Tests for the audit log tools shared by MCP and Kuma."""

import json
from datetime import datetime, timedelta, timezone

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from baserow_enterprise_tests.assistant.utils import make_test_ctx
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.exceptions import PermissionException
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.groups import (
    AREA_AUDIT_LOG,
    GROUP_AUDIT_LOG_READ,
    mcp_tool_group_registry,
)
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.subjects import UserSubjectType
from baserow.core.tools import ToolContext
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.tools.core.tools import (
    list_audit_log as kuma_list_audit_log,
)
from baserow_enterprise.assistant.tools.routing import is_tool_active
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.audit_log.tools import list_audit_log, search_audit_log
from baserow_premium.license.exceptions import FeaturesNotAvailableError

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
AUDIT_LOG_TOOLS = ["list_audit_log", "search_audit_log"]


def _call(endpoint, name, arguments):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _entry(workspace, user, days_ago=0, **kwargs):
    defaults = {
        "workspace_id": workspace.id,
        "actor_id": user.id,
        "actor_name": user.email,
        "action_type": "create_table",
        "action_timestamp": NOW - timedelta(days=days_ago),
        "action_params": {"table_id": 1, "table_name": "Leads"},
        "original_action_short_descr": "Create table",
        "original_action_long_descr": 'Table "%(table_name)s" created',
        "ip_address": "127.0.0.1",
    }
    return AuditLogEntry.objects.create(**{**defaults, **kwargs})


@pytest.fixture
def admin_ctx(enterprise_data_fixture, enable_enterprise, synced_roles):
    user = enterprise_data_fixture.create_user(email="anna@example.com")
    workspace = enterprise_data_fixture.create_workspace(user=user)
    return ToolContext(user=user, workspace=workspace)


@pytest.mark.django_db
def test_list_audit_log_returns_workspace_entries_newest_first(admin_ctx):
    older = _entry(admin_ctx.workspace, admin_ctx.user, days_ago=2)
    newer = _entry(admin_ctx.workspace, admin_ctx.user, days_ago=1)

    result = list_audit_log(admin_ctx)

    assert [entry["id"] for entry in result["entries"]] == [newer.id, older.id]
    assert result["has_more"] is False
    assert result["entries"][0] == {
        "id": newer.id,
        "timestamp": (NOW - timedelta(days=1)).isoformat(),
        "actor": {
            "id": admin_ctx.user.id,
            "type": UserSubjectType.type,
            "name": "anna@example.com",
        },
        "action_type": "create_table",
        "description": newer.description,
        "ip_address": "127.0.0.1",
    }


@pytest.mark.django_db
def test_list_audit_log_shows_timestamps_in_the_user_timezone(admin_ctx):
    _entry(admin_ctx.workspace, admin_ctx.user)
    admin_ctx.timezone = "Europe/Amsterdam"

    timestamp = list_audit_log(admin_ctx)["entries"][0]["timestamp"]

    assert timestamp == "2026-11-02T13:00:00+01:00"


@pytest.mark.django_db
def test_list_audit_log_never_shows_other_workspace(admin_ctx, enterprise_data_fixture):
    other = enterprise_data_fixture.create_workspace(user=admin_ctx.user)
    _entry(other, admin_ctx.user)
    AuditLogEntry.objects.create(
        workspace_id=None,
        actor_id=admin_ctx.user.id,
        action_type="create_workspace",
        action_timestamp=NOW,
    )

    assert list_audit_log(admin_ctx)["entries"] == []


@pytest.mark.django_db
def test_list_audit_log_filters(admin_ctx, enterprise_data_fixture):
    colleague = enterprise_data_fixture.create_user()
    workspace = admin_ctx.workspace
    mine = _entry(workspace, admin_ctx.user, days_ago=1)
    theirs = _entry(workspace, colleague, days_ago=10, action_type="delete_table")
    # An agent can have the same id as a user.
    _entry(
        workspace,
        admin_ctx.user,
        actor_type=AgentSubjectType.type,
        actor_name="Agent",
    )

    def ids(**filters):
        return [
            entry["id"] for entry in list_audit_log(admin_ctx, **filters)["entries"]
        ]

    assert ids(user_id=admin_ctx.user.id) == [mine.id]
    assert ids(action_types=["delete_table"]) == [theirs.id]
    assert ids(to_timestamp=NOW - timedelta(days=5)) == [theirs.id]
    assert ids(
        from_timestamp=NOW - timedelta(days=5), to_timestamp=NOW - timedelta(hours=1)
    ) == [mine.id]


@pytest.mark.django_db
def test_list_audit_log_reads_a_timestamp_without_offset_in_the_user_timezone(
    admin_ctx,
):
    entry = _entry(admin_ctx.workspace, admin_ctx.user)
    admin_ctx.timezone = "Europe/Amsterdam"

    # 12:30 in Amsterdam is before the entry, at 13:00 there.
    before = list_audit_log(admin_ctx, to_timestamp=datetime(2026, 11, 2, 12, 30))
    after = list_audit_log(admin_ctx, from_timestamp=datetime(2026, 11, 2, 12, 30))

    assert before["entries"] == []
    assert [e["id"] for e in after["entries"]] == [entry.id]


@pytest.mark.django_db
def test_list_audit_log_pages(admin_ctx):
    for days_ago in range(3):
        _entry(admin_ctx.workspace, admin_ctx.user, days_ago=days_ago)

    first = list_audit_log(admin_ctx, size=2)
    last = list_audit_log(admin_ctx, page=2, size=2)

    assert (len(first["entries"]), first["has_more"]) == (2, True)
    assert (len(last["entries"]), last["has_more"]) == (1, False)


@pytest.mark.django_db
def test_audit_log_needs_enterprise_licence(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    ctx = ToolContext(user=user, workspace=workspace)

    with pytest.raises(FeaturesNotAvailableError):
        list_audit_log(ctx)
    with pytest.raises(FeaturesNotAvailableError):
        search_audit_log(ctx, "table", NOW - timedelta(days=1), NOW)


@pytest.mark.django_db
def test_audit_log_refuses_non_admin(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(member, "BUILDER")]
    )
    _entry(workspace, admin)
    ctx = ToolContext(user=member, workspace=workspace)

    with pytest.raises(PermissionException):
        list_audit_log(ctx)
    with pytest.raises(PermissionException):
        search_audit_log(ctx, "table", NOW - timedelta(days=1), NOW)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    ["anna@example", "ANNA", "create_table", "create table"],
)
def test_search_audit_log_matches_actor_type_and_description(admin_ctx, query):
    entry = _entry(admin_ctx.workspace, admin_ctx.user)

    result = search_audit_log(admin_ctx, query, NOW - timedelta(days=1), NOW)

    assert [found["id"] for found in result["entries"]] == [entry.id]


@pytest.mark.django_db
def test_search_audit_log_stays_in_workspace_and_range(
    admin_ctx, enterprise_data_fixture
):
    other = enterprise_data_fixture.create_workspace(user=admin_ctx.user)
    _entry(other, admin_ctx.user)
    _entry(admin_ctx.workspace, admin_ctx.user, days_ago=10)
    _entry(admin_ctx.workspace, admin_ctx.user, action_type="other", days_ago=0)

    result = search_audit_log(
        admin_ctx, "create_table", NOW - timedelta(days=1), NOW + timedelta(days=1)
    )

    assert result["entries"] == []


@pytest.mark.django_db
def test_search_audit_log_rejects_range_over_90_days(admin_ctx):
    with pytest.raises(DjangoValidationError):
        search_audit_log(admin_ctx, "table", NOW - timedelta(days=91), NOW)


@pytest.mark.django_db
def test_search_audit_log_rejects_reversed_range(admin_ctx):
    with pytest.raises(DjangoValidationError):
        search_audit_log(admin_ctx, "table", NOW, NOW - timedelta(days=1))


def test_audit_log_group_is_not_in_the_read_only_preset():
    group = mcp_tool_group_registry.get(GROUP_AUDIT_LOG_READ)
    assert group.area == AREA_AUDIT_LOG
    assert group.read_only_preset is False
    assert group.order == 100
    for name in AUDIT_LOG_TOOLS:
        tool = mcp_tool_registry.get(name)
        assert tool.group == GROUP_AUDIT_LOG_READ
        assert tool.read_only is True


@pytest.mark.django_db
def test_new_endpoint_does_not_get_the_audit_log_tools(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    endpoint = MCPEndpointHandler().create_endpoint(user, workspace, "Key")

    assert not set(endpoint.allowed_tools) & set(AUDIT_LOG_TOOLS)
    assert "list_tables" in endpoint.allowed_tools


@pytest.mark.django_db(transaction=True)
def test_list_audit_log_over_mcp(admin_ctx, enterprise_data_fixture):
    entry = _entry(admin_ctx.workspace, admin_ctx.user)
    endpoint = enterprise_data_fixture.create_mcp_endpoint(
        user=admin_ctx.user,
        workspace=admin_ctx.workspace,
        allowed_tools=AUDIT_LOG_TOOLS,
    )

    listed = _call(endpoint, "list_audit_log", {})
    searched = _call(
        endpoint,
        "search_audit_log",
        {
            "query": "anna",
            "from_timestamp": (NOW - timedelta(days=1)).isoformat(),
            "to_timestamp": NOW.isoformat(),
        },
    )

    assert json.loads(listed.content[0].text)["entries"][0]["id"] == entry.id
    assert json.loads(searched.content[0].text)["entries"][0]["id"] == entry.id


@pytest.mark.django_db(transaction=True)
def test_audit_log_over_mcp_tells_the_client_why_not(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(member, "BUILDER")]
    )
    endpoint = enterprise_data_fixture.create_mcp_endpoint(
        user=member, workspace=workspace, allowed_tools=AUDIT_LOG_TOOLS
    )

    result = _call(endpoint, "list_audit_log", {})

    assert result.isError
    assert result.content[0].text == (
        "You don't have permission to do this in this workspace."
    )


@pytest.mark.django_db(transaction=True)
def test_audit_log_over_mcp_tells_the_client_about_the_licence(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    endpoint = enterprise_data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=AUDIT_LOG_TOOLS
    )

    result = _call(endpoint, "list_audit_log", {})

    assert result.isError
    assert result.content[0].text == (
        "The related user does not have access to these features."
    )


@pytest.mark.django_db
def test_kuma_list_audit_log_returns_entries(admin_ctx):
    entry = _entry(admin_ctx.workspace, admin_ctx.user)

    result = kuma_list_audit_log(
        make_test_ctx(admin_ctx.user, admin_ctx.workspace), thought="who did what"
    )

    assert [found["id"] for found in result["entries"]] == [entry.id]


@pytest.mark.parametrize("mode", list(AgentMode))
@pytest.mark.parametrize("name", AUDIT_LOG_TOOLS)
def test_kuma_audit_log_tools_are_active_in_every_mode(mode, name):
    assert is_tool_active(name, mode)


@pytest.mark.django_db
def test_list_audit_log_rejects_reversed_range(admin_ctx):
    # An empty page would read as nothing having happened in that period.
    with pytest.raises(DjangoValidationError):
        list_audit_log(
            admin_ctx, from_timestamp=NOW, to_timestamp=NOW - timedelta(days=1)
        )


@pytest.mark.django_db
def test_audit_log_reads_entries_with_an_unknown_timezone(admin_ctx):
    # Kuma takes the timezone from what the browser reports, without checking it.
    _entry(admin_ctx.workspace, admin_ctx.user)
    admin_ctx.timezone = "Etc/Unknown"

    assert len(list_audit_log(admin_ctx)["entries"]) == 1


@pytest.mark.django_db
def test_search_audit_log_over_mcp_refuses_a_blank_query(
    admin_ctx, enterprise_data_fixture
):
    # Two spaces would run as a search and a blank result proves nothing.
    endpoint = enterprise_data_fixture.create_mcp_endpoint(
        user=admin_ctx.user,
        workspace=admin_ctx.workspace,
        allowed_tools=AUDIT_LOG_TOOLS,
    )

    result = _call(
        endpoint,
        "search_audit_log",
        {
            "query": "  ",
            "from_timestamp": (NOW - timedelta(days=1)).isoformat(),
            "to_timestamp": NOW.isoformat(),
        },
    )

    assert result.isError
