from copy import deepcopy

import pytest

from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
@pytest.mark.parametrize("copy_table", [False, True])
@pytest.mark.parametrize(
    "reference",
    ["get('{path}')", "get( '{path}' )", "get(('{path}'))"],
)
def test_dashboard_copy_remaps_filter_and_source_formulas(
    data_fixture, copy_table, reference
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    widget = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Team",
        values=["Design"],
        operator="starts_with",
        formula_value=BaserowFormulaObject.create(
            reference.format(path=f"table.{table.id}.*.{field.db_column}")
        ),
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=source.service,
        field=field,
        type="equal",
        value=BaserowFormulaObject.create(
            reference.format(path=f"dashboard_filter.{selection.id}")
        ),
    )
    application_type = DashboardApplicationType()
    config = ImportExportConfig(include_permission_data=True, is_duplicate=True)
    exported = application_type.export_serialized(dashboard, config)
    assert set(exported["filters"][0]) == {
        "id",
        "order",
        "label",
        "type",
        "operator",
        "mode",
        "multiple",
        "formula_value",
        "values",
    }
    mapping = {}
    expected_table, expected_field = table, field
    if copy_table:
        expected_table = data_fixture.create_database_table(user=user)
        expected_field = data_fixture.create_text_field(table=expected_table)
        mapping = {
            "database_tables": {table.id: expected_table.id},
            "database_fields": {field.id: expected_field.id},
        }
    imported = application_type.import_serialized(
        dashboard.workspace, deepcopy(exported), config, mapping
    )
    copied_widget = WidgetService().get_widgets(user, imported.id)[0]
    copied_filter = DashboardFilterService().get_filters(user, imported.id)[0]
    assert copied_widget.id != widget.id
    assert copied_filter.operator == "starts_with"
    assert copied_filter.values == ["Design"]
    assert (
        copied_filter.formula_value["formula"]
        == f"get('table.{expected_table.id}.*.{expected_field.db_column}')"
    )
    assert (
        copied_widget.data_source.service.specific.service_filters.get().value[
            "formula"
        ]
        == f"get('dashboard_filter.{copied_filter.id}')"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("legacy_export", [False, True])
def test_dashboard_copy_preserves_filter_order(data_fixture, legacy_export):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    service = DashboardFilterService()
    first, second, third = [
        service.create_filter(user, dashboard.id, label=label)
        for label in ["Country", "Channel", "Team"]
    ]
    service.order_filters(user, dashboard.id, [third.id, first.id, second.id])
    application_type = DashboardApplicationType()
    config = ImportExportConfig(include_permission_data=True, is_duplicate=True)
    exported = application_type.export_serialized(dashboard, config)
    if legacy_export:
        for dashboard_filter in exported["filters"]:
            dashboard_filter.pop("order")
    else:
        # The stored order is authoritative, even if export entries are rearranged.
        exported["filters"].reverse()

    imported = application_type.import_serialized(
        dashboard.workspace, deepcopy(exported), config, {}
    )
    assert [f.label for f in service.get_filters(user, imported.id)] == [
        "Team",
        "Country",
        "Channel",
    ]
