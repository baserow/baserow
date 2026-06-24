# noinspection PyPep8Naming

import pytest

MAX_ORDER_VALUE = 32767


# noinspection PyPep8Naming
@pytest.mark.once_per_day_in_ci
@pytest.mark.django_db
def test_forwards_migration(data_fixture, migrator, teardown_table_metadata):
    migrate_from = [("database", "0211_viewsort_viewgroupby_priority")]
    migrate_to = [("database", "0212_fix_viewsort_priority_overflow")]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Database = old_state.apps.get_model("database", "Database")
    Table = old_state.apps.get_model("database", "Table")
    TextField = old_state.apps.get_model("database", "TextField")
    GridView = old_state.apps.get_model("database", "GridView")
    ViewSort = old_state.apps.get_model("database", "ViewSort")
    ViewGroupBy = old_state.apps.get_model("database", "ViewGroupBy")

    workspace = Workspace.objects.create(name="workspace")
    database = Database.objects.create(
        content_type=ContentType.objects.get_for_model(Database),
        order=1,
        name="db",
        workspace=workspace,
        trashed=False,
    )
    table = Table.objects.create(database=database, name="table", order=1)
    field_a = TextField.objects.create(
        name="a",
        table=table,
        order=1,
        content_type=ContentType.objects.get_for_model(TextField),
    )
    field_b = TextField.objects.create(
        name="b",
        table=table,
        order=2,
        content_type=ContentType.objects.get_for_model(TextField),
    )
    grid_view = GridView.objects.create(
        table=table,
        name="grid",
        order=1,
        content_type=ContentType.objects.get_for_model(GridView),
    )

    # Two sorts both backfilled to the smallint ceiling by migration 0211.
    sort_a = ViewSort.objects.create(
        view=grid_view, field=field_a, order="ASC", priority=MAX_ORDER_VALUE
    )
    sort_b = ViewSort.objects.create(
        view=grid_view, field=field_b, order="ASC", priority=MAX_ORDER_VALUE
    )
    group_a = ViewGroupBy.objects.create(
        view=grid_view, field=field_a, order="ASC", priority=MAX_ORDER_VALUE
    )
    group_b = ViewGroupBy.objects.create(
        view=grid_view, field=field_b, order="ASC", priority=MAX_ORDER_VALUE
    )

    new_state = migrator.migrate(migrate_to)
    NewViewSort = new_state.apps.get_model("database", "ViewSort")
    NewViewGroupBy = new_state.apps.get_model("database", "ViewGroupBy")

    # Priorities are renumbered densely, preserving order (by previous priority, id).
    assert NewViewSort.objects.get(id=sort_a.id).priority == 1
    assert NewViewSort.objects.get(id=sort_b.id).priority == 2
    assert NewViewGroupBy.objects.get(id=group_a.id).priority == 1
    assert NewViewGroupBy.objects.get(id=group_b.id).priority == 2
