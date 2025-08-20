from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from baserow_premium.views.models import (
    CalendarViewFieldOptions,
    KanbanViewFieldOptions,
    TimelineViewFieldOptions,
)
from rest_framework.status import HTTP_200_OK, HTTP_402_PAYMENT_REQUIRED

from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
def test_list_views_ownership_type(
    api_client, data_fixture, alternative_per_workspace_license_service
):
    """
    In premium, both collaborative and personal views are returned.
    """

    workspace = data_fixture.create_workspace(name="Group 1")
    database = data_fixture.create_database_application(workspace=workspace)
    user, token = data_fixture.create_user_and_token(
        workspace=workspace,
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )
    user2, token2 = data_fixture.create_user_and_token(
        workspace=workspace,
        email="test2@test.nl",
        password="password",
        first_name="Test2",
    )
    table_1 = data_fixture.create_database_table(user=user, database=database)
    view_1 = data_fixture.create_grid_view(
        table=table_1, order=1, ownership_type="collaborative", owned_by=user
    )
    view_2 = data_fixture.create_grid_view(
        table=table_1, order=3, ownership_type="personal", owned_by=user
    )
    # view belongs to another user
    view_3 = data_fixture.create_grid_view(
        table=table_1, order=3, ownership_type="personal", owned_by=user2
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table_1.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["id"] == view_1.id
    assert response_json[0]["ownership_type"] == "collaborative"
    assert response_json[1]["id"] == view_2.id
    assert response_json[1]["ownership_type"] == "personal"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_can_limit_linked_items_in_premium_views(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table_a, table_b, link_a_to_b = premium_data_fixture.create_two_linked_tables(
        user=user
    )
    start_date_field = premium_data_fixture.create_date_field(table=table_a)
    stop_date_field = premium_data_fixture.create_date_field(table=table_a)

    rows_b = RowHandler().force_create_rows(user, table_b, [{}] * 3).created_rows
    RowHandler().force_create_rows(
        user,
        table_a,
        [
            {
                start_date_field.db_column: "2023-01-01",
                stop_date_field.db_column: "2023-01-02",
                link_a_to_b.db_column: [row.id for row in rows_b],
            }
        ],
    )

    kanban = premium_data_fixture.create_kanban_view(user=user, table=table_a)
    kanban_url = reverse(
        "api:database:views:kanban:list", kwargs={"view_id": kanban.id}
    )
    resp = api_client.get(kanban_url, HTTP_AUTHORIZATION=f"JWT {token}", format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["rows"]["null"]["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(
        f"{kanban_url}?limit_linked_items=2",
        HTTP_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["rows"]["null"]["results"][0][link_a_to_b.db_column]) == 2

    calendar = premium_data_fixture.create_calendar_view(
        user=user,
        table=table_a,
        date_field=start_date_field,
        create_options=True,
    )
    calendar_url = (
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + "?from_timestamp=2023-01-01&to_timestamp=2023-01-31"
    )
    resp = api_client.get(
        calendar_url, HTTP_AUTHORIZATION=f"JWT {token}", format="json"
    )
    assert resp.status_code == HTTP_200_OK
    assert (
        len(resp.json()["rows"]["2023-01-01"]["results"][0][link_a_to_b.db_column]) == 3
    )

    # Limit the linked items to 2
    resp = api_client.get(
        f"{calendar_url}&limit_linked_items=2",
        HTTP_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert resp.status_code == HTTP_200_OK
    assert (
        len(resp.json()["rows"]["2023-01-01"]["results"][0][link_a_to_b.db_column]) == 2
    )

    timeline = premium_data_fixture.create_timeline_view(
        user=user,
        table=table_a,
        start_date_field=start_date_field,
        end_date_field=stop_date_field,
        create_options=True,
    )
    timeline_url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline.id}
    )
    resp = api_client.get(
        timeline_url, HTTP_AUTHORIZATION=f"JWT {token}", format="json"
    )
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(
        f"{timeline_url}?limit_linked_items=2",
        HTTP_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_can_limit_linked_items_in_premium_public_views(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table_a, table_b, link_a_to_b = premium_data_fixture.create_two_linked_tables(
        user=user
    )
    start_date_field = premium_data_fixture.create_date_field(table=table_a)
    stop_date_field = premium_data_fixture.create_date_field(table=table_a)

    rows_b = RowHandler().force_create_rows(user, table_b, [{}] * 3).created_rows
    RowHandler().force_create_rows(
        user,
        table_a,
        [
            {
                start_date_field.db_column: "2023-01-01",
                stop_date_field.db_column: "2023-01-02",
                link_a_to_b.db_column: [row.id for row in rows_b],
            }
        ],
    )

    kanban = premium_data_fixture.create_kanban_view(
        user=user, table=table_a, public=True
    )
    KanbanViewFieldOptions.objects.update(hidden=False)
    kanban_url = reverse(
        "api:database:views:kanban:public_rows", kwargs={"slug": kanban.slug}
    )
    resp = api_client.get(kanban_url, format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["rows"]["null"]["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(f"{kanban_url}?limit_linked_items=2", format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["rows"]["null"]["results"][0][link_a_to_b.db_column]) == 2

    calendar = premium_data_fixture.create_calendar_view(
        user=user,
        table=table_a,
        date_field=start_date_field,
        create_options=True,
        public=True,
    )
    CalendarViewFieldOptions.objects.update(hidden=False)
    calendar_url = (
        reverse(
            "api:database:views:calendar:public_rows", kwargs={"slug": calendar.slug}
        )
        + "?from_timestamp=2023-01-01&to_timestamp=2023-01-31"
    )
    resp = api_client.get(calendar_url, format="json")
    assert resp.status_code == HTTP_200_OK
    assert (
        len(resp.json()["rows"]["2023-01-01"]["results"][0][link_a_to_b.db_column]) == 3
    )

    # Limit the linked items to 2
    resp = api_client.get(f"{calendar_url}&limit_linked_items=2", format="json")
    assert resp.status_code == HTTP_200_OK
    assert (
        len(resp.json()["rows"]["2023-01-01"]["results"][0][link_a_to_b.db_column]) == 2
    )

    timeline = premium_data_fixture.create_timeline_view(
        user=user,
        table=table_a,
        start_date_field=start_date_field,
        end_date_field=stop_date_field,
        create_options=True,
        public=True,
    )
    TimelineViewFieldOptions.objects.update(hidden=False)
    timeline_url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline.slug}
    )
    resp = api_client.get(timeline_url, format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 3

    # Limit the linked items to 2
    resp = api_client.get(f"{timeline_url}?limit_linked_items=2", format="json")
    assert resp.status_code == HTTP_200_OK
    assert len(resp.json()["results"][0][link_a_to_b.db_column]) == 2


@pytest.mark.django_db
def test_create_personal_grid_view_without_license(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "personal",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_personal_grid_view_with_license(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "personal",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["ownership_type"] == "personal"
