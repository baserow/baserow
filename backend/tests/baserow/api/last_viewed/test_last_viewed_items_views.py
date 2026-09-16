from datetime import datetime, timezone

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)

from baserow.core.last_viewed.models import UserLastViewedItem


def _record(user, item_type, item, application, workspace, when):
    return UserLastViewedItem.objects.create(
        user=user,
        item_type=item_type,
        item_id=item.id,
        application=application,
        workspace=workspace,
        last_viewed=datetime.fromisoformat(when).replace(tzinfo=timezone.utc),
    )


@pytest.mark.django_db
def test_list_last_viewed_items_requires_authentication(api_client):
    response = api_client.get(reverse("api:last_viewed:items"))

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_last_viewed_items_returns_every_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, name="Acme")
    database = data_fixture.create_database_application(workspace=workspace, name="CRM")
    table = data_fixture.create_database_table(database=database, name="Customers")
    view = data_fixture.create_gallery_view(table=table, name="Cards")
    builder = data_fixture.create_builder_application(workspace=workspace, name="Site")
    page = data_fixture.create_builder_page(builder=builder, name="Home")
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="KPIs"
    )
    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Bots"
    )
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="Slack"
    )
    _record(user, "database_view", view, database, workspace, "2026-01-04 10:00")
    _record(user, "builder_page", page, builder, workspace, "2026-01-03 10:00")
    _record(user, "dashboard", dashboard, dashboard, workspace, "2026-01-02 10:00")
    _record(
        user, "automation_workflow", workflow, automation, workspace, "2026-01-01 10:00"
    )

    response = api_client.get(
        reverse("api:last_viewed:items"), HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "has_more": False,
        "results": [
            {
                "type": "database_view",
                "sub_type": "gallery",
                "last_viewed": "2026-01-04T10:00:00Z",
                "application": {"id": database.id, "name": "CRM", "type": "database"},
                "workspace": {"id": workspace.id, "name": "Acme"},
                "item": {
                    "id": view.id,
                    "name": "Cards",
                    "table": {"id": table.id, "name": "Customers"},
                },
            },
            {
                "type": "builder_page",
                "sub_type": None,
                "last_viewed": "2026-01-03T10:00:00Z",
                "application": {"id": builder.id, "name": "Site", "type": "builder"},
                "workspace": {"id": workspace.id, "name": "Acme"},
                "item": {"id": page.id, "name": "Home"},
            },
            {
                "type": "dashboard",
                "sub_type": None,
                "last_viewed": "2026-01-02T10:00:00Z",
                "application": {
                    "id": dashboard.id,
                    "name": "KPIs",
                    "type": "dashboard",
                },
                "workspace": {"id": workspace.id, "name": "Acme"},
                "item": {"id": dashboard.id, "name": "KPIs"},
            },
            {
                "type": "automation_workflow",
                "sub_type": None,
                "last_viewed": "2026-01-01T10:00:00Z",
                "application": {
                    "id": automation.id,
                    "name": "Bots",
                    "type": "automation",
                },
                "workspace": {"id": workspace.id, "name": "Acme"},
                "item": {"id": workflow.id, "name": "Slack"},
            },
        ],
    }


@pytest.mark.django_db
def test_list_last_viewed_items_pagination_and_filters(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    table = data_fixture.create_database_table(database=database)
    grid = data_fixture.create_grid_view(table=table)
    form = data_fixture.create_form_view(table=table)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace_2)
    _record(user, "database_view", grid, database, workspace_1, "2026-01-03 10:00")
    _record(user, "database_view", form, database, workspace_1, "2026-01-02 10:00")
    _record(user, "dashboard", dashboard, dashboard, workspace_2, "2026-01-01 10:00")
    url = reverse("api:last_viewed:items")

    def get(**params):
        response = api_client.get(url, params, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        data = response.json()
        return [
            (result["type"], result["item"]["id"]) for result in data["results"]
        ], data["has_more"]

    assert get(limit=2) == (
        [("database_view", grid.id), ("database_view", form.id)],
        True,
    )
    assert get(limit=2, offset=2) == ([("dashboard", dashboard.id)], False)
    assert get(workspace_ids=str(workspace_2.id)) == (
        [("dashboard", dashboard.id)],
        False,
    )
    assert get(types="database_view:form") == ([("database_view", form.id)], False)
    assert get(types="database_view:form,dashboard") == (
        [("database_view", form.id), ("dashboard", dashboard.id)],
        False,
    )
    # Mentioning the whole type wins over one of its sub types.
    assert get(types="database_view:form,database_view") == (
        [("database_view", grid.id), ("database_view", form.id)],
        False,
    )


@pytest.mark.django_db
def test_list_last_viewed_items_validates_query_parameters(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    url = reverse("api:last_viewed:items")

    for params in [
        {"limit": 101},
        {"limit": 0},
        {"offset": -1},
        {"offset": 401},
        {"workspace_ids": "1,a"},
        {"types": "unknown"},
        {"types": "database_view:unknown"},
        {"types": "builder_page:grid"},
    ]:
        response = api_client.get(url, params, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_400_BAD_REQUEST, params
        assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
