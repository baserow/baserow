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
        "group_by_row_id": False,
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
    assert result["errors"][0]["error"] == (
        "The related user does not have access to these features."
    )
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


def _styled_chart(premium_data_fixture):
    """A chart with two series, the second one restyled in the UI."""

    ctx, dashboard, table, _, amount, stage = _setup(premium_data_fixture)
    widget_id = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "chart",
                "title": "Styled",
                "table_id": table.id,
                "series": [
                    {"field_id": amount.id, "aggregation_type": "sum"},
                    {"field_id": amount.id, "aggregation_type": "max"},
                ],
                "group_by_field_id": stage.id,
            }
        ],
    )["created"][0]["id"]
    second = ChartSeriesConfig.objects.filter(widget_id=widget_id).order_by(
        "series__order"
    )[1]
    second.series_chart_type = "LINE"
    second.series_color = "#ff0000"
    second.save()
    return ctx, table, amount, widget_id


def _styles(widget_id):
    return [
        (c.series_id, c.series_chart_type, c.series_color)
        for c in ChartSeriesConfig.objects.filter(widget_id=widget_id).order_by(
            "series__order"
        )
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_changing_the_view_keeps_series_styles(premium_data_fixture):
    ctx, table, _, widget_id = _styled_chart(premium_data_fixture)
    view = premium_data_fixture.create_grid_view(table=table)
    before = _styles(widget_id)

    result = update_widgets(ctx, [{"widget_id": widget_id, "view_id": view.id}])

    assert result["errors"] == []
    assert result["updated"][0]["view_id"] == view.id
    assert _styles(widget_id) == before


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_changing_one_series_keeps_the_style_of_the_others(premium_data_fixture):
    ctx, _, amount, widget_id = _styled_chart(premium_data_fixture)
    before = _styles(widget_id)

    result = update_widgets(
        ctx,
        [
            {
                "widget_id": widget_id,
                "series": [
                    {"field_id": amount.id, "aggregation_type": "average"},
                    {"field_id": amount.id, "aggregation_type": "max"},
                    {"field_id": amount.id, "aggregation_type": "min"},
                ],
            }
        ],
    )

    assert result["errors"] == []
    after = _styles(widget_id)
    assert after[:2] == before
    assert after[2][1:] == ("BAR", None)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_changing_the_chart_type_keeps_series_colours(premium_data_fixture):
    ctx, _, _, widget_id = _styled_chart(premium_data_fixture)

    update_widgets(ctx, [{"widget_id": widget_id, "chart_type": "LINE"}])

    assert [s[1:] for s in _styles(widget_id)] == [
        ("LINE", None),
        ("LINE", "#ff0000"),
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_changing_the_group_by_keeps_series_styles(premium_data_fixture):
    ctx, table, _, widget_id = _styled_chart(premium_data_fixture)
    region = premium_data_fixture.create_single_select_field(table=table, name="Region")
    before = _styles(widget_id)

    result = update_widgets(
        ctx, [{"widget_id": widget_id, "group_by_field_id": region.id}]
    )

    assert result["errors"] == []
    assert result["updated"][0]["group_by_field_id"] == region.id
    assert _styles(widget_id) == before


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_chart_rejects_aggregation_the_chart_service_does_not_have(
    premium_data_fixture,
):
    ctx, dashboard, table, *_ = _setup(premium_data_fixture)
    date = premium_data_fixture.create_date_field(table=table, name="Closed")

    result = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "chart",
                "title": "First close",
                "table_id": table.id,
                "series": [{"field_id": date.id, "aggregation_type": "min_date"}],
            }
        ],
    )

    assert result["created"] == []
    error = result["errors"][0]["error"]
    assert "min_date can't be used on field 'Closed'. Use one of: " in error
    assert "min_date," not in error and "max_date" not in error
    assert Widget.objects.filter(dashboard=dashboard).count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_removing_a_series_keeps_the_style_of_the_others(premium_data_fixture):
    ctx, _, amount, widget_id = _styled_chart(premium_data_fixture)
    before = _styles(widget_id)

    result = update_widgets(
        ctx,
        [
            {
                "widget_id": widget_id,
                "series": [{"field_id": amount.id, "aggregation_type": "max"}],
            }
        ],
    )

    assert result["errors"] == []
    assert _styles(widget_id) == [before[1]]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_reordering_series_keeps_their_styles(premium_data_fixture):
    ctx, _, amount, widget_id = _styled_chart(premium_data_fixture)
    before = _styles(widget_id)

    update_widgets(
        ctx,
        [
            {
                "widget_id": widget_id,
                "series": [
                    {"field_id": amount.id, "aggregation_type": "max"},
                    {"field_id": amount.id, "aggregation_type": "sum"},
                ],
            }
        ],
    )

    assert _styles(widget_id) == [before[1], before[0]]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_chart_clears_the_group_by(premium_data_fixture):
    ctx, _, _, widget_id = _styled_chart(premium_data_fixture)

    result = update_widgets(
        ctx, [{"widget_id": widget_id, "clear": ["group_by_field_id"]}]
    )

    assert result["errors"] == []
    assert result["updated"][0]["group_by_field_id"] is None
    assert result["updated"][0]["group_by_row_id"] is False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_chart_grouped_by_row_id_is_listed_as_such(premium_data_fixture):
    ctx, _, _, widget_id = _styled_chart(premium_data_fixture)
    widget = Widget.objects.get(id=widget_id).specific
    # How the UI stores "group by row id".
    widget.data_source.service.specific.service_aggregation_group_bys.update(
        field_id=None
    )

    (listed,) = list_widgets(ctx, widget.dashboard_id)["widgets"]
    assert listed["group_by_field_id"] is None
    assert listed["group_by_row_id"] is True

    result = update_widgets(
        ctx, [{"widget_id": widget_id, "clear": ["group_by_field_id"]}]
    )
    assert result["errors"] == []
    assert result["updated"][0]["group_by_row_id"] is False
