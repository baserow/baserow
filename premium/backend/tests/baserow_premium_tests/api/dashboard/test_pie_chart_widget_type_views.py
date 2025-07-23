from django.test.utils import override_settings

import pytest
from baserow_premium.api.fields.exceptions import HTTP_400_BAD_REQUEST
from baserow_premium.dashboard.widgets.models import PieChartSeriesConfig
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationSeries,
)
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK

from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_pie_chart_widget(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    dashboard = premium_data_fixture.create_dashboard_application(user=user)

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "title": "Title",
            "description": "Description",
            "type": "pie_chart",
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
        "type": "pie_chart",
        "series_config": [],
        "default_series_chart_type": "PIE",
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_pie_chart_widget_default_pie(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    dashboard = premium_data_fixture.create_dashboard_application(user=user)

    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "title": "Title",
            "description": "Description",
            "type": "pie_chart",
            "default_series_chart_type": "PIE",
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
        "type": "pie_chart",
        "series_config": [],
        "default_series_chart_type": "PIE",
    }


@pytest.mark.django_db
def test_get_widgets_with_pie_chart_widget(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    workspace = premium_data_fixture.create_workspace(user=user)
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    data_source = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, name="Name 1"
    )
    service = data_source.service
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_number_field(table=table)
    series_1 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="min", order=1
    )
    series_2 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="max", order=1
    )
    widget = premium_data_fixture.create_pie_chart_widget(
        dashboard=dashboard,
        data_source=data_source,
        title="Widget 1",
        description="Description 1",
    )
    PieChartSeriesConfig.objects.create(
        widget=widget, series=series_1, series_chart_type="PIE"
    )
    PieChartSeriesConfig.objects.create(
        widget=widget, series=series_2, series_chart_type="DOUGHNUT"
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
            "type": "pie_chart",
            "series_config": [
                {
                    "series_id": series_1.id,
                    "series_chart_type": "PIE",
                },
                {
                    "series_id": series_2.id,
                    "series_chart_type": "DOUGHNUT",
                },
            ],
            "default_series_chart_type": "PIE",
        },
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_pie_chart_widget_series_config(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(user=user)
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    data_source = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, name="Name 1"
    )
    service = data_source.service
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_number_field(table=table)
    series_1 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="min", order=1
    )
    series_2 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="max", order=1
    )
    widget = premium_data_fixture.create_pie_chart_widget(
        dashboard=dashboard,
        data_source=data_source,
        title="Widget 1",
        description="Description 1",
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.patch(
        url,
        {
            "series_config": [
                {
                    "series_id": series_1.id,
                    "series_chart_type": "PIE",
                },
                {
                    "series_id": series_2.id,
                    "series_chart_type": "DOUGHNUT",
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json["series_config"] == [
        {"series_chart_type": "PIE", "series_id": series_1.id},
        {"series_chart_type": "DOUGHNUT", "series_id": series_2.id},
    ]

    assert PieChartSeriesConfig.objects.filter(widget=widget).count() == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_pie_chart_widget_series_config_invalid_series_id(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    data_source = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, name="Name 1"
    )
    widget = premium_data_fixture.create_pie_chart_widget(
        dashboard=dashboard,
        data_source=data_source,
        title="Widget 1",
        description="Description 1",
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.patch(
        url,
        {
            "series_config": [
                {
                    "series_id": 0,
                    "series_chart_type": "PIE",
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json == {
        "detail": "The requested configuration is not allowed.",
        "error": "ERROR_WIDGET_IMPROPERLY_CONFIGURED",
    }


@pytest.mark.django_db
def test_update_pie_widget_preserve_chart_config(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    workspace = premium_data_fixture.create_workspace(user=user)
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    data_source = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, name="Name 1"
    )
    service = data_source.service
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_number_field(table=table)
    series_1 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="min", order=1
    )
    series_2 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="max", order=1
    )
    widget = premium_data_fixture.create_pie_chart_widget(
        dashboard=dashboard,
        data_source=data_source,
        title="Widget 1",
        description="Description 1",
    )
    PieChartSeriesConfig.objects.create(
        widget=widget, series=series_1, series_chart_type="PIE"
    )
    PieChartSeriesConfig.objects.create(
        widget=widget, series=series_2, series_chart_type="DOUGHNUT"
    )

    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    response = api_client.patch(
        url,
        {
            "title": "Title changed"
            # series_config is not modified here
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response_json == {
        "id": widget.id,
        "title": "Title changed",
        "description": "Description 1",
        "dashboard_id": dashboard.id,
        "data_source_id": data_source.id,
        "order": "1.00000000000000000000",
        "type": "pie_chart",
        "series_config": [
            {
                "series_id": series_1.id,
                "series_chart_type": "PIE",
            },
            {
                "series_id": series_2.id,
                "series_chart_type": "DOUGHNUT",
            },
        ],
        "default_series_chart_type": "PIE",
    }
