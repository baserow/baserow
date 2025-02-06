from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError

import pytest

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.dashboard.widgets.trash_types import WidgetTrashableItemType
from baserow.contrib.integrations.local_baserow.models import LocalBaserowAggregateRows
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_create_summary_widget_creates_data_source(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget_type = "summary"

    created_widget = WidgetService().create_widget(
        user, widget_type, dashboard.id, title="My widget", description="My description"
    )

    assert created_widget.data_source is not None
    assert (
        created_widget.data_source.service.content_type
        == ContentType.objects.get_for_model(LocalBaserowAggregateRows)
    )


@pytest.mark.django_db
def test_summary_widget_trash_restore(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    data_source_id = widget.data_source.id

    TrashHandler.trash(user, dashboard.workspace, dashboard, widget)

    ds = DashboardDataSource.objects_and_trash.get(id=data_source_id)
    assert ds.trashed is True

    TrashHandler.restore_item(user, WidgetTrashableItemType.type, widget.id)

    ds = DashboardDataSource.objects_and_trash.get(id=data_source_id)
    assert ds.trashed is False


@pytest.mark.django_db
def test_summary_widget_datasource_cannot_be_deleted(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    summary_widget = data_fixture.create_summary_widget(dashboard=dashboard)

    with pytest.raises(ProtectedError):
        DashboardDataSourceService().delete_data_source(
            user, summary_widget.data_source.id
        )
