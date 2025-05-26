import pytest
from pyinstrument import Profiler

from baserow.contrib.database.views.usage_types import FormViewWorkspaceStorageUsageItem
from baserow.core.models import Workspace
from baserow.core.trash.handler import TrashHandler
from baserow.core.usage.handler import UsageHandler
from baserow.core.usage.registries import USAGE_UNIT_MB


@pytest.mark.django_db
def test_form_view_workspace_storage_usage_item(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 0

    cover_image = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)
    logo_image = data_fixture.create_user_file(is_image=True, size=4 * USAGE_UNIT_MB)

    data_fixture.create_form_view(
        table=table,
        cover_image=cover_image,
        logo_image=logo_image,
    )

    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 6


@pytest.mark.django_db
def test_form_view_workspace_storage_usage_item_trashed_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    cover_image = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)
    logo_image = data_fixture.create_user_file(is_image=True, size=4 * USAGE_UNIT_MB)

    data_fixture.create_form_view(
        table=table,
        cover_image=cover_image,
        logo_image=logo_image,
    )

    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 6

    TrashHandler().trash(user, workspace, database, database)
    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )
    assert usage == 0


@pytest.mark.django_db
def test_form_view_workspace_storage_usage_item_trashed_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    cover_image = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)
    logo_image = data_fixture.create_user_file(is_image=True, size=4 * USAGE_UNIT_MB)

    data_fixture.create_form_view(
        table=table,
        cover_image=cover_image,
        logo_image=logo_image,
    )

    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 6

    TrashHandler().trash(user, workspace, database, table)
    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )
    assert usage == 0


@pytest.mark.django_db
def test_form_view_workspace_storage_usage_item_duplicate_ids(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    image = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)

    data_fixture.create_form_view(
        table=table,
        cover_image=image,
        logo_image=image,
    )

    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 2  # Instead of 4


@pytest.mark.django_db
def test_form_view_workspace_storage_usage_item_duplicate_ids_within_image_category(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    cover_image = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)
    logo_image = data_fixture.create_user_file(is_image=True, size=4 * USAGE_UNIT_MB)

    data_fixture.create_form_view(
        table=table,
        cover_image=cover_image,
        logo_image=logo_image,
    )

    data_fixture.create_form_view(
        table=table,
        cover_image=cover_image,
        logo_image=logo_image,
    )

    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 6  # Instead of 12


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_form_view_workspace_storage_usage_item_performance(data_fixture):
    form_views_amount = 1000

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    for i in range(form_views_amount):
        cover_image = data_fixture.create_user_file(
            is_image=True, size=2 * USAGE_UNIT_MB
        )
        logo_image = data_fixture.create_user_file(
            is_image=True, size=4 * USAGE_UNIT_MB
        )

        data_fixture.create_form_view(
            table=table,
            cover_image=cover_image,
            logo_image=logo_image,
        )

    profiler = Profiler()
    profiler.start()
    usage = FormViewWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )
    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))

    assert usage == form_views_amount * 6


@pytest.mark.django_db
def test_get_workspace_row_count_annotation_sums_all_database_tables_row_counts(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # One with no tables
    data_fixture.create_database_application(workspace=workspace)

    # One with a mix of tables with and without the count
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(user=user, database=database, row_count=10)
    data_fixture.create_database_table(user=user, database=database)

    # One with a single table
    database_single_table = data_fixture.create_database_application(
        workspace=workspace
    )
    data_fixture.create_database_table(
        user=user, database=database_single_table, row_count=50
    )

    # And a second workspace with its own different tables
    workspace2 = data_fixture.create_workspace(user=user)
    database_other_workspace = data_fixture.create_database_application(
        workspace=workspace2
    )
    data_fixture.create_database_table(
        user=user, database=database_other_workspace, row_count=1234
    )

    annotated_workspaces = Workspace.objects.annotate(
        row_count=UsageHandler.get_workspace_row_count_annotation()
    ).order_by("id")
    with django_assert_num_queries(1):
        assert list(annotated_workspaces.values("id", "row_count")) == [
            {"id": workspace.id, "row_count": 60},
            {"id": workspace2.id, "row_count": 1234},
        ]


@pytest.mark.django_db
def test_get_workspace_row_count_annotation_ignores_trashed_databases(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=workspace, trashed=True
    )
    data_fixture.create_database_table(user=user, database=database, row_count=10)
    data_fixture.create_database_table(user=user, database=database)

    annotated_workspaces = Workspace.objects.annotate(
        row_count=UsageHandler.get_workspace_row_count_annotation()
    )
    with django_assert_num_queries(1):
        assert list(annotated_workspaces.values("id", "row_count")) == [
            {"id": workspace.id, "row_count": 0},
        ]


@pytest.mark.django_db
def test_get_workspace_row_count_annotation_ignores_trashed_tables(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(user=user, database=database, row_count=10)
    data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_database_table(
        user=user, database=database, row_count=20, trashed=True
    )

    annotated_workspaces = Workspace.objects.annotate(
        row_count=UsageHandler.get_workspace_row_count_annotation()
    )
    with django_assert_num_queries(1):
        assert list(annotated_workspaces.values("id", "row_count")) == [
            {"id": workspace.id, "row_count": 10},
        ]
