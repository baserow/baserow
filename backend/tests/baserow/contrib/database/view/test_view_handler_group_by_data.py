import pytest

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import DEFAULT_SORT_TYPE_KEY
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.mark.django_db
def test_get_group_by_data_supports_every_groupable_field(data_fixture):
    """
    Grouping by any field that reports it can be grouped by must not raise. This
    exercises every field type/sub type present in the interesting test table.
    """

    table, user, row, blank_row, context = setup_interesting_test_table(data_fixture)

    view_handler = ViewHandler()
    model = table.get_model()

    groupable_fields = []
    for field in context["fields"].values():
        specific = field.specific
        field_type = field_type_registry.get_by_model(specific)
        if field_type.check_can_group_by(specific, DEFAULT_SORT_TYPE_KEY):
            groupable_fields.append(specific)

    assert groupable_fields, "Expected the interesting table to have groupable fields"

    failures = {}
    for field in groupable_fields:
        grid = data_fixture.create_grid_view(user=user, table=table)
        data_fixture.create_view_group_by(view=grid, field=field)
        base_queryset = view_handler.get_queryset(
            user, grid, model=model, apply_sorts=False
        )
        view_group_bys = list(grid.viewgroupby_set.all())
        try:
            result = view_handler.get_group_by_data(base_queryset, view_group_bys)
            assert "groups" in result
        except Exception as exc:  # noqa: BLE001
            failures[field.db_column] = f"{type(exc).__name__}: {exc}"

    assert not failures, "group-by data failed for fields:\n" + "\n".join(
        f"  {name}: {err}" for name, err in failures.items()
    )


def _group_paths(view_handler, user, grid, model, db_column):
    """The group key of each group, in the order group-by data returns them."""

    base_queryset = view_handler.get_queryset(
        user, grid, model=model, apply_sorts=False
    )
    data = view_handler.get_group_by_data(
        base_queryset, list(grid.viewgroupby_set.all()), limit=200
    )
    return [tuple(group["path"][db_column]) for group in data["groups"]], data


def _distinct_group_keys_in_row_order(view_handler, user, grid, model, db_column):
    """
    The distinct group keys in the order the rows are sorted by the view. This is the
    order groups were shown in before the collapsible group-by feature, where the
    frontend grouped consecutive rows. group-by data must reproduce it exactly.
    """

    seen = []
    for row in view_handler.get_queryset(user, grid, model=model):
        key = tuple(related.id for related in getattr(row, db_column).all())
        if key not in seen:
            seen.append(key)
    return seen


