from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK
from tqdm import tqdm

from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService


@pytest.mark.django_db
def test_create_local_baserow_integration_with_user(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("local_baserow")

    integration = IntegrationService().create_integration(
        user, integration_type, application=application
    )

    assert integration.authorized_user.id == user.id


@pytest.mark.django_db
def test_get_local_baserow_databases_no_databases(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(authorized_user=user)

    databases = LocalBaserowIntegrationType.get_local_baserow_databases(integration)

    assert len(databases) == 0


@pytest.mark.django_db
def test_get_local_baserow_databases(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=builder
    )
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, order=1
    )
    database_2 = data_fixture.create_database_application(
        user=user, workspace=workspace, order=2
    )
    table = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database_2, order=1)
    table_3 = data_fixture.create_database_table(database=database_2, order=2)

    # Create some unrelated database and tables, that should not be included in the
    # result.
    database_tmp_2 = data_fixture.create_database_application(user=user)
    database_tmp_3 = data_fixture.create_database_application()
    data_fixture.create_database_table(database=database_tmp_2)
    data_fixture.create_database_table(database=database_tmp_3)
    data_fixture.create_database_table()

    databases = LocalBaserowIntegrationType.get_local_baserow_databases(integration)

    assert len(databases) == 2

    assert databases[0].id == database.id
    assert len(databases[0].tables) == 1
    assert databases[0].tables[0].id == table.id

    assert databases[1].id == database_2.id
    assert len(databases[1].tables) == 2
    assert databases[1].tables[0].id == table_2.id
    assert databases[1].tables[1].id == table_3.id


@pytest.mark.django_db
def test_get_local_baserow_databases_number_of_queries(
    data_fixture, django_assert_num_queries, bypass_check_permissions
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=builder
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    with CaptureQueriesContext(connection) as queries:
        LocalBaserowIntegrationType.get_local_baserow_databases(integration)

    data_fixture.create_database_table(database=database)
    database_2 = data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    data_fixture.create_database_table(database=database_2)

    with CaptureQueriesContext(connection) as queries_2:
        LocalBaserowIntegrationType.get_local_baserow_databases(integration)

    assert len(queries.captured_queries) == len(queries_2.captured_queries)


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
# pytest -k "test_get_local_baserow_databases_performance" -s --run-disabled-in-ci
# 4.500s for 30 x 999 x 100 table/views/fields on Intel(R) Core(TM) i9-9900K
# CPU @ 3.60GHz - # 7200 bogomips
def test_get_local_baserow_databases_performance(data_fixture, api_client, profiler):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=builder
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)

    table_amount = 30
    views_per_table_amount = 999
    field_amount_per_table = 100

    for i in tqdm(range(table_amount), desc="Tables creation"):
        table = data_fixture.create_database_table(database=database, name=i)

        for j in range(int(views_per_table_amount / 3)):
            data_fixture.create_grid_view(table=table, name=j)

        for j in range(int(views_per_table_amount / 3)):
            data_fixture.create_gallery_view(table=table, name=j)

        for j in range(int(views_per_table_amount / 3)):
            data_fixture.create_form_view(table=table, name=j)

        for j in range(field_amount_per_table):
            data_fixture.create_text_field(table=table)

    print("------TYPE FUNCTION-------")
    with profiler(html_report_name="get_local_baserow_databases_function"):
        LocalBaserowIntegrationType.get_local_baserow_databases(integration)

    print("------SERIALIZATION-------")
    url = reverse("api:integrations:list", kwargs={"application_id": builder.id})
    with profiler(html_report_name="get_local_baserow_databases_serialization"):
        api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )


@pytest.mark.django_db
def test_get_integrations_serializer(
    api_client, data_fixture, bypass_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    # table = data_fixture.create_database_table(database=database)
    table, fields, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW"],
        ],
    )
    view = data_fixture.create_grid_view(table=table, order=2)
    not_sortable_view = data_fixture.create_gallery_view(table=table, order=1)
    not_filterable_and_sortable_view = data_fixture.create_form_view(
        table=table, order=3
    )
    data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:integrations:list", kwargs={"application_id": application.id})

    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1

    assert response_json[0]["context_data"] == {
        "databases": [
            {
                "id": database.id,
                "name": database.name,
                "created_on": database.created_on.isoformat(
                    timespec="microseconds"
                ).replace("+00:00", "Z"),
                "order": database.order,
                "type": "database",
                "workspace": {
                    "id": workspace.id,
                    "name": workspace.name,
                    "generative_ai_models_enabled": {},
                },
                "tables": [
                    {
                        "id": table.id,
                        "name": table.name,
                        "database_id": table.database_id,
                        "is_data_sync": table.is_data_synced_table,
                        "is_two_way_data_sync": table.is_two_way_data_synced_table,
                    }
                ],
                "views": [
                    {
                        "id": not_sortable_view.id,
                        "name": not_sortable_view.name,
                        "table_id": table.id,
                    },
                    {"id": view.id, "name": view.name, "table_id": table.id},
                ],
            },
        ]
    }

    # If we add more views or table we should have the same amount of query
    database_2 = data_fixture.create_database_application(workspace=workspace)
    table_2 = data_fixture.create_database_table(database=database_2)
    data_fixture.create_database_table(database=database_2)

    data_fixture.create_grid_view(table=table_2, order=2)
    data_fixture.create_gallery_view(table=table_2, order=1)
    data_fixture.create_form_view(table=table_2, order=3)

    with CaptureQueriesContext(connection) as queries_2:
        api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    for q in queries_2.captured_queries:
        print(q, "/n")

    assert len(queries.captured_queries) == len(queries_2.captured_queries)


@pytest.mark.django_db
def test_after_import(data_fixture):
    """Test the LocalBaserowIntegrationType::after_import() method."""

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("local_baserow")

    integration = IntegrationService().create_integration(
        user, integration_type, application=application
    )

    integration.authorized_user = None
    integration.save()

    assert integration.authorized_user is None

    integration.get_type().after_import(user, integration)

    integration.refresh_from_db()

    assert integration.authorized_user == user
