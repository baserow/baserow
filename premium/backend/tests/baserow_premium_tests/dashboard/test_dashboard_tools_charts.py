"""Chart and pie chart widgets through the shared dashboard tools."""

from django.test.utils import override_settings

import pytest

from baserow.contrib.dashboard.tools.widgets import (
    create_widgets,
    get_widget_data,
    list_widgets,
    update_widgets,
)
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.core.tools import ToolContext
from baserow_premium.dashboard.widgets.models import ChartSeriesConfig


def _setup(premium_data_fixture, licence=True):
    user = premium_data_fixture.create_user(has_active_premium_license=licence)
    workspace = premium_data_fixture.create_workspace(user=user)
    dashboard = premium_data_fixture.create_dashboard_application(workspace=workspace)
    premium_data_fixture.create_local_baserow_integration(
        application=dashboard, authorized_user=user
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    name = premium_data_fixture.create_text_field(
        table=table, name="Name", primary=True
    )
    amount = premium_data_fixture.create_number_field(table=table, name="Amount")
    stage = premium_data_fixture.create_single_select_field(table=table, name="Stage")
    won = premium_data_fixture.create_select_option(field=stage, value="Won")
    lost = premium_data_fixture.create_select_option(field=stage, value="Lost")
    model = table.get_model()
    for value, option in ((2, won), (3, won), (7, lost)):
        model.objects.create(
            **{f"field_{amount.id}": value, f"field_{stage.id}_id": option.id}
        )
    ctx = ToolContext(user=user, workspace=workspace)
    return ctx, dashboard, table, name, amount, stage


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_chart_widget_with_series_and_group_by(premium_data_fixture):
    ctx, dashboard, table, _, amount, stage = _setup(premium_data_fixture)

    result = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "chart",
                "title": "By stage",
                "table_id": table.id,
                "series": [
                    {"field_id": amount.id, "aggregation_type": "sum"},
                    {"field_id": amount.id, "aggregation_type": "max"},
                ],
                "group_by_field_id": stage.id,
                "chart_type": "LINE",
            }
        ],
    )

    assert result["errors"] == []
    (created,) = result["created"]
    assert created | {"id": None, "data_source_id": None} == {
        "id": None,
        "type": "chart",
        "title": "By stage",
        "description": "",
        "data_source_id": None,
        "table_id": table.id,
        "view_id": None,
        "series": [
            {"field_id": amount.id, "aggregation_type": "sum"},
            {"field_id": amount.id, "aggregation_type": "max"},
        ],
        "group_by_field_id": stage.id,
        "chart_type": "LINE",
    }
    assert list_widgets(ctx, dashboard.id)["widgets"] == [created]
    # Each series is drawn as a line, as the chart says.
    configs = ChartSeriesConfig.objects.filter(widget_id=created["id"])
    assert sorted(c.series_chart_type for c in configs) == ["LINE", "LINE"]
    data = get_widget_data(ctx, [created["id"]])["widgets"][0]
    assert data["configured"] is True
    results = {row["id"]: row for row in data["data"]["results"]}
    # JSON values, as the API returns them.
    assert results["Won"]["Amount sum"] == "5"
    assert results["Lost"]["Amount max"] == "7"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_pie_chart_widget_draws_series_as_pie(premium_data_fixture):
    ctx, dashboard, table, _, amount, stage = _setup(premium_data_fixture)

    result = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "pie_chart",
                "title": "Split",
                "table_id": table.id,
                "series": [{"field_id": amount.id, "aggregation_type": "sum"}],
                "group_by_field_id": stage.id,
            }
        ],
    )

    assert result["errors"] == []
    widget = Widget.objects.get(id=result["created"][0]["id"]).specific
    assert result["created"][0]["chart_type"] == "PIE"
    assert [c.series_chart_type for c in widget.series_config.all()] == ["PIE"]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_chart_type_redraws_every_series(premium_data_fixture):
    ctx, dashboard, table, _, amount, _ = _setup(premium_data_fixture)
    widget_id = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "chart",
                "title": "Bars",
                "table_id": table.id,
                "series": [{"field_id": amount.id, "aggregation_type": "sum"}],
            }
        ],
    )["created"][0]["id"]

    result = update_widgets(ctx, [{"widget_id": widget_id, "chart_type": "LINE"}])

    assert result["errors"] == []
    assert result["updated"][0]["chart_type"] == "LINE"
    configs = ChartSeriesConfig.objects.filter(widget_id=widget_id)
    assert [c.series_chart_type for c in configs] == ["LINE"]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_chart_series_replaces_them(premium_data_fixture):
    ctx, dashboard, table, _, amount, _ = _setup(premium_data_fixture)
    widget_id = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "chart",
                "title": "Bars",
                "table_id": table.id,
                "series": [{"field_id": amount.id, "aggregation_type": "sum"}],
            }
        ],
    )["created"][0]["id"]

    result = update_widgets(
        ctx,
        [
            {
                "widget_id": widget_id,
                "series": [{"field_id": amount.id, "aggregation_type": "average"}],
            }
        ],
    )

    assert result["errors"] == []
    assert result["updated"][0]["series"] == [
        {"field_id": amount.id, "aggregation_type": "average"}
    ]
    assert ChartSeriesConfig.objects.filter(widget_id=widget_id).count() == 1


@pytest.mark.django_db
def test_create_chart_widget_without_licence_reports_feature_error(
    premium_data_fixture,
):
    ctx, dashboard, table, _, amount, _ = _setup(premium_data_fixture, licence=False)

    result = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "chart",
                "title": "By stage",
                "table_id": table.id,
                "series": [{"field_id": amount.id, "aggregation_type": "sum"}],
            }
        ],
    )

    assert result["created"] == []
    error = result["errors"][0]["error"]
    assert error != "Internal error."
    assert "licen" in error.lower() or "feature" in error.lower()
    assert Widget.objects.filter(dashboard=dashboard).count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_chart_series_over_the_limit_is_rejected(premium_data_fixture, settings):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES = 1
    ctx, dashboard, table, _, amount, _ = _setup(premium_data_fixture)

    result = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "chart",
                "title": "Too many",
                "table_id": table.id,
                "series": [
                    {"field_id": amount.id, "aggregation_type": "sum"},
                    {"field_id": amount.id, "aggregation_type": "max"},
                ],
            }
        ],
    )

    assert result["created"] == []
    assert "maximum" in result["errors"][0]["error"]
    assert Widget.objects.filter(dashboard=dashboard).count() == 0
