import pytest
from baserow_premium.views.handler import get_rows_grouped_by_single_select_field
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL

from baserow.contrib.database.views.exceptions import ViewDoesNotExist, ViewNotInTable
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import (
    OWNERSHIP_TYPE_COLLABORATIVE,
    GridView,
    View,
)
from baserow.core.exceptions import PermissionDenied


@pytest.mark.django_db
def test_get_rows_grouped_by_single_select_field(
    premium_data_fixture, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    view = premium_data_fixture.create_grid_view(table=table)
    text_field = premium_data_fixture.create_text_field(table=table, primary=True)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="red"
    )

    model = table.get_model()
    row_none1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row None 1",
            f"field_{single_select_field.id}_id": None,
        }
    )
    row_none2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row None 2",
            f"field_{single_select_field.id}_id": None,
        }
    )
    row_a1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row A1",
            f"field_{single_select_field.id}_id": option_a.id,
        }
    )
    row_a2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row A2",
            f"field_{single_select_field.id}_id": option_a.id,
        }
    )
    row_b1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row B1",
            f"field_{single_select_field.id}_id": option_b.id,
        }
    )
    row_b2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row B2",
            f"field_{single_select_field.id}_id": option_b.id,
        }
    )

    # The amount of queries including
    with django_assert_num_queries(6):
        rows = get_rows_grouped_by_single_select_field(
            user, view, single_select_field, model=model
        )

    assert len(rows) == 3
    assert rows["null"]["count"] == 2
    assert len(rows["null"]["results"]) == 2
    assert rows["null"]["results"][0].id == row_none1.id
    assert rows["null"]["results"][1].id == row_none2.id

    assert rows[str(option_a.id)]["count"] == 2
    assert len(rows[str(option_a.id)]["results"]) == 2
    assert rows[str(option_a.id)]["results"][0].id == row_a1.id
    assert rows[str(option_a.id)]["results"][1].id == row_a2.id

    assert rows[str(option_b.id)]["count"] == 2
    assert len(rows[str(option_b.id)]["results"]) == 2
    assert rows[str(option_b.id)]["results"][0].id == row_b1.id
    assert rows[str(option_b.id)]["results"][1].id == row_b2.id

    rows = get_rows_grouped_by_single_select_field(
        user, view, single_select_field, default_limit=1
    )

    assert len(rows) == 3
    assert rows["null"]["count"] == 2
    assert len(rows["null"]["results"]) == 1
    assert rows["null"]["results"][0].id == row_none1.id

    assert rows[str(option_a.id)]["count"] == 2
    assert len(rows[str(option_a.id)]["results"]) == 1
    assert rows[str(option_a.id)]["results"][0].id == row_a1.id

    assert rows[str(option_b.id)]["count"] == 2
    assert len(rows[str(option_b.id)]["results"]) == 1
    assert rows[str(option_b.id)]["results"][0].id == row_b1.id

    rows = get_rows_grouped_by_single_select_field(
        user, view, single_select_field, default_limit=1, default_offset=1
    )

    assert len(rows) == 3
    assert rows["null"]["count"] == 2
    assert len(rows["null"]["results"]) == 1
    assert rows["null"]["results"][0].id == row_none2.id

    assert rows[str(option_a.id)]["count"] == 2
    assert len(rows[str(option_a.id)]["results"]) == 1
    assert rows[str(option_a.id)]["results"][0].id == row_a2.id

    assert rows[str(option_b.id)]["count"] == 2
    assert len(rows[str(option_b.id)]["results"]) == 1
    assert rows[str(option_b.id)]["results"][0].id == row_b2.id

    rows = get_rows_grouped_by_single_select_field(
        user,
        view,
        single_select_field,
        option_settings={"null": {"limit": 1, "offset": 1}},
    )

    assert len(rows) == 1
    assert rows["null"]["count"] == 2
    assert len(rows["null"]["results"]) == 1
    assert rows["null"]["results"][0].id == row_none2.id

    rows = get_rows_grouped_by_single_select_field(
        user,
        view,
        single_select_field,
        option_settings={
            str(option_a.id): {"limit": 1, "offset": 0},
            str(option_b.id): {"limit": 1, "offset": 1},
        },
    )

    assert len(rows) == 2

    assert rows[str(option_a.id)]["count"] == 2
    assert len(rows[str(option_a.id)]["results"]) == 1
    assert rows[str(option_a.id)]["results"][0].id == row_a1.id

    assert rows[str(option_b.id)]["count"] == 2
    assert len(rows[str(option_b.id)]["results"]) == 1
    assert rows[str(option_b.id)]["results"][0].id == row_b2.id

    rows = get_rows_grouped_by_single_select_field(
        user,
        view,
        single_select_field,
        option_settings={
            str(option_a.id): {"limit": 10, "offset": 10},
        },
    )

    assert len(rows) == 1
    assert rows[str(option_a.id)]["count"] == 2
    assert len(rows[str(option_a.id)]["results"]) == 0


