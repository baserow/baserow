from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, connections, transaction
from django.db.models import QuerySet

import pytest

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.widgets.exceptions import WidgetDoesNotExist
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.models import SummaryWidget, Widget
from baserow.contrib.dashboard.widgets.registries import widget_type_registry


@pytest.mark.django_db
def test_get_widget(data_fixture, django_assert_num_queries):
    widget = data_fixture.create_summary_widget(title="Title 1")

    fetched_widget = WidgetHandler().get_widget(widget_id=widget.id)

    with django_assert_num_queries(0):
        fetched_widget.dashboard.id
        fetched_widget.dashboard.workspace.id

    assert fetched_widget == widget


@pytest.mark.django_db
def test_get_widget_does_not_exist(data_fixture):
    with pytest.raises(WidgetDoesNotExist):
        WidgetHandler().get_widget(widget_id=999)


@pytest.mark.django_db
def test_get_widget_with_base_queryset(data_fixture):
    widget = data_fixture.create_summary_widget(
        title="Title 1",
    )
    widget_2 = data_fixture.create_summary_widget(
        title="Title 2",
    )
    base_queryset = Widget.objects.filter(title="Title 1")

    fetched_widget = WidgetHandler().get_widget(widget.id, base_queryset)
    assert fetched_widget == widget

    with pytest.raises(WidgetDoesNotExist):
        WidgetHandler().get_widget(widget_2.id, base_queryset)


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
def test_get_widget_for_update(data_fixture):
    widget = data_fixture.create_summary_widget(
        title="Title 1",
    )

    with transaction.atomic():
        fetched_widget = WidgetHandler().get_widget_for_update(widget_id=widget.id)

        with pytest.raises(DatabaseError):
            connections["default-copy"]
            Widget.objects.using("default-copy").select_for_update(nowait=True).get(
                id=widget.id
            )

    assert fetched_widget == widget


@pytest.mark.django_db
def test_get_widget_for_update_does_not_exist(data_fixture):
    with pytest.raises(WidgetDoesNotExist):
        WidgetHandler().get_widget_for_update(widget_id=999)


@pytest.mark.django_db
def test_get_widget_for_update_with_base_queryset(data_fixture):
    widget = data_fixture.create_summary_widget(title="Title 1")
    widget_2 = data_fixture.create_summary_widget(title="Title 2")
    base_queryset = Widget.objects.filter(title="Title 1")

    fetched_widget = WidgetHandler().get_widget_for_update(widget.id, base_queryset)
    assert fetched_widget == widget

    with pytest.raises(WidgetDoesNotExist):
        WidgetHandler().get_widget_for_update(widget_2.id, base_queryset)


@pytest.mark.django_db
def test_get_widgets(data_fixture, django_assert_num_queries):
    dashboard = data_fixture.create_dashboard_application()
    dashboard_2 = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(
        title="Title 1",
        dashboard=dashboard,
    )
    widget_2 = data_fixture.create_summary_widget(
        title="Title 2",
        description="Desc 2",
        dashboard=dashboard,
    )
    widget_different_dashboard = data_fixture.create_summary_widget(
        title="Title 1",
        dashboard=dashboard_2,
    )

    widgets: list = WidgetHandler().get_widgets(dashboard, specific=False)
    assert len(widgets) == 2

    with django_assert_num_queries(0):
        assert widgets[0].title == widget.title
        assert widgets[0].dashboard.id == widget.dashboard.id
        assert widgets[0].order == widget.order
        assert isinstance(widgets[0], Widget)
        assert widgets[1].title == widget_2.title
        assert widgets[1].description == widget_2.description
        assert widgets[1].dashboard.id == widget_2.dashboard.id
        assert widgets[1].order == widget_2.order
        assert isinstance(widgets[1], Widget)
        widgets[0].dashboard.workspace.id


@pytest.mark.django_db
def test_get_widgets_specific(data_fixture, django_assert_num_queries):
    dashboard = data_fixture.create_dashboard_application()
    dashboard_2 = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(
        title="Title 1",
        dashboard=dashboard,
    )
    widget_2 = data_fixture.create_summary_widget(
        title="Title 2",
        dashboard=dashboard,
    )
    widget_different_dashboard = data_fixture.create_summary_widget(
        title="Title 1",
        dashboard=dashboard_2,
    )

    widgets: QuerySet = WidgetHandler().get_widgets(dashboard, specific=True)
    assert len(widgets) == 2

    with django_assert_num_queries(0):
        assert widgets[0].title == widget.title
        assert widgets[0].dashboard.id == widget.dashboard.id
        assert widgets[0].order == widget.order
        assert isinstance(widgets[0], SummaryWidget)
        assert widgets[1].title == widget_2.title
        assert widgets[1].dashboard.id == widget_2.dashboard.id
        assert widgets[1].order == widget_2.order
        assert isinstance(widgets[1], SummaryWidget)
        widgets[0].dashboard.workspace.id


@pytest.mark.django_db
def test_get_widgets_with_base_queryset(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    dashboard_2 = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(
        title="Title 1",
        dashboard=dashboard,
    )
    widget_2 = data_fixture.create_summary_widget(
        title="Title 2",
        dashboard=dashboard,
    )
    widget_3 = data_fixture.create_summary_widget(
        title="Title 3",
        dashboard=dashboard,
    )
    widget_different_dashboard = data_fixture.create_summary_widget(
        title="Title 1",
        dashboard=dashboard_2,
    )
    base_queryset = Widget.objects.filter(title="Title 2")

    widgets = WidgetHandler().get_widgets(
        dashboard, base_queryset=base_queryset, specific=False
    )

    assert len(list(widgets)) == 1


@pytest.mark.django_db
def test_create_widget(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    widget_type = widget_type_registry.get("summary")

    widget = WidgetHandler().create_widget(
        widget_type,
        dashboard=dashboard,
        title="New widget title",
        description="My desc",
    )

    assert widget.dashboard.id == dashboard.id
    assert widget.order == 1
    assert widget.title == "New widget title"
    assert widget.description == "My desc"
    assert widget.content_type == ContentType.objects.get_for_model(SummaryWidget)
    assert Widget.objects.count() == 1


@pytest.mark.django_db
def test_update_widget(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    dashboard_2 = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, title="Original title", description="Original desc"
    )

    updated_widget = WidgetHandler().update_widget(
        widget, dashboard=dashboard_2, title="Changed title", description="Changed desc"
    )

    assert updated_widget.widget.dashboard.id == dashboard.id  # can't be changed
    assert updated_widget.widget.title == "Changed title"
    assert updated_widget.widget.description == "Changed desc"


@pytest.mark.django_db
def test_delete_widget(data_fixture):
    widget = data_fixture.create_summary_widget(title="Title 1")
    data_source_id = widget.data_source_id
    assert Widget.objects.count() == 1

    WidgetHandler().delete_widget(widget)
    assert Widget.objects.count() == 0

    assert DashboardDataSource.objects.filter(id=data_source_id).count() == 0
