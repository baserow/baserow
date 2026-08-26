from importlib import import_module

import pytest


def test_0004_widget_grid_layout_migration_is_non_atomic():
    migration_module = import_module(
        "baserow.contrib.dashboard.migrations.0004_widget_grid_layout"
    )

    assert migration_module.Migration.atomic is False


@pytest.mark.once_per_day_in_ci
def test_0004_widget_grid_layout_backfills_type_heights_and_multiple_batches(
    migrator,
):
    migrate_from = [("dashboard", "0003_widget_dashboarddatasource_summarywidget")]
    migrate_to = [("dashboard", "0004_widget_grid_layout")]
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
            )
            for index in range(1_001)
        ]
    )

    new_state = migrator.migrate(migrate_to)
    Widget = new_state.apps.get_model("dashboard", "Widget")

    mixed_widgets = list(
        Widget.objects.filter(dashboard_id=mixed_dashboard.id).order_by("order", "id")
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

    large_widgets = Widget.objects.filter(dashboard_id=large_dashboard.id).order_by(
        "order", "id"
    )
    assert large_widgets.count() == 1_001
    assert large_widgets.first().grid_y == 0
    assert large_widgets.last().grid_y == 4_000
    assert not large_widgets.filter(grid_layout_initialized=False).exists()
