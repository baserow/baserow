from django.test.utils import override_settings

import pytest
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK

from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_chart_widget(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()
    dashboard = enterprise_data_fixture.create_dashboard_application(user=user)

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "title": "Title",
            "description": "Description",
            "type": "chart",
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
        "type": "chart",
    }


@pytest.mark.django_db
def test_get_widgets_with_chart_widget(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    dashboard = enterprise_data_fixture.create_dashboard_application(user=user)
    data_source = enterprise_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, name="Name 1"
    )
    widget = enterprise_data_fixture.create_chart_widget(
        dashboard=dashboard,
        data_source=data_source,
        title="Widget 1",
        description="Description 1",
    )

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
            "type": "chart",
        },
    ]