@pytest.mark.django_db
def test_get_group_by_data_orders_multiple_collaborators_groups_like_rows(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    collaborator_a = data_fixture.create_user(
        workspace=database.workspace, first_name="Aaa"
    )
    collaborator_b = data_fixture.create_user(
        workspace=database.workspace, first_name="Bbb"
    )
    collaborator_c = data_fixture.create_user(
        workspace=database.workspace, first_name="Ccc"
    )
    field = data_fixture.create_multiple_collaborators_field(table=table, name="People")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    model = table.get_model()
    db_column = field.db_column
    for collaborator in [
        collaborator_c,
        collaborator_a,
        collaborator_a,
        collaborator_b,
    ]:
        getattr(model.objects.create(), db_column).set([collaborator.id])

    view_handler = ViewHandler()
    order, data = _group_paths(view_handler, user, grid, model, db_column)

    assert order == [(collaborator_a.id,), (collaborator_b.id,), (collaborator_c.id,)]
    assert order == _distinct_group_keys_in_row_order(
        view_handler, user, grid, model, db_column
    )
    assert [group["row_offset"] for group in data["groups"]] == [0, 2, 3]


@pytest.mark.django_db
def test_get_group_by_data_orders_multiple_select_groups_like_rows(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    option_a = data_fixture.create_select_option(field=field, value="Aaa", order=0)
    option_b = data_fixture.create_select_option(field=field, value="Bbb", order=1)
    option_c = data_fixture.create_select_option(field=field, value="Ccc", order=2)
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    model = table.get_model()
    db_column = field.db_column
    for option in [option_c, option_a, option_a, option_b]:
        getattr(model.objects.create(), db_column).set([option.id])

    view_handler = ViewHandler()
    order, data = _group_paths(view_handler, user, grid, model, db_column)

    assert order == [(option_a.id,), (option_b.id,), (option_c.id,)]
    assert order == _distinct_group_keys_in_row_order(
        view_handler, user, grid, model, db_column
    )
    assert [group["row_offset"] for group in data["groups"]] == [0, 2, 3]


@pytest.mark.django_db
def test_get_group_by_data_orders_link_row_groups_like_rows(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    linked_table = data_fixture.create_database_table(user=user, database=database)
    linked_primary = data_fixture.create_text_field(
        table=linked_table, name="Name", primary=True
    )
    field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table, name="Links"
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    linked_model = linked_table.get_model()
    linked_a = linked_model.objects.create(**{f"field_{linked_primary.id}": "Aaa"})
    linked_b = linked_model.objects.create(**{f"field_{linked_primary.id}": "Bbb"})
    linked_c = linked_model.objects.create(**{f"field_{linked_primary.id}": "Ccc"})

    model = table.get_model()
    db_column = field.db_column
    for linked in [linked_c, linked_a, linked_a, linked_b]:
        getattr(model.objects.create(), db_column).set([linked.id])

    view_handler = ViewHandler()
    order, data = _group_paths(view_handler, user, grid, model, db_column)

    assert order == [(linked_a.id,), (linked_b.id,), (linked_c.id,)]
    assert order == _distinct_group_keys_in_row_order(
        view_handler, user, grid, model, db_column
    )
    assert [group["row_offset"] for group in data["groups"]] == [0, 2, 3]


@pytest.mark.django_db
def test_get_group_by_data_groups_collaborator_set_regardless_of_order(data_fixture):
    """
    The same set of collaborators added in different orders must form a single group,
    keyed by the sorted ids. Regression for optimistically-created groups whose key
    (the cell's append order) otherwise diverged from the server's group key.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    collaborator_a = data_fixture.create_user(
        workspace=database.workspace, first_name="Aaa"
    )
    collaborator_b = data_fixture.create_user(
        workspace=database.workspace, first_name="Bbb"
    )
    field = data_fixture.create_multiple_collaborators_field(table=table, name="People")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=field)

    model = table.get_model()
    db_column = field.db_column
    getattr(model.objects.create(), db_column).set(
        [collaborator_a.id, collaborator_b.id]
    )
    getattr(model.objects.create(), db_column).set(
        [collaborator_b.id, collaborator_a.id]
    )

    view_handler = ViewHandler()
    base_queryset = view_handler.get_queryset(
        user, grid, model=model, apply_sorts=False
    )
    data = view_handler.get_group_by_data(
        base_queryset, list(grid.viewgroupby_set.all()), limit=50
    )

    sorted_ids = sorted([collaborator_a.id, collaborator_b.id])
    assert [list(group["path"][db_column]) for group in data["groups"]] == [sorted_ids]
    assert data["groups"][0]["row_count"] == 2


@pytest.mark.django_db
def test_get_group_by_data_resolves_collaborator_parent_path_regardless_of_order(
    data_fixture,
):
    """
    Fetching the children of a collaborator parent group must resolve the rows even when
    the requested parent path lists the ids in a different order than the stored set.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    collaborator_a = data_fixture.create_user(
        workspace=database.workspace, first_name="Aaa"
    )
    collaborator_b = data_fixture.create_user(
        workspace=database.workspace, first_name="Bbb"
    )
    people = data_fixture.create_multiple_collaborators_field(
        table=table, name="People"
    )
    status = data_fixture.create_single_select_field(table=table, name="Status")
    option = data_fixture.create_select_option(field=status, value="Open", order=0)
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=people)
    data_fixture.create_view_group_by(view=grid, field=status)

    model = table.get_model()
    row = model.objects.create(**{f"field_{status.id}_id": option.id})
    getattr(row, people.db_column).set([collaborator_a.id, collaborator_b.id])

    view_handler = ViewHandler()
    base_queryset = view_handler.get_queryset(
        user, grid, model=model, apply_sorts=False
    )
    view_group_bys = list(grid.viewgroupby_set.all())

    data = view_handler.get_group_by_data(
        base_queryset,
        view_group_bys,
        # Reversed order on purpose; the path must still resolve the same group.
        parent_path={people.db_column: [collaborator_b.id, collaborator_a.id]},
    )

    assert [group["path"][status.db_column] for group in data["groups"]] == [option.id]


@pytest.mark.django_db
def test_get_group_by_data_supports_many_to_many_parent_level(data_fixture):
    """
    Fetching the children of a many-to-many group (its value is a list of ids in the
    requested parent path) must not raise. Regression for the nested collaborator +
    single select group-by.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    collaborator = data_fixture.create_user(
        workspace=database.workspace, first_name="Aaa"
    )
    people = data_fixture.create_multiple_collaborators_field(
        table=table, name="People"
    )
    status = data_fixture.create_single_select_field(table=table, name="Status")
    option = data_fixture.create_select_option(field=status, value="Open", order=0)
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=people)
    data_fixture.create_view_group_by(view=grid, field=status)

    model = table.get_model()
    row = model.objects.create(**{f"field_{status.id}_id": option.id})
    getattr(row, people.db_column).set([collaborator.id])

    view_handler = ViewHandler()
    base_queryset = view_handler.get_queryset(
        user, grid, model=model, apply_sorts=False
    )
    view_group_bys = list(grid.viewgroupby_set.all())

    data = view_handler.get_group_by_data(
        base_queryset,
        view_group_bys,
        parent_path={people.db_column: [collaborator.id]},
    )

    assert [group["path"][status.db_column] for group in data["groups"]] == [option.id]
