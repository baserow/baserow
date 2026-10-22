from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError
from django.test.utils import override_settings

import pytest

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.dashboard.widgets.trash_types import WidgetTrashableItemType
from baserow.core.trash.handler import TrashHandler
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_chart_widget_creates_data_source(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    widget_type = "chart"

    created_widget = WidgetService().create_widget(
        user, widget_type, dashboard.id, title="My widget", description="My description"
    )

    assert created_widget.data_source is not None
    assert (
        created_widget.data_source.service.content_type
        == ContentType.objects.get_for_model(LocalBaserowGroupedAggregateRows)
    )


@pytest.mark.django_db
def test_chart_widget_trash_restore(premium_data_fixture):
    user = premium_data_fixture.create_user()
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    widget = premium_data_fixture.create_chart_widget(dashboard=dashboard)
    data_source_id = widget.data_source.id

    TrashHandler.trash(user, dashboard.workspace, dashboard, widget)

    ds = DashboardDataSource.objects_and_trash.get(id=data_source_id)
    assert ds.trashed is True

    TrashHandler.restore_item(user, WidgetTrashableItemType.type, widget.id)

    ds = DashboardDataSource.objects_and_trash.get(id=data_source_id)
    assert ds.trashed is False


@pytest.mark.django_db
def test_chart_widget_datasource_cannot_be_deleted(premium_data_fixture):
    user = premium_data_fixture.create_user()
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    chart_widget = premium_data_fixture.create_chart_widget(dashboard=dashboard)

    with pytest.raises(ProtectedError):
        DashboardDataSourceService().delete_data_source(
            user, chart_widget.data_source.id
        )


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["chart", "pie_chart"])
def test_chart_series_color_persistence(premium_data_fixture, kind):
    """A series color survives updates and serialization and can be reset."""
    from baserow.contrib.dashboard.widgets.registries import widget_type_registry
    from baserow.contrib.dashboard.widgets.types import UpdatedWidget
    from baserow_premium.api.dashboard.widgets.serializers import (
        ChartSeriesConfigSerializer,
        PieChartSeriesConfigSerializer,
    )
    from baserow_premium.integrations.local_baserow.models import (
        LocalBaserowTableServiceAggregationSeries,
    )

    widget = getattr(premium_data_fixture, f"create_{kind}_widget")()
    field = premium_data_fixture.create_number_field()
    series = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=widget.data_source.service, field=field, aggregation_type="sum", order=0
    )
    chart_type = "BAR" if kind == "chart" else "PIE"
    serializer_class = (
        ChartSeriesConfigSerializer
        if kind == "chart"
        else PieChartSeriesConfigSerializer
    )
    widget_type = widget_type_registry.get(kind)
    for color in ["#aabbcc", "#12345678", None]:
        config = {
            "series_id": series.id,
            "series_chart_type": chart_type,
            "series_color": color,
        }
        serializer = serializer_class(data=config)
        assert serializer.is_valid(), serializer.errors
        widget_type.after_update(
            UpdatedWidget(widget, {}, {}), series_config=[serializer.validated_data]
        )
        assert widget.series_config.get().series_color == color
        exported = widget_type.serialize_property(widget, "series_config")
        assert exported[0].get("series_color") == color
