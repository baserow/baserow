from django.db import migrations, models, transaction
from django.db.models import F, Max, Q

BATCH_SIZE = 1_000


def populate_widget_grid_layout(apps, schema_editor):
    Dashboard = apps.get_model("dashboard", "Dashboard")
    Widget = apps.get_model("dashboard", "Widget")
    db_alias = schema_editor.connection.alias
    dashboard_manager = Dashboard._base_manager.db_manager(db_alias)
    widget_manager = Widget._base_manager.db_manager(db_alias)

    # Process dashboards and their ordered widget rows with keyset pagination. This
    # avoids both an unbounded in-memory snapshot and a server-side cursor/transaction
    # spanning the whole table. The primary key makes the widget cursor deterministic
    # when multiple rows have the same fractional order.
    last_dashboard_id = 0
    while True:
        dashboard_ids = list(
            widget_manager
            .filter(dashboard_id__gt=last_dashboard_id)
            .order_by("dashboard_id")
            .values_list("dashboard_id", flat=True)
            .distinct()[:BATCH_SIZE]
        )
        if not dashboard_ids:
            break
        last_dashboard_id = dashboard_ids[-1]

        for dashboard_id in dashboard_ids:
            last_order = None
            last_widget_id = 0
            while True:
                cursor = Q()
                if last_order is not None:
                    cursor = Q(order__gt=last_order) | Q(
                        order=last_order, id__gt=last_widget_id
                    )
                with transaction.atomic(using=db_alias):
                    # Match the runtime lock order (dashboard, then widgets). The
                    # chunk is read and rewritten under these locks so a current
                    # process cannot initialize the same rows between both steps.
                    try:
                        dashboard_manager.select_for_update(of=("self",)).get(
                            id=dashboard_id
                        )
                    except Dashboard.DoesNotExist:
                        # A concurrent permanent dashboard deletion can complete
                        # after the keyset snapshot but before this dashboard's turn.
                        # Its widgets are gone as well, so there is nothing to backfill.
                        break
                    next_grid_y = (
                        widget_manager
                        .filter(
                            dashboard_id=dashboard_id,
                            grid_layout_initialized=True,
                        )
                        .aggregate(
                            max_bottom=Max(F("grid_y") + F("grid_height"))
                        )["max_bottom"]
                        or 0
                    )
                    widgets = list(
                        widget_manager
                        .select_for_update()
                        .filter(cursor, dashboard_id=dashboard_id)
                        .select_related("content_type")
                        .order_by("order", "id")[:BATCH_SIZE]
                    )
                    if not widgets:
                        break

                    widgets_to_update = []
                    for widget in widgets:
                        if widget.grid_layout_initialized:
                            continue

                        grid_height = (
                            4 if widget.content_type.model == "summarywidget" else 9
                        )
                        widget.grid_x = 0
                        widget.grid_y = next_grid_y
                        widget.grid_width = 6
                        widget.grid_height = grid_height
                        widget.grid_layout_initialized = True
                        widgets_to_update.append(widget)
                        next_grid_y += grid_height

                    if widgets_to_update:
                        widget_manager.bulk_update(
                            widgets_to_update,
                            [
                                "grid_x",
                                "grid_y",
                                "grid_width",
                                "grid_height",
                                "grid_layout_initialized",
                            ],
                            batch_size=BATCH_SIZE,
                        )

                    last_order = widgets[-1].order
                    last_widget_id = widgets[-1].id


class Migration(migrations.Migration):
    # Release the AddField locks before the potentially long data backfill. Each
    # data batch above has its own bounded transaction.
    atomic = False

    dependencies = [
        ("dashboard", "0003_widget_dashboarddatasource_summarywidget"),
    ]

    operations = [
        migrations.AddField(
            model_name="widget",
            name="grid_x",
            field=models.PositiveIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name="widget",
            name="grid_y",
            field=models.PositiveIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name="widget",
            name="grid_width",
            field=models.PositiveIntegerField(db_default=6, default=6),
        ),
        migrations.AddField(
            model_name="widget",
            name="grid_height",
            field=models.PositiveIntegerField(db_default=9, default=9),
        ),
        migrations.AddField(
            model_name="widget",
            name="grid_layout_initialized",
            field=models.BooleanField(db_default=False, default=True),
        ),
        migrations.RunPython(populate_widget_grid_layout, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="widget",
            options={"ordering": ("grid_y", "grid_x", "id")},
        ),
    ]
