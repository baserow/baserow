from decimal import Decimal
from unittest.mock import Mock

from django.contrib.contenttypes.models import ContentType

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceSort,
)
from baserow.core.services.exceptions import ServiceImproperlyConfigured
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
)


def test_grouped_aggregate_rows_service_get_schema_name():
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    assert service_type.get_schema_name(Mock(id=123)) == "GroupedAggregation123Schema"


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_no_data(data_fixture):
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    service = ServiceHandler().create_service(service_type)

    assert service.content_type == ContentType.objects.get_for_model(
        LocalBaserowGroupedAggregateRows
    )
    assert service.table_id is None
    assert service.view_id is None
    assert service.integration_id is None
    assert service.service_aggregation_series.all().count() == 0
    assert service.service_aggregation_group_bys.all().count() == 0


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
    )

    service = ServiceHandler().create_service(service_type, **values)

    assert service.integration.id == integration.id
    assert service.table.id == table.id
    assert service.view.id == view.id
    aggregation_series = service.service_aggregation_series.all()
    assert aggregation_series.count() == 2
    assert aggregation_series[0].field_id == field.id
    assert aggregation_series[0].aggregation_type == "sum"
    assert aggregation_series[1].field_id == field_2.id
    assert aggregation_series[1].aggregation_type == "sum"
    group_bys = service.service_aggregation_group_bys.all()
    assert group_bys.count() == 1
    assert group_bys[0].field_id == field.id


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_series_field_not_in_table(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table_2)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field_2.id} is not related"
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_series_agg_type_doesnt_exist(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "avg"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The aggregation type 'avg' doesn't exist.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_series_incompatible_aggregation_type(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} is not compatible with aggregation type",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_group_by_field_not_in_table(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table_2)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field_2.id} is not related"
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_max_series_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    field_4 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
                {"field_id": field_3.id, "aggregation_type": "sum"},
                {"field_id": field_4.id, "aggregation_type": "sum"},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of series exceeds the maximum allowed length of 3.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_max_group_bys_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [
                {"field_id": field.id},
                {"field_id": field_2.id},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of group by fields exceeds the maximum allowed length of 1.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_sort_by_field_outside_of_series_group_bys(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
            "service_sorts": [
                {"field": field_2},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} cannot be used for sorting.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_sort_by_primary_field_no_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table, primary=True)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [],
            "service_sorts": [
                {"field": field_2},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} cannot be used for sorting.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_sort_by_primary_field_with_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
            "service_sorts": [
                {"field": field},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field.id} cannot be used for sorting.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_field_2 = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "sum"},
                {"field_id": table_2_field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    service = (
        ServiceHandler().update_service(service_type, service=service, **values).service
    )

    assert service.integration.id == table_2_integration.id
    assert service.table.id == table_2.id
    assert service.view.id == table_2_view.id
    aggregation_series = service.service_aggregation_series.all()
    assert aggregation_series.count() == 2
    assert aggregation_series[0].field_id == table_2_field.id
    assert aggregation_series[0].aggregation_type == "sum"
    assert aggregation_series[1].field_id == table_2_field_2.id
    assert aggregation_series[1].aggregation_type == "sum"
    group_bys = service.service_aggregation_group_bys.all()
    assert group_bys.count() == 1
    assert group_bys[0].field_id == table_2_field.id


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_series_field_not_in_table(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field.id} is not related"
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_series_agg_type_doesnt_exist(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "avg"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError,
        match=f"The aggregation type 'avg' doesn't exist.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_series_incompatible_aggregation_type(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_text_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {table_2_field.id} is not compatible with aggregation type",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_group_by_field_not_in_table(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field.id} is not related"
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_max_series_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    field_4 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
                {"field_id": field_3.id, "aggregation_type": "sum"},
                {"field_id": field_4.id, "aggregation_type": "sum"},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of series exceeds the maximum allowed length of 3.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_max_group_bys_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [
                {"field_id": field.id},
                {"field_id": field_2.id},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of group by fields exceeds the maximum allowed length of 1.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_sort_by_field_outside_of_series_group_bys(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
            "service_sorts": [
                {"field": field_2},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} cannot be used for sorting.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_sort_by_primary_field_no_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table, primary=True)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [],
            "service_sorts": [
                {"field": field_2},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} cannot be used for sorting.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_sort_by_primary_field_with_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
            "service_sorts": [
                {"field": field},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field.id} cannot be used for sorting.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_reset_after_table_change(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field, order=2, order_by="ASC"
    )

    values = service_type.prepare_values(
        {
            "table_id": table_2.id,
        },
        user,
        service,
    )

    service = (
        ServiceHandler().update_service(service_type, service=service, **values).service
    )

    # integration is kept
    assert service.integration.id == integration.id
    # table is changed
    assert service.table.id == table_2.id
    # everything else is resetted
    assert service.view is None
    assert service.service_aggregation_series.all().count() == 0
    assert service.service_aggregation_group_bys.all().count() == 0
    assert service.service_sorts.all().count() == 0


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 2},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": {
            f"field_{field.id}": Decimal("20"),
            f"field_{field_2.id}": Decimal("8"),
        },
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_with_view(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    data_fixture.create_view_filter(
        view=view, field=field, type="lower_than", value="5"
    )
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 6},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 6},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": {
            f"field_{field.id}": Decimal("6"),
            f"field_{field_2.id}": Decimal("4"),
        },
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_with_service_filters(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = None
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=field_2, type="lower_than", value="5", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 6},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 6},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": {
            f"field_{field.id}": Decimal("6"),
            f"field_{field_2.id}": Decimal("4"),
        },
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_no_series(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = None
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfigured) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == "There are no aggregation series defined."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_aggregation_type_doesnt_exist(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="invalid", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfigured) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == "The the aggregation type invalid doesn't exist."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_incompatible_aggregation(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="not_checked_percentage", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfigured) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert (
        exc.value.args[0]
        == f"The field with ID {field.id} is not compatible with the aggregation type not_checked_percentage."
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_agg_series_field_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, trashed=True)
    field_2 = data_fixture.create_number_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfigured) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == f"The field with ID {field.id} is trashed."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_group_by_field_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table, trashed=True)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfigured) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == f"The field with ID {field_2.id} is trashed."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_table_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user, trashed=True)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfigured) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == f"The specified table is trashed"


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_with_total_aggregation(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_boolean_field(table=table)
    field_2 = data_fixture.create_boolean_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="checked_percentage", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service,
        field=field_2,
        aggregation_type="not_checked_percentage",
        order=1,
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": True, f"field_{field_2.id}": True},
            {f"field_{field.id}": True, f"field_{field_2.id}": True},
            {f"field_{field.id}": True, f"field_{field_2.id}": True},
            {f"field_{field.id}": False, f"field_{field_2.id}": False},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": {
            f"field_{field.id}": 75.0,
            f"field_{field_2.id}": 25.0,
        },
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_group_by(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_text_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_3, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 2,
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": "First group",
            },
            {
                f"field_{field.id}": 4,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": "Second group",
            },
            {
                f"field_{field.id}": 6,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": "First group",
            },
            {
                f"field_{field.id}": 8,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": "Second group",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": "Second group",
            },
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": "Third group",
            },
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": None,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": Decimal("1"),
                f"field_{field_2.id}": Decimal("1"),
                f"field_{field_3.id}": None,
            },
            {
                f"field_{field.id}": Decimal("1"),
                f"field_{field_2.id}": Decimal("1"),
                f"field_{field_3.id}": "Third group",
            },
            {
                f"field_{field.id}": Decimal("8"),
                f"field_{field_2.id}": Decimal("6"),
                f"field_{field_3.id}": "First group",
            },
            {
                f"field_{field.id}": Decimal("22"),
                f"field_{field_2.id}": Decimal("7"),
                f"field_{field_3.id}": "Second group",
            },
        ]
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_group_by_id(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 2},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": Decimal("2"),
                f"field_{field_2.id}": Decimal("2"),
                "id": 1,
            },
            {
                f"field_{field.id}": Decimal("4"),
                f"field_{field_2.id}": Decimal("2"),
                "id": 2,
            },
            {
                f"field_{field.id}": Decimal("6"),
                f"field_{field_2.id}": Decimal("2"),
                "id": 3,
            },
            {
                f"field_{field.id}": Decimal("8"),
                f"field_{field_2.id}": Decimal("2"),
                "id": 4,
            },
        ]
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_with_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_3, order=1, order_by="ASC"
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_2, order=2, order_by="DESC"
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            # group 1
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            # group 2
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            # group 3
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            # group 4
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 100,
                f"field_{field_3.id}": 100,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": Decimal("90"),
                f"field_{field_2.id}": Decimal("9"),
                f"field_{field_3.id}": Decimal("3"),
            },
            {
                f"field_{field.id}": Decimal("60"),
                f"field_{field_2.id}": Decimal("6"),
                f"field_{field_3.id}": Decimal("6"),
            },
            {
                f"field_{field.id}": Decimal("30"),
                f"field_{field_2.id}": Decimal("3"),
                f"field_{field_3.id}": Decimal("6"),
            },
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": Decimal("100"),
                f"field_{field_3.id}": Decimal("100"),
            },
        ],
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_with_group_by_row_id(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_3, order=1, order_by="ASC"
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_2, order=2, order_by="DESC"
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 4,
            },
            {
                f"field_{field.id}": 2,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": 1,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": Decimal("5"),
                f"field_{field_3.id}": Decimal("1"),
                "id": 5,
            },
            {
                f"field_{field.id}": Decimal("3"),
                f"field_{field_2.id}": Decimal("3"),
                f"field_{field_3.id}": Decimal("2"),
                "id": 4,
            },
            {
                f"field_{field.id}": Decimal("3"),
                f"field_{field_2.id}": Decimal("3"),
                f"field_{field_3.id}": Decimal("3"),
                "id": 3,
            },
            {
                f"field_{field.id}": Decimal("2"),
                f"field_{field_2.id}": Decimal("2"),
                f"field_{field_3.id}": Decimal("3"),
                "id": 2,
            },
            {
                f"field_{field.id}": Decimal("1"),
                f"field_{field_2.id}": Decimal("1"),
                f"field_{field_3.id}": Decimal("4"),
                "id": 1,
            },
        ],
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_without_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_3, order=1, order_by="ASC"
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_2, order=2, order_by="DESC"
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 4,
            },
            {
                f"field_{field.id}": 2,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": 1,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    # the results are still a dictionary, not sorted on the backend
    assert result == {
        "result": {
            f"field_{field.id}": Decimal("9"),
            f"field_{field_2.id}": Decimal("14"),
            f"field_{field_3.id}": Decimal("13"),
        }
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_group_by_field(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field, order=1, order_by="ASC"
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            # group 1
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            # group 2
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            # group 3
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            # group 4
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 100,
                f"field_{field_3.id}": 100,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": Decimal("100"),
                f"field_{field_3.id}": Decimal("100"),
            },
            {
                f"field_{field.id}": Decimal("10"),
                f"field_{field_2.id}": Decimal("3"),
                f"field_{field_3.id}": Decimal("6"),
            },
            {
                f"field_{field.id}": Decimal("20"),
                f"field_{field_2.id}": Decimal("6"),
                f"field_{field_3.id}": Decimal("6"),
            },
            {
                f"field_{field.id}": Decimal("30"),
                f"field_{field_2.id}": Decimal("9"),
                f"field_{field_3.id}": Decimal("3"),
            },
        ],
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_group_by_row_id(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field, order=1, order_by="ASC"
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": "A",
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 4,
            },
            {
                f"field_{field.id}": "H",
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": "I",
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": "B",
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": "",
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": 1,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": "",
                f"field_{field_2.id}": Decimal("5"),
                f"field_{field_3.id}": Decimal("1"),
                "id": 5,
            },
            {
                f"field_{field.id}": "A",
                f"field_{field_2.id}": Decimal("1"),
                f"field_{field_3.id}": Decimal("4"),
                "id": 1,
            },
            {
                f"field_{field.id}": "B",
                f"field_{field_2.id}": Decimal("3"),
                f"field_{field_3.id}": Decimal("2"),
                "id": 4,
            },
            {
                f"field_{field.id}": "H",
                f"field_{field_2.id}": Decimal("2"),
                f"field_{field_3.id}": Decimal("3"),
                "id": 2,
            },
            {
                f"field_{field.id}": "I",
                f"field_{field_2.id}": Decimal("3"),
                f"field_{field_3.id}": Decimal("3"),
                "id": 3,
            },
        ],
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_field_outside_series_or_group_bys(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_2, order=1, order_by="ASC"
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(
        ServiceImproperlyConfigured,
        match=f"The field with ID {field_2.id} cannot be used for sorting.",
    ):
        ServiceHandler().dispatch_service(service, dispatch_context)


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_primary_field_no_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field, order=2, order_by="ASC"
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(
        ServiceImproperlyConfigured,
        match=f"The field with ID {field.id} cannot be used for sorting.",
    ):
        ServiceHandler().dispatch_service(service, dispatch_context)


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_primary_field_group_by_another_field(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field, order=2, order_by="ASC"
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(
        ServiceImproperlyConfigured,
        match=f"The field with ID {field.id} cannot be used for sorting.",
    ):
        ServiceHandler().dispatch_service(service, dispatch_context)


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_with_group_by_ignore_view_sort(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    # these sorts will be ignored
    data_fixture.create_view_sort(view=view, field=field_3, order="ASC")
    data_fixture.create_view_sort(view=view, field=field_2, order="DESC")
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            # group 1
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            # group 2
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            # group 3
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            # group 4
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 100,
                f"field_{field_3.id}": 100,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": Decimal("100"),
                f"field_{field_3.id}": Decimal("100"),
            },
            {
                f"field_{field.id}": Decimal("30"),
                f"field_{field_2.id}": Decimal("3"),
                f"field_{field_3.id}": Decimal("6"),
            },
            {
                f"field_{field.id}": Decimal("90"),
                f"field_{field_2.id}": Decimal("9"),
                f"field_{field_3.id}": Decimal("3"),
            },
            {
                f"field_{field.id}": Decimal("60"),
                f"field_{field_2.id}": Decimal("6"),
                f"field_{field_3.id}": Decimal("6"),
            },
        ],
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_max_buckets_sort_on_group_by_field(
    data_fixture, settings
):
    settings.BASEROW_ENTERPRISE_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_2, order=1, order_by="ASC"
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 40,
                f"field_{field_2.id}": "Z",
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
            {
                f"field_{field.id}": 50,
                f"field_{field_2.id}": "M",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": Decimal("10"),
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": Decimal("60"),
                f"field_{field_2.id}": "H",
            },
            {
                f"field_{field.id}": Decimal("20"),
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": Decimal("30"),
                f"field_{field_2.id}": "L",
            },
        ],
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_max_buckets_sort_on_series(
    data_fixture, settings
):
    settings.BASEROW_ENTERPRISE_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field, order=1, order_by="ASC"
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 40,
                f"field_{field_2.id}": "Z",
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
            {
                f"field_{field.id}": 50,
                f"field_{field_2.id}": "M",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": Decimal("10"),
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": Decimal("20"),
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": Decimal("30"),
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": Decimal("40"),
                f"field_{field_2.id}": "Z",
            },
        ],
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_max_buckets_sort_on_primary_field(
    data_fixture, settings
):
    settings.BASEROW_ENTERPRISE_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table, primary=True)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    LocalBaserowTableServiceSort.objects.create(
        service=service, field=field_2, order=1, order_by="ASC"
    )

    rows = RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 40,
                f"field_{field_2.id}": "Z",
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
            {
                f"field_{field.id}": 50,
                f"field_{field_2.id}": "M",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert result == {
        "result": [
            {
                f"field_{field.id}": Decimal("10"),
                f"field_{field_2.id}": "A",
                "id": rows[3].id,
            },
            {
                f"field_{field.id}": Decimal("60"),
                f"field_{field_2.id}": "H",
                "id": rows[4].id,
            },
            {
                f"field_{field.id}": Decimal("20"),
                f"field_{field_2.id}": "K",
                "id": rows[1].id,
            },
            {
                f"field_{field.id}": Decimal("30"),
                f"field_{field_2.id}": "L",
                "id": rows[2].id,
            },
        ],
    }
