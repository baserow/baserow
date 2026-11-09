"""Tests for the application tools shared by MCP and Kuma."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from pydantic import ValidationError

from baserow.contrib.automation.tools.workflows import get_automation_in_workspace
from baserow.contrib.dashboard.tools.dashboards import get_dashboard_in_workspace
from baserow.contrib.database.tools.tables import get_database
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    InstanceTypeDoesNotExist,
    PermissionException,
)
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.service import CoreService
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import create_application, list_applications


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


@pytest.fixture
def workspace_apps(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    apps = [
        data_fixture.create_database_application(workspace=workspace, name="Sales"),
        data_fixture.create_builder_application(workspace=workspace, name="Portal"),
        data_fixture.create_automation_application(workspace=workspace, name="Sync"),
        data_fixture.create_dashboard_application(workspace=workspace, name="KPIs"),
    ]
    # Another workspace of the same user must stay hidden.
    data_fixture.create_database_application(user=user, name="Elsewhere")
    return ToolContext(user=user, workspace=workspace), apps


@pytest.mark.django_db
def test_list_applications_lists_every_type(workspace_apps):
    ctx, (sales, portal, sync, kpis) = workspace_apps

    result = list_applications(ctx)

    assert result == {
        "applications": [
            {"id": sales.id, "name": "Sales", "type": "database"},
            {"id": portal.id, "name": "Portal", "type": "builder"},
            {"id": sync.id, "name": "Sync", "type": "automation"},
            {"id": kpis.id, "name": "KPIs", "type": "dashboard"},
        ],
        "total": 4,
        "page": 1,
        "has_more": False,
    }


@pytest.mark.django_db
def test_list_applications_filters_by_type(workspace_apps):
    ctx, (sales, portal, *_) = workspace_apps

    result = list_applications(ctx, types=["builder", "database"])

    assert [app["id"] for app in result["applications"]] == [sales.id, portal.id]
    assert result["total"] == 2


@pytest.mark.django_db
def test_list_applications_rejects_an_unknown_type(workspace_apps):
    ctx, _ = workspace_apps

    with pytest.raises(InstanceTypeDoesNotExist):
        list_applications(ctx, types=["spreadsheet"])


@pytest.mark.django_db
def test_list_applications_pages(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    databases = [
        data_fixture.create_database_application(workspace=workspace, order=i)
        for i in range(5)
    ]
    ctx = ToolContext(user=user, workspace=workspace)

    first = list_applications(ctx, page=1, size=2)
    last = list_applications(ctx, page=3, size=2)

    assert [app["id"] for app in first["applications"]] == [
        databases[0].id,
        databases[1].id,
    ]
    assert (first["total"], first["has_more"]) == (5, True)
    assert [app["id"] for app in last["applications"]] == [databases[4].id]
    assert (last["page"], last["has_more"]) == (3, False)


@pytest.mark.django_db
def test_list_applications_over_mcp_lists_only_databases(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["list_applications"])
    database = data_fixture.create_database_application(
        workspace=endpoint.workspace, name="Sales"
    )
    data_fixture.create_builder_application(workspace=endpoint.workspace)
    data_fixture.create_automation_application(workspace=endpoint.workspace)

    result = _call(endpoint, "list_applications", {})
    too_big = _call(endpoint, "list_applications", {"size": 101})
    by_type = _call(endpoint, "list_applications", {"types": ["builder"]})

    assert json.loads(result.content[0].text) == {
        "applications": [{"id": database.id, "name": "Sales", "type": "database"}],
        "total": 1,
        "page": 1,
        "has_more": False,
    }
    assert too_big.isError is True
    assert too_big.content[0].text.startswith("Invalid arguments. size:")
    assert by_type.isError is True
    assert by_type.content[0].text.startswith("Invalid arguments. types:")


@pytest.mark.django_db
def test_list_databases_still_answers_with_its_old_shape(data_fixture):
    # An endpoint without an allow-list keeps the legacy tools, list_databases
    # among them, and doesn't get list_applications.
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(
        workspace=endpoint.workspace, name="Sales"
    )
    data_fixture.create_builder_application(workspace=endpoint.workspace)

    result = _call(endpoint, "list_databases", {})
    refused = _call(endpoint, "list_applications", {})

    assert json.loads(result.content[0].text) == [
        {"id": database.id, "name": "Sales", "order": database.order}
    ]
    assert refused.isError is True
    assert refused.content[0].text == "Tool 'list_applications' not found."


@pytest.mark.django_db
def test_create_application_trims_the_name_and_refuses_a_blank_one(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = ToolContext(user=user, workspace=workspace)

    created = create_application(ctx, "database", "  Sales  ")

    assert created.name == "Sales"
    with pytest.raises(ValidationError):
        create_application(ctx, "database", "   ")


@pytest.mark.django_db
def test_update_tools_report_a_hidden_application_as_not_found(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = ToolContext(user=user, workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    def deny(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(CoreService, "get_application", deny)

    for getter in (
        get_database,
        get_automation_in_workspace,
        get_dashboard_in_workspace,
    ):
        with pytest.raises(ApplicationDoesNotExist):
            getter(ctx, database.id)
