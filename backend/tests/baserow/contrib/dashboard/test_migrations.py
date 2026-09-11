from django.db.migrations.recorder import MigrationRecorder
from django.db.models.query import QuerySet

import pytest


@pytest.mark.once_per_day_in_ci
def test_widget_grid_layout_backfill_resumes_after_a_failed_batch(
    migrator, monkeypatch
):
    migrate_from = [("dashboard", "0003_widget_dashboarddatasource_summarywidget")]
    migrate_to = [("dashboard", "0005_populate_widget_grid_layout")]
    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Dashboard = old_state.apps.get_model("dashboard", "Dashboard")
    Widget = old_state.apps.get_model("dashboard", "Widget")
    SummaryWidget = old_state.apps.get_model("dashboard", "SummaryWidget")

    workspace = Workspace.objects.create(name="Workspace")
    dashboard_content_type = ContentType.objects.get_for_model(Dashboard)
    summary_content_type = ContentType.objects.get_for_model(SummaryWidget)
    other_content_type = ContentType.objects.get_for_model(Widget)
    mixed_dashboard = Dashboard.objects.create(
        workspace=workspace,
        order=1,
        name="Mixed dashboard",
        content_type=dashboard_content_type,
    )
    large_dashboard = Dashboard.objects.create(
        workspace=workspace,
        order=2,
        name="Large dashboard",
        content_type=dashboard_content_type,
    )
    Widget.objects.create(
        dashboard=mixed_dashboard,
        content_type=summary_content_type,
        title="Summary",
        order=1,
    )
    trashed_widget = Widget.objects.create(
        dashboard=mixed_dashboard,
        content_type=other_content_type,
        title="Trashed",
        order=1,
        trashed=True,
    )
    Widget.objects.create(
        dashboard=mixed_dashboard,
        content_type=other_content_type,
        title="Other",
        order=1,
    )
    Widget.objects.bulk_create(
        [
            Widget(
                dashboard=large_dashboard,
                content_type=summary_content_type,
                title=f"Summary {index}",
                order=index,
                # A trashed widget at the batch boundary must not reserve space
                # when the next batch resumes from the initialized layout.
                trashed=index == 999,
            )
            for index in range(1_001)
        ]
    )

    bulk_update = QuerySet.bulk_update

    def fail_second_large_batch(queryset, objects, *args, **kwargs):
        if (
            queryset.model._meta.label_lower == "dashboard.widget"
            and objects[0].title == "Summary 1000"
        ):
            raise RuntimeError("Interrupted backfill")
        return bulk_update(queryset, objects, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(QuerySet, "bulk_update", fail_second_large_batch)
        with pytest.raises(RuntimeError, match="Interrupted backfill"):
            migrator.migrate(migrate_to)

    applied = MigrationRecorder.Migration.objects.filter(app="dashboard")
    assert applied.filter(name="0004_widget_grid_layout").exists()
    assert not applied.filter(name="0005_populate_widget_grid_layout").exists()

    partial_state = migrator.migrate([("dashboard", "0004_widget_grid_layout")])
    Widget = partial_state.apps.get_model("dashboard", "Widget")
    assert (
        Widget.objects.filter(
            dashboard_id=large_dashboard.id, grid_layout_initialized=True
        ).count()
        == 1_000
    )

    new_state = migrator.migrate(migrate_to)
    Widget = new_state.apps.get_model("dashboard", "Widget")

    mixed_widgets = list(
        Widget.objects.filter(dashboard_id=mixed_dashboard.id, trashed=False).order_by(
            "order", "id"
        )
    )
    assert [
        (
            widget.grid_y,
            widget.grid_width,
            widget.grid_height,
            widget.grid_layout_initialized,
        )
        for widget in mixed_widgets
    ] == [(0, 6, 4, True), (4, 6, 9, True)]
    trashed_widget = Widget._base_manager.get(id=trashed_widget.id)
    assert trashed_widget.grid_layout_initialized
    assert trashed_widget.grid_height == 9

    large_widgets = Widget.objects.filter(dashboard_id=large_dashboard.id).order_by(
        "order", "id"
    )
    assert large_widgets.count() == 1_001
    assert large_widgets.first().grid_y == 0
    assert large_widgets.last().grid_y == 3_996
    assert not large_widgets.filter(grid_layout_initialized=False).exists()
