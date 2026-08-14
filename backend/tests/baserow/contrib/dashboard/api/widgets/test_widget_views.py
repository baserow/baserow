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
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.test_utils.helpers import AnyInt

SUMMARY_GRID_LAYOUT = {
    "default_width": 2,
    "default_height": 4,
    "min_width": 1,
    "min_height": 4,
    "max_width": 6,
    "max_height": 6,
}


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
            "grid_x": 0,
            "grid_y": 0,
            "grid_width": 6,
            "grid_height": 9,
            "grid_layout": SUMMARY_GRID_LAYOUT,
            "type": "summary",
        },
        {
            "id": widget_2.id,
            "title": "Widget 2",
            "description": "Description 2",
            "dashboard_id": dashboard.id,
            "data_source_id": data_source_2.id,
            "order": "1.00000000000000000000",
            "grid_x": 0,
            "grid_y": 0,
            "grid_width": 6,
            "grid_height": 9,
            "grid_layout": SUMMARY_GRID_LAYOUT,
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
        "grid_x": 0,
        "grid_y": 0,
        "grid_width": 2,
        "grid_height": 4,
        "grid_layout": SUMMARY_GRID_LAYOUT,
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
        "grid_x": 0,
        "grid_y": 0,
        "grid_width": 6,
        "grid_height": 9,
        "grid_layout": SUMMARY_GRID_LAYOUT,
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


@pytest.mark.django_db
def test_update_widget_layout(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    first_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="First"
    )
    second_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Second"
    )

    url = reverse("api:dashboard:widgets:layout", kwargs={"dashboard_id": dashboard.id})
    response = api_client.patch(
        url,
        {
            "widgets": [
                {
                    "id": first_widget.id,
                    "grid_x": 0,
                    "grid_y": 0,
                    "grid_width": 2,
                    "grid_height": 4,
                },
                {
                    "id": second_widget.id,
                    "grid_x": 2,
                    "grid_y": 0,
                    "grid_width": 2,
                    "grid_height": 4,
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert {
        widget["id"]: (widget["grid_x"], widget["grid_y"]) for widget in response.json()
    } == {
        first_widget.id: (0, 0),
        second_widget.id: (2, 0),
    }

    first_widget.refresh_from_db()
    second_widget.refresh_from_db()
    assert (first_widget.grid_x, first_widget.grid_y) == (0, 0)
    assert (second_widget.grid_x, second_widget.grid_y) == (2, 0)


@pytest.mark.django_db
def test_update_widget_layout_filters_response_by_widget_permissions(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    visible_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Visible"
    )
    hidden_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Hidden"
    )

    def exclude_hidden_widget(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=hidden_widget.id)

    url = reverse("api:dashboard:widgets:layout", kwargs={"dashboard_id": dashboard.id})
    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_hidden_widget
        response = api_client.patch(
            url,
            {
                "widgets": [
                    {
                        "id": visible_widget.id,
                        "grid_x": 4,
                        "grid_y": 0,
                        "grid_width": 2,
                        "grid_height": 4,
                    }
                ]
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    assert [widget["id"] for widget in response.json()] == [visible_widget.id]
    assert response.json()[0]["grid_x"] == 4
    hidden_widget.refresh_from_db()
    assert (hidden_widget.grid_x, hidden_widget.grid_y) == (2, 0)


@pytest.mark.django_db
def test_update_widget_layout_rejects_collision_with_hidden_widget(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    visible_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Visible"
    )
    hidden_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Hidden"
    )

    def exclude_hidden_widget(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=hidden_widget.id)

    url = reverse("api:dashboard:widgets:layout", kwargs={"dashboard_id": dashboard.id})
    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_hidden_widget
        response = api_client.patch(
            url,
            {
                "widgets": [
                    {
                        "id": visible_widget.id,
                        "grid_x": 2,
                        "grid_y": 0,
                        "grid_width": 2,
                        "grid_height": 4,
                    }
                ]
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_WIDGET_LAYOUT_INVALID"
    visible_widget.refresh_from_db()
    hidden_widget.refresh_from_db()
    assert (visible_widget.grid_x, visible_widget.grid_y) == (0, 0)
    assert (hidden_widget.grid_x, hidden_widget.grid_y) == (2, 0)


@pytest.mark.django_db
def test_update_widget_layout_rejects_grid_y_beyond_total_layout_height(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Widget"
    )

    url = reverse("api:dashboard:widgets:layout", kwargs={"dashboard_id": dashboard.id})
    response = api_client.patch(
        url,
        {
            "widgets": [
                {
                    "id": widget.id,
                    "grid_x": 0,
                    "grid_y": 2_147_483_648,
                    "grid_width": 2,
                    "grid_height": 4,
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_WIDGET_LAYOUT_INVALID"
    widget.refresh_from_db()
    assert widget.grid_y == 0


@pytest.mark.django_db
def test_update_widget_layout_rejects_collisions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    first_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="First"
    )
    second_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Second"
    )

    url = reverse("api:dashboard:widgets:layout", kwargs={"dashboard_id": dashboard.id})
    response = api_client.patch(
        url,
        {
            "widgets": [
                {
                    "id": first_widget.id,
                    "grid_x": 0,
                    "grid_y": 0,
                    "grid_width": 2,
                    "grid_height": 4,
                },
                {
                    "id": second_widget.id,
                    "grid_x": 0,
                    "grid_y": 0,
                    "grid_width": 2,
                    "grid_height": 4,
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_WIDGET_LAYOUT_INVALID"
