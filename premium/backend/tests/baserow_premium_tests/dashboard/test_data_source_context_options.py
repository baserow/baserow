import pytest

from baserow.contrib.dashboard.api.data_sources.serializers import (
    DashboardDataSourceSerializer,
)
from baserow.contrib.dashboard.api.public.serializers import (
    serialize_public_data_source,
)
from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.data_providers import (
    DashboardDataSourceContextDataProviderType,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.widgets.models import TextFilterWidget
from baserow.core.formula import BaserowFormulaObject
from baserow.core.registries import ImportExportConfig
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db
@pytest.mark.parametrize(
    "service_name",
    [
        "local_baserow_list_rows",
        "local_baserow_get_row",
        "local_baserow_aggregate_rows",
        "local_baserow_grouped_aggregate_rows",
    ],
)
def test_every_table_source_exposes_all_field_options(
    premium_data_fixture, service_name
):
    """Unselected fields and unused options are discoverable for every source type."""
    fixture = premium_data_fixture
    user = fixture.create_user()
    dashboard = fixture.create_dashboard_application(user=user)
    table = fixture.create_database_table(user=user)
    amount = fixture.create_number_field(table=table, name="Revenue")
    category = fixture.create_single_select_field(table=table, name="Category")
    audience = fixture.create_multiple_select_field(table=table, name="Audience")
    option = fixture.create_select_option(field=category, value="Books", color="blue")
    other = fixture.create_select_option(field=audience, value="Retail", color="green")
    service_type = service_type_registry.get(service_name)
    values = (
        {"field": amount, "aggregation_type": "sum"}
        if service_name == "local_baserow_aggregate_rows"
        else {}
    )
    source = DashboardDataSourceHandler().create_data_source(
        dashboard,
        "Products",
        service_type,
        table=table,
        **values,
    )
    service = source.service.specific
    serialized = service_type.get_serializer(
        service, DashboardDataSourceSerializer, context={"data_source": source}
    ).data
    expected = [{"id": option.id, "value": "Books", "color": "blue"}]
    assert serialized["context_data"][category.db_column] == expected
    assert serialized["context_data"][audience.db_column] == [
        {"id": other.id, "value": "Retail", "color": "green"}
    ]
    schema = serialized["context_data_schema"]
    assert schema["title"] == table.name
    assert set(schema["properties"]) == {category.db_column, audience.db_column}
    assert set(schema["properties"][category.db_column]["items"]["properties"]) == {
        "id",
        "value",
        "color",
    }
    assert (
        serialize_public_data_source(
            source, referenced_option_fields=[category.db_column]
        )["context_data"][category.db_column]
        == expected
    )
    assert (
        audience.db_column
        not in serialize_public_data_source(
            source, referenced_option_fields=[category.db_column]
        )["context_data"]
    )
    provider = DashboardDataSourceContextDataProviderType()
    assert provider.extract_properties(
        [str(source.id), category.db_column, "*", "value"]
    ) == {service.id: [category.db_column]}
    assert service_type.import_context_path(
        [category.db_column, "*", "value"], {"database_fields": {category.id: 999}}
    ) == ["field_999", "*", "value"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "service_name",
    ["local_baserow_aggregate_rows", "local_baserow_grouped_aggregate_rows"],
)
def test_aggregate_option_formulas_remap_when_dashboard_is_copied(
    premium_data_fixture, service_name
):
    """Option references keep their source and field when an aggregate is duplicated."""
    fixture = premium_data_fixture
    user = fixture.create_user()
    dashboard = fixture.create_dashboard_application(user=user)
    table = fixture.create_database_table(user=user)
    amount = fixture.create_number_field(table=table)
    category = fixture.create_single_select_field(table=table)
    fixture.create_select_option(field=category, value="Books", color="blue")
    values = (
        {"field": amount, "aggregation_type": "sum"}
        if service_name == "local_baserow_aggregate_rows"
        else {}
    )
    source = DashboardDataSourceHandler().create_data_source(
        dashboard,
        "Products",
        service_type_registry.get(service_name),
        table=table,
        **values,
    )
    TextFilterWidget.objects.create(
        dashboard=dashboard,
        title="Category",
        mode="dropdown",
        options=BaserowFormulaObject.create(
            f"get('data_source_context.{source.id}.{category.db_column}.*.value')"
        ),
    )
    mapping = {
        "database_tables": {table.id: table.id},
        "database_fields": {field.id: field.id for field in table.field_set.all()},
    }
    config = ImportExportConfig(include_permission_data=True)
    kind = DashboardApplicationType()
    copied = kind.import_serialized(
        dashboard.workspace, kind.export_serialized(dashboard, config), config, mapping
    )
    copied_owner = TextFilterWidget.objects.get(dashboard=copied)
    copied_source = mapping["dashboard_data_sources"][source.id]
    assert copied_owner.options == BaserowFormulaObject.create(
        f"get('data_source_context.{copied_source}.{category.db_column}.*.value')"
    )
