from unittest.mock import patch

from django.conf import settings
from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK


@pytest.fixture
def scheduled_views(django_capture_on_commit_callbacks):
    """
    Yields the list of (item_type, item_id) scheduled by requests made inside the
    fixture, with the real task never enqueued.
    """

    scheduled = []

    def record(args, countdown):
        assert countdown == settings.BASEROW_LAST_VIEWED_DEBOUNCE_SECONDS
        scheduled.append(args[1:])

    with patch(
        "baserow.core.last_viewed.tasks.mark_item_viewed.apply_async",
        side_effect=record,
    ):
        with django_capture_on_commit_callbacks(execute=True):
            yield scheduled


@pytest.mark.django_db(transaction=True)
def test_grid_view_rows_endpoint_schedules_last_viewed(
    api_client, data_fixture, scheduled_views
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(table=table)

    response = api_client.get(
        reverse("api:database:views:grid:list", kwargs={"view_id": view.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert scheduled_views == [("database_view", view.id)]


@pytest.mark.django_db(transaction=True)
def test_field_options_endpoint_schedules_last_viewed_only_for_form_views(
    api_client, data_fixture, scheduled_views
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    form_view = data_fixture.create_form_view(table=table)

    response = api_client.get(
        reverse("api:database:views:field_options", kwargs={"view_id": grid_view.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert scheduled_views == []

    response = api_client.get(
        reverse("api:database:views:field_options", kwargs={"view_id": form_view.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert scheduled_views == [("database_view", form_view.id)]


@pytest.mark.django_db(transaction=True)
def test_builder_elements_endpoint_schedules_last_viewed_except_shared_page(
    api_client, data_fixture, scheduled_views
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    shared_page = data_fixture.create_builder_page(builder=builder, shared=True)

    response = api_client.get(
        reverse("api:builder:element:list", kwargs={"page_id": shared_page.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert scheduled_views == []

    response = api_client.get(
        reverse("api:builder:element:list", kwargs={"page_id": page.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert scheduled_views == [("builder_page", page.id)]


@pytest.mark.django_db(transaction=True)
def test_dashboard_widgets_endpoint_schedules_last_viewed(
    api_client, data_fixture, scheduled_views
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    response = api_client.get(
        reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert scheduled_views == [("dashboard", dashboard.id)]


@pytest.mark.django_db(transaction=True)
def test_automation_nodes_endpoint_schedules_last_viewed(
    api_client, data_fixture, scheduled_views
):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

    response = api_client.get(
        reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert scheduled_views == [("automation_workflow", workflow.id)]
