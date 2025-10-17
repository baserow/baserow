from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.rows.handler import RowHandler
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
def test_get_dashboard_data_sources(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source1 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 1"
        )
    )
    data_source2 = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, name="Name 2"
    )

    url = reverse(
        "api:dashboard:data_sources:list", kwargs={"dashboard_id": dashboard.id}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json[0] == {
        "aggregation_type": "",
        "field_id": None,
        "context_data": {},
        "context_data_schema": None,
        "dashboard_id": dashboard.id,
        "filter_type": "AND",
        "filters": [],
        "id": data_source1.id,
        "integration_id": AnyInt(),
        "name": "Name 1",
        "order": "1.00000000000000000000",
        "schema": None,
        "search_query": {"formula": "", "mode": "simple", "version": "0.1"},
        "table_id": None,
        "type": "local_baserow_aggregate_rows",
        "view_id": None,
        "sample_data": None,
    }
    assert response_json[1] == {
        "context_data": None,
        "context_data_schema": None,
        "dashboard_id": dashboard.id,
        "default_result_count": 20,
        "filter_type": "AND",
        "filters": [],
        "sortings": [],
        "id": data_source2.id,
        "integration_id": AnyInt(),
        "name": "Name 2",
        "order": "2.00000000000000000000",
        "schema": None,
        "search_query": {"formula": "", "mode": "simple", "version": "0.1"},
        "table_id": None,
        "type": "local_baserow_list_rows",
        "view_id": None,
        "sample_data": None,
    }


@pytest.mark.django_db
def test_get_dashboard_data_sources_dashboard_doesnt_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:dashboard:data_sources:list", kwargs={"dashboard_id": 0})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_get_dashboard_data_sources_unauthorized(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    url = reverse(
        "api:dashboard:data_sources:list", kwargs={"dashboard_id": dashboard.id}
    )
    response = api_client.get(
        url,
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_get_dashboard_data_sources_permission_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application()
    data_source1 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 1"
        )
    )
    url = reverse(
        "api:dashboard:data_sources:list", kwargs={"dashboard_id": dashboard.id}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_update_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user, table=table)
    data_source1 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard
        )
    )
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source1.id}
    )

    response = api_client.patch(
        url,
        {
            "table_id": table.id,
            "view_id": view.id,
            "name": "name test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["view_id"] == view.id
    assert response.json()["table_id"] == table.id
    assert response.json()["name"] == "name test"


@pytest.mark.django_db
def test_update_data_source_bad_request(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source1 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard
        )
    )

    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source1.id}
    )
    response = api_client.patch(
        url,
        {"table_id": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_update_data_source_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:dashboard:data_sources:item", kwargs={"data_source_id": 0})
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_data_source_unauthorized(api_client, data_fixture):
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1"
        )
    )
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.patch(
        url,
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_update_data_source_permission_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1"
        )
    )
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_update_data_source_change_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard
        )
    )
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.patch(
        url,
        {"type": "local_baserow_list_rows"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    assert response.json()["error"] == "ERROR_SERVICE_CONFIGURATION_NOT_ALLOWED"


@pytest.mark.django_db
def test_update_data_source_service_type_doesnt_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard
        )
    )
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.patch(
        url,
        {"type": "xxx"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_INVALID_TYPE"


@pytest.mark.django_db
def test_update_data_source_service_type_none(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard
        )
    )
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.patch(
        url,
        {"type": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_INVALID_TYPE"


@pytest.mark.django_db
def test_update_data_source_integration_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard
        )
    )
    new_integration = data_fixture.create_local_baserow_integration()
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.patch(
        url,
        {"integration_id": new_integration.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_CONFIGURATION_NOT_ALLOWED"


@pytest.mark.django_db
def test_update_data_source_with_service_type_for_different_dispatch_type(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard
        )
    )

    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source.id}
    )

    response = api_client.patch(
        url,
        {"type": "local_baserow_upsert_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"]
        == "ERROR_DASHBOARD_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE"
    )


@pytest.mark.django_db
def test_dispatch_dashboard_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        [
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 20},
            {f"field_{field.id}": 30},
        ],
    )
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        integration=integration, table=table, field=field, aggregation_type="sum"
    )
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1", user=user, dashboard=dashboard, service=service
        )
    )
    url = reverse(
        "api:dashboard:data_sources:dispatch", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {"result": 60}


@pytest.mark.django_db
def test_dispatch_dashboard_data_source_data_source_doesnt_exist(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:dashboard:data_sources:dispatch", kwargs={"data_source_id": 0})
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_dispatch_dashboard_data_source_unauthorized(api_client, data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 1"
        )
    )
    url = reverse(
        "api:dashboard:data_sources:dispatch", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.post(
        url,
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_dispatch_dashboard_data_source_permission_denied(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Name 1"
        )
    )
    url = reverse(
        "api:dashboard:data_sources:dispatch", kwargs={"data_source_id": data_source.id}
    )
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_dispatch_data_source_improperly_configured(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "2"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    dashboard = data_fixture.create_dashboard_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=dashboard
    )
    data_source_missing_field = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            user=user,
            dashboard=dashboard,
            integration=integration,
            view=view,
            table=table,
        )
    )
    url = reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": data_source_missing_field.id},
    )

    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED"
    )
    assert (
        response.json()["detail"] == "The data_source configuration is incorrect: "
        "The field property is missing."
    )

    data_source_missing_integration = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            user=user,
            dashboard=dashboard,
            integration=None,
        )
    )

    url = reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": data_source_missing_integration.id},
    )

    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    assert (
        response.json()["error"] == "ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED"
    )
    assert (
        response.json()["detail"] == "The data_source configuration is incorrect: "
        "No integration selected"
    )
