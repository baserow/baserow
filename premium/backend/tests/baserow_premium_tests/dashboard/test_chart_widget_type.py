from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError
from django.test.utils import override_settings

import pytest
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
)

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.dashboard.widgets.trash_types import WidgetTrashableItemType
from baserow.core.trash.handler import TrashHandler


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
