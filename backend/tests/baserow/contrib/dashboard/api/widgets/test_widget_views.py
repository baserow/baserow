from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.dashboard.widgets.models import Widget
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
def test_get_widgets(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    dashboard_2 = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 1"
        )
    )
    data_source_2 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 2"
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard,
        data_source=data_source,
        title="Widget 1",
        description="Description 1",
    )
    widget_2 = data_fixture.create_summary_widget(
        dashboard=dashboard,
        data_source=data_source_2,
        title="Widget 2",
        description="Description 2",
    )
    widget_3 = data_fixture.create_summary_widget(dashboard=dashboard_2)

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response_json == [
        {
            "id": widget.id,
            "title": "Widget 1",
            "description": "Description 1",
            "dashboard_id": dashboard.id,
            "data_source_id": data_source.id,
            "order": "1.00000000000000000000",
            "type": "summary",
        },
        {
            "id": widget_2.id,
            "title": "Widget 2",
            "description": "Description 2",
            "dashboard_id": dashboard.id,
            "data_source_id": data_source_2.id,
            "order": "1.00000000000000000000",
            "type": "summary",
        },
    ]


@pytest.mark.django_db
def test_get_widgets_dashboard_doesnt_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": 0})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_widgets_permissions_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application()

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_widget(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "title": "Title",
            "description": "Description",
            "type": "summary",
            # dashboard and data source id will be ignored
            "dashboard_id": 123,
            "data_source_id": 123,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "id": AnyInt(),
        "title": "Title",
        "description": "Description",
        "data_source_id": AnyInt(),
        "dashboard_id": dashboard.id,
        "order": "1.00000000000000000000",
        "type": "summary",
    }


@pytest.mark.django_db
def test_create_widget_wrong_widget_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "title": "Title",
            "type": "xxx",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_WIDGET_TYPE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_widget_permission_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application()

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "title": "Title",
            "type": "summary",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_widget_dashboard_doesnt_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": 0})
    response = api_client.post(
        url,
        {
            "title": "Title",
            "type": "summary",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_widget_empty_title(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "title": "",
            "type": "summary",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": {
            "title": [
                {
                    "code": "blank",
                    "error": "This field may not be blank.",
                },
            ],
        },
        "error": "ERROR_REQUEST_BODY_VALIDATION",
    }

    response = api_client.post(
        url,
        {
            "title": None,
            "type": "summary",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": {
            "title": [
                {
                    "code": "null",
                    "error": "This field may not be null.",
                },
            ],
        },
        "error": "ERROR_REQUEST_BODY_VALIDATION",
    }


@pytest.mark.django_db
def test_update_widget(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    dashboard_2 = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 1"
        )
    )
    data_source_2 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 2"
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, data_source=data_source
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.patch(
        url,
        {
            "title": "Changed title",
            "description": "Changed desc",
            # dashboard, data source and type shouldnt be changed
            "dashboard": dashboard_2.id,
            "data_source_id": data_source_2.id,
            "type": "xxx",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "id": widget.id,
        "title": "Changed title",
        "description": "Changed desc",
        "dashboard_id": widget.dashboard.id,
        "data_source_id": data_source.id,
        "order": "1.00000000000000000000",
        "type": "summary",
    }
    widget.refresh_from_db()
    assert widget.dashboard.id == dashboard.id
    assert widget.data_source.id == data_source.id


@pytest.mark.django_db
def test_update_widget_permissions_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 1"
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, data_source=data_source
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.patch(
        url,
        {
            "title": "Changed title",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_update_widget_doesnt_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": 0})
    response = api_client.patch(
        url,
        {
            "title": "Changed title",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WIDGET_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_widget_empty_title(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 1"
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, data_source=data_source
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.patch(
        url,
        {
            "title": "",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": {
            "title": [
                {
                    "code": "blank",
                    "error": "This field may not be blank.",
                },
            ],
        },
        "error": "ERROR_REQUEST_BODY_VALIDATION",
    }

    response = api_client.patch(
        url,
        {
            "title": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": {
            "title": [
                {
                    "code": "null",
                    "error": "This field may not be null.",
                },
            ],
        },
        "error": "ERROR_REQUEST_BODY_VALIDATION",
    }


@pytest.mark.django_db
def test_delete_widget(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 1"
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, data_source=data_source
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert Widget.objects.count() == 0


@pytest.mark.django_db
def test_delete_widget_permissions_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 1"
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, data_source=data_source
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"
    assert Widget.objects.count() == 1


@pytest.mark.django_db
def test_delete_widget_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": 0})

    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WIDGET_DOES_NOT_EXIST"