@pytest.mark.django_db
def test_get_rows_grouped_by_single_select_field_not_existing_options_are_null(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    view = View()
    view.id = 999  # fake pk
    view.table = table
    text_field = premium_data_fixture.create_text_field(table=table, primary=True)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="red"
    )

    model = table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row 1",
            f"field_{single_select_field.id}_id": None,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row 2",
            f"field_{single_select_field.id}_id": option_a.id,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row 3",
            f"field_{single_select_field.id}_id": option_b.id,
        }
    )

    option_b.delete()
    rows = get_rows_grouped_by_single_select_field(
        user, view, single_select_field, model=model
    )

    assert len(rows) == 2
    assert rows["null"]["count"] == 2
    assert len(rows["null"]["results"]) == 2
    assert rows["null"]["results"][0].id == row_1.id
    assert rows["null"]["results"][1].id == row_3.id
    assert rows[str(option_a.id)]["count"] == 1
    assert len(rows[str(option_a.id)]["results"]) == 1
    assert rows[str(option_a.id)]["results"][0].id == row_2.id

    option_a.delete()
    rows = get_rows_grouped_by_single_select_field(
        user, view, single_select_field, model=model
    )

    assert len(rows) == 1
    assert rows["null"]["count"] == 3
    assert len(rows["null"]["results"]) == 3
    assert rows["null"]["results"][0].id == row_1.id
    assert rows["null"]["results"][1].id == row_2.id
    assert rows["null"]["results"][2].id == row_3.id


