"""
Tests for changing the filters of the charts' data sources with the service filter
tools shared by Kuma and MCP.
"""

import pytest

from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFilter,
)
from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterOperation,
)
from baserow.contrib.integrations.local_baserow.service_filters.tools import (
    list_filterable_data_sources,
    list_service_filters,
    update_service_filters,
)
from baserow.core.tools import ToolContext


@pytest.fixture
def chart(premium_data_fixture):
    user = premium_data_fixture.create_user()
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    amount = premium_data_fixture.create_number_field(table=table, name="Amount")
    dashboard = premium_data_fixture.create_dashboard_application(workspace=workspace)
    data_source = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    premium_data_fixture.create_chart_widget(
        dashboard=dashboard, title="Deals per month", data_source=data_source
    )
    return ToolContext(user=user, workspace=workspace), data_source, amount


def add_amount_filter(amount, group=None) -> FilterOperation:
    return FilterOperation(
        op="add_filter",
        field_id=amount.id,
        type="higher_than",
        value="1000",
        group=group,
    )


@pytest.mark.django_db
def test_chart_data_sources_are_listed_by_widget_title(chart):
    ctx, data_source, _ = chart

    result = list_filterable_data_sources(ctx)

    assert [
        (item["kind"], item["id"], item["name"]) for item in result["data_sources"]
    ] == [("dashboard_data_source", data_source.id, "Deals per month")]
    described = list_service_filters(ctx, "dashboard_data_source", data_source.id)
    assert described["name"] == "Deals per month"
    assert described["supports_filter_groups"] is True


@pytest.mark.django_db
def test_chart_filters_are_saved_with_nested_groups(chart):
    """Chart filters preserve their group membership and parent relationships."""
    ctx, data_source, amount = chart
    result = update_service_filters(
        ctx,
        "dashboard_data_source",
        data_source.id,
        [
            FilterOperation(op="add_group", group_id="g", filter_type="OR"),
            add_amount_filter(amount, group="g"),
            FilterOperation(
                op="add_group", group_id="nested", parent_group="g", filter_type="AND"
            ),
            add_amount_filter(amount, group="nested"),
        ],
    )
    assert result["changed"] is True
    filters = list(
        LocalBaserowTableServiceFilter.objects.filter(
            service=data_source.service
        ).select_related("group")
    )
    assert [(f.field_id, f.type, f.value["formula"]) for f in filters] == [
        (amount.id, "higher_than", "1000"),
        (amount.id, "higher_than", "1000"),
    ]
    parent, child = [f.group for f in filters]
    assert parent.filter_type == "OR"
    assert parent.parent_group_id is None
    assert child.filter_type == "AND"
    assert child.parent_group_id == parent.id
