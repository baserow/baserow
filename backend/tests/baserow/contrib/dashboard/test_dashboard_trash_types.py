import pytest

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.dashboard.widgets.trash_types import WidgetTrashableItemType
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_restore_widget(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    widget_2 = data_fixture.create_summary_widget(dashboard=dashboard)

    TrashHandler.trash(user, dashboard.workspace, dashboard, widget_2)

    assert [p.id for p in WidgetService().get_widgets(user, dashboard.id)] == [
        widget.id,
    ]

    TrashHandler.restore_item(user, WidgetTrashableItemType.type, widget_2.id)

    assert [p.id for p in WidgetService().get_widgets(user, dashboard.id)] == [
        widget.id,
        widget_2.id,
    ]


@pytest.mark.django_db
def test_restore_widget_after_compacted_delete_is_placed_after_active_layout(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    widget_2 = data_fixture.create_summary_widget(dashboard=dashboard)
    widget.grid_width = 6
    widget.grid_height = 4
    widget.save(update_fields=["grid_width", "grid_height"])
    widget_2.grid_width = 6
    widget_2.grid_height = 4
    widget_2.save(update_fields=["grid_width", "grid_height"])

    WidgetService().delete_widget(user, widget.id)
    widget_2.refresh_from_db()
    assert widget_2.grid_y == 0

    TrashHandler.restore_item(user, WidgetTrashableItemType.type, widget.id)

    widget.refresh_from_db()
    assert (widget.grid_x, widget.grid_y) == (0, 4)
    assert (widget_2.grid_x, widget_2.grid_y) == (0, 0)


@pytest.mark.django_db
def test_delete_widget_permanently_removes_data_source(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    data_source_id = widget.data_source.id

    TrashHandler.trash(user, dashboard.workspace, dashboard, widget)
    TrashHandler.empty(user, dashboard.workspace.id, dashboard.id)
    TrashHandler.permanently_delete_marked_trash()

    assert Widget.objects.filter(id=widget.id).count() == 0
    assert DashboardDataSource.objects.filter(id=data_source_id).count() == 0


@pytest.mark.django_db
def test_widget_trash_hooks_receive_persisted_state_and_restoration_metadata(
    data_fixture, monkeypatch
):
    """Hooks bracket persisted changes and see restored layout and custom metadata."""
    from baserow.contrib.dashboard.widgets.registries import widget_type_registry

    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    remaining = data_fixture.create_summary_widget(dashboard=dashboard)
    widget_type = widget_type_registry.get_by_model(widget)
    observations = []

    def record_hook(name):
        original = getattr(widget_type, name)

        def hook(instance, *args):
            entry = args[-1]
            persisted = Widget.objects_and_trash.get(id=instance.id)
            source = DashboardDataSource.objects_and_trash.get(id=widget.data_source_id)
            observations.append(
                (name, instance.trashed, persisted.trashed, source.trashed)
            )
            if name == "before_trashed":
                assert args[0] == user
                entry.additional_restoration_data = {"custom": "preserved"}
                entry.save(update_fields=["additional_restoration_data"])
            elif name == "after_restore":
                assert entry.additional_restoration_data["custom"] == "preserved"
                assert instance.grid_y >= remaining.grid_y + remaining.grid_height
            return original(instance, *args)

        return hook

    for name in ["before_trashed", "after_trashed", "before_restore", "after_restore"]:
        monkeypatch.setattr(widget_type, name, record_hook(name))
    # The trash API can receive base widgets rather than their specific subclasses.
    entry = TrashHandler.trash(
        user, dashboard.workspace, dashboard, Widget.objects.get(id=widget.id)
    )
    entry.refresh_from_db()
    assert entry.additional_restoration_data["custom"] == "preserved"
    TrashHandler.restore_item(user, WidgetTrashableItemType.type, widget.id)
    assert observations == [
        ("before_trashed", False, False, False),
        ("after_trashed", True, True, True),
        ("before_restore", True, True, True),
        ("after_restore", False, False, False),
    ]