@pytest.mark.django_db
def test_get_rows_grouped_by_single_select_field_with_empty_table(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table()
    view = View()
    view.id = 999  # fake pk
    view.table = table
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    rows = get_rows_grouped_by_single_select_field(user, view, single_select_field)
    assert len(rows) == 1
    assert rows["null"]["count"] == 0
    assert len(rows["null"]["results"]) == 0


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_list_views_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    view2 = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    user_views = handler.list_views(user, table, "grid", False, False, False, False, 10)
    assert len(user_views) == 2

    user2_views = handler.list_views(
        user2, table, "grid", False, False, False, False, 10
    )
    assert len(user2_views) == 1
    assert user2_views[0].id == view.id


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_get_view_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    handler.get_view_as_user(user, view.id)

    with pytest.raises(PermissionDenied):
        handler.get_view_as_user(user2, view.id)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_create_view_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )

    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    grid = GridView.objects.all().first()
    assert grid.owned_by == user
    assert grid.ownership_type == "personal"


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_update_view_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )

    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    handler.update_view(user=user, view=view, name="Renamed")
    view.refresh_from_db()
    assert view.name == "Renamed"

    with pytest.raises(PermissionDenied):
        handler.update_view(user=user2, view=view, name="Not my view")


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_duplicate_view_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )

    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    duplicated_view = handler.duplicate_view(user, view)
    assert duplicated_view.ownership_type == "personal"
    assert duplicated_view.owned_by == user

    with pytest.raises(PermissionDenied):
        handler.get_view_as_user(user2, duplicated_view.id)

    with pytest.raises(PermissionDenied):
        duplicated_view = handler.duplicate_view(user2, view)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_delete_view_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    handler.delete_view(user, view)

    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    with pytest.raises(PermissionDenied):
        handler.delete_view(user2, view)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_field_options_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )

    handler.get_field_options_as_user(user, view)

    with pytest.raises(PermissionDenied):
        handler.get_field_options_as_user(user2, view)

    handler.update_field_options(view, {}, user)

    with pytest.raises(PermissionDenied):
        handler.update_field_options(view, {}, user2)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_filters_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )
    field = data_fixture.create_text_field(table=view.table)

    filter = handler.create_filter(user, view, field, "equal", "value")

    with pytest.raises(PermissionDenied):
        handler.create_filter(user2, view, field, "equal", "value")

    handler.get_filter(user, filter.id)

    with pytest.raises(PermissionDenied):
        handler.get_filter(user2, filter.id)

    list = handler.list_filters(user, view.id)
    assert len(list) == 1

    with pytest.raises(PermissionDenied):
        handler.list_filters(user2, view.id)

    handler.update_filter(user, filter, field, "equal", "another value")

    with pytest.raises(PermissionDenied):
        handler.update_filter(user2, filter, field, "equal", "another value")

    with pytest.raises(PermissionDenied):
        handler.delete_filter(user2, filter)

    handler.delete_filter(user, filter)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_sorts_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )
    field = data_fixture.create_text_field(table=view.table)

    sort = handler.create_sort(user=user, view=view, field=field, order="ASC")

    with pytest.raises(PermissionDenied):
        handler.create_sort(user=user2, view=view, field=field, order="ASC")

    handler.get_sort(user, sort.id)

    with pytest.raises(PermissionDenied):
        handler.get_sort(user2, sort.id)

    list = handler.list_sorts(user, view.id)
    assert len(list) == 1

    with pytest.raises(PermissionDenied):
        handler.list_sorts(user2, view.id)

    handler.update_sort(user, sort, field)

    with pytest.raises(PermissionDenied):
        handler.update_sort(user2, sort, field)

    with pytest.raises(PermissionDenied):
        handler.delete_sort(user2, sort)

    handler.delete_sort(user, sort)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_decorations_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )
    decorator_type_name = "left_border_color"
    value_provider_type_name = ""
    value_provider_conf = {}

    decoration = handler.create_decoration(
        view,
        decorator_type_name,
        value_provider_type_name,
        value_provider_conf,
        user=user,
    )

    with pytest.raises(PermissionDenied):
        handler.create_decoration(
            view,
            decorator_type_name,
            value_provider_type_name,
            value_provider_conf,
            user=user2,
        )

    result = handler.get_decoration(user, decoration.id)
    assert result == decoration

    with pytest.raises(PermissionDenied):
        handler.get_decoration(user2, decoration.id)

    list = handler.list_decorations(user, view.id)
    assert len(list) == 1

    with pytest.raises(PermissionDenied):
        handler.list_decorations(user2, view.id)

    handler.update_decoration(decoration, user)

    with pytest.raises(PermissionDenied):
        handler.update_decoration(decoration, user2)

    with pytest.raises(PermissionDenied):
        handler.delete_decoration(decoration, user2)

    handler.delete_decoration(decoration, user)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_aggregations_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    field = data_fixture.create_number_field(user=user, table=table)
    view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type="personal",
    )
    handler.update_field_options(
        view=view,
        field_options={
            field.id: {
                "aggregation_type": "sum",
                "aggregation_raw_type": "sum",
            }
        },
    )
    aggr = [
        (
            field,
            "max",
        ),
    ]

    aggregations = handler.get_view_field_aggregations(user, view)
    assert field.db_column in aggregations

    handler.get_field_aggregations(user, view, aggr)

    with pytest.raises(PermissionDenied):
        handler.get_view_field_aggregations(user2, view)

    with pytest.raises(PermissionDenied):
        handler.get_field_aggregations(user2, view, aggr)


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_update_view_slug_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_update_view_ownership_type_no_premium(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    """A test to make sure it shouldn't be possible to update view `ownership_type`
    if User doesn't have premium features enabled.
    """

    workspace = data_fixture.create_workspace(name="Workspace 1")
    initial_owner_of_the_view = premium_data_fixture.create_user(workspace=workspace)
    user_without_premium = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(
        user=initial_owner_of_the_view,
        database=database,
    )
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        initial_owner_of_the_view, workspace.id
    )

    view = handler.create_view(
        user=initial_owner_of_the_view,
        table=table,
        type_name="form",
        name="Form",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    assert view.owned_by == initial_owner_of_the_view

    # The other user shouldn't be able to change the ownership type of the view,
    # since he doesn't have PREMIUM enabled:
    with pytest.raises(PermissionDenied):
        handler.update_view(
            user=user_without_premium,
            view=view,
            ownership_type=OWNERSHIP_TYPE_PERSONAL,
        )

    # New User should only be able to view / update the view, since initially it
    # was set as being `collaborative`:
    handler.get_view_as_user(user_without_premium, view.id)
    NEW_NAME = "Not my view"
    result = handler.update_view(
        user=user_without_premium,
        view=view,
        name=NEW_NAME,
    )
    assert result.updated_view_instance.name == NEW_NAME


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_update_view_ownership_type_owner_changed(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    """Tests if view owner (`owned_by` attribute) is updated when `ownership_type`
    for the view is changed.
    """

    workspace = data_fixture.create_workspace(name="Workspace 1")
    initial_owner_of_the_view = premium_data_fixture.create_user(workspace=workspace)
    new_owner_of_the_view = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(
        user=initial_owner_of_the_view,
        database=database,
    )
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        initial_owner_of_the_view, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        new_owner_of_the_view, workspace.id
    )

    view = handler.create_view(
        user=initial_owner_of_the_view,
        table=table,
        type_name="form",
        name="Form",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    assert view.owned_by == initial_owner_of_the_view

    handler.update_view(
        user=new_owner_of_the_view, view=view, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )
    assert view.owned_by == new_owner_of_the_view

    # Old (initial) user should loose the access to the view:
    with pytest.raises(PermissionDenied):
        handler.get_view_as_user(initial_owner_of_the_view, view.id)

    with pytest.raises(PermissionDenied):
        handler.update_view(
            user=initial_owner_of_the_view,
            view=view,
            name="Not my view anymore",
        )

    # New user is the only one that still has access to the view:
    handler.get_view_as_user(new_owner_of_the_view, view.id)
    new_view_name = "My new view name"
    result = handler.update_view(
        user=new_owner_of_the_view, view=view, name=new_view_name
    )
    updated_view = result.updated_view_instance
    assert updated_view.name == new_view_name


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_update_view_ownership_type_valid_type_string(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    """Tests if view ownership type can only be changed to one of the allowed
    view types (personal or collaborative).
    """

    workspace = data_fixture.create_workspace(name="Workspace 1")
    initial_owner_of_the_view = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(
        user=initial_owner_of_the_view,
        database=database,
    )
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        initial_owner_of_the_view, workspace.id
    )

    view = handler.create_view(
        user=initial_owner_of_the_view,
        table=table,
        type_name="form",
        name="Form",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    # Update the view from being collaborative to being personal and then back
    # to being collaborative again, all should be good:
    handler.update_view(
        user=initial_owner_of_the_view,
        view=view,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )
    view.refresh_from_db()
    assert view.owned_by == initial_owner_of_the_view
    assert view.ownership_type == OWNERSHIP_TYPE_PERSONAL

    handler.update_view(
        user=initial_owner_of_the_view,
        view=view,
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    view.refresh_from_db()
    assert view.owned_by == initial_owner_of_the_view
    assert view.ownership_type == OWNERSHIP_TYPE_COLLABORATIVE

    # Attempt to update the view to non existent ownership option:
    with pytest.raises(PermissionDenied):
        handler.update_view(
            user=initial_owner_of_the_view, view=view, ownership_type="non existent"
        )
    view.refresh_from_db()
    assert view.owned_by == initial_owner_of_the_view
    assert view.ownership_type == OWNERSHIP_TYPE_COLLABORATIVE


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_get_public_view_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    view = handler.create_view(
        user=user,
        table=table,
        type_name="form",
        name="Form",
        ownership_type="personal",
    )
    view.public = False
    view.slug = "slug"
    view.save()

    handler.get_public_view_by_slug(user, "slug")

    with pytest.raises(ViewDoesNotExist):
        handler.get_public_view_by_slug(user2, "slug")


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_order_views_personal_ownership_type(
    data_fixture, premium_data_fixture, alternative_per_workspace_license_service
):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = premium_data_fixture.create_user(workspace=workspace)
    user2 = premium_data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user2, workspace.id
    )
    grid_1 = data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, order=1, ownership_type="collaborative"
    )
    grid_2 = data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, order=2, ownership_type="collaborative"
    )
    grid_3 = data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, order=3, ownership_type="collaborative"
    )
    personal_grid = data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, order=2, ownership_type="personal"
    )
    personal_grid_2 = data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, order=3, ownership_type="personal"
    )

    handler.order_views(
        user=user,
        table=table,
        order=[personal_grid_2.id, personal_grid.id],
    )

    grid_1.refresh_from_db()
    grid_2.refresh_from_db()
    grid_3.refresh_from_db()
    personal_grid.refresh_from_db()
    personal_grid_2.refresh_from_db()
    assert personal_grid_2.order == 1
    assert personal_grid.order == 2
    assert grid_1.order == 1
    assert grid_2.order == 2
    assert grid_3.order == 3

    with pytest.raises(ViewNotInTable):
        handler.order_views(
            user=user2,
            table=table,
            order=[personal_grid_2.id, personal_grid_2.id],
        )
