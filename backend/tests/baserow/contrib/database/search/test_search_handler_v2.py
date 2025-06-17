import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.models import WorkspaceDatabaseSettings
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.search_bulder import SearchBuilder
from baserow.contrib.database.search.types import SearchTableState
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.mark.django_db
def test_search_workspace_table(data_fixture, run_on_commit):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    assert workspace.workspacedatabasesettings is not None
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    assert workspace.workspacedatabasesettings is not None
    workspace_settings = WorkspaceDatabaseSettings.objects.get(
        workspace_id=workspace.id
    )
    workspace_settings.delete()

    SearchHandler.create_search_table_for_workspace(workspace.id)

    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.READY},
    )

    model = table.get_model()

    assert len(model.objects.all()) == 2

    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)
    assert len(search_table.objects.all()) == 0  # no data yet
    run_on_commit()
    assert len(search_table.objects.all()) > 0  # no data yet


@pytest.mark.django_db
def test_create_tsvector_table(data_fixture, run_on_commit):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)

    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.READY},
    )

    model = table.get_model()
    assert len(model.objects.all()) == 2
    run_on_commit()
    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)

    assert len(search_table.objects.all()) > 0

    sbuilder = SearchBuilder(table)
    sbuilder.add_term("example")
    q = sbuilder.get_queryset()
    assert len(q) == 1


@pytest.mark.django_db
def test_update_and_cleanup_tsvector_table(data_fixture, run_on_commit):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.READY},
    )

    run_on_commit()
    model: GeneratedTableModel = table.get_model()

    assert len(model.objects.all()) == 2

    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)

    assert len(search_table.objects.all()) > 0

    # ensure update is queryable
    sbuilder = SearchBuilder(table)
    sbuilder.add_term("example")
    q = sbuilder.get_queryset()
    assert len(q) == 1

    long_text_field = model.get_field_object_by_user_field_name("long_text")
    email_field = model.get_field_object_by_user_field_name("email")
    field_ids = [
        f["field"].id
        for f in (
            long_text_field,
            email_field,
        )
    ]

    RowHandler().update_row_by_id(
        user=user,
        table=table,
        row_id=inserted_row.id,
        values={
            long_text_field["field"].id: "foobar",
            email_field["field"].id: "bar@foo.com",
        },
    )

    run_on_commit()

    sbuilder = SearchBuilder(table)
    sbuilder.add_term("example", field_ids=field_ids)
    q = sbuilder.get_queryset()

    assert len(q) == 0

    sbuilder = SearchBuilder(table)
    sbuilder.add_term("foobar")
    q = sbuilder.get_queryset()

    assert len(q) == 1


@pytest.mark.django_db
def test_search_builder_api(data_fixture, run_on_commit):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.READY},
    )

    run_on_commit()
    model: GeneratedTableModel = table.get_model()

    long_text_field = model.get_field_object_by_user_field_name("long_text")
    email_field = model.get_field_object_by_user_field_name("email")
    field_ids = [
        f["field"].id
        for f in (
            long_text_field,
            email_field,
        )
    ]
    sbuilder = SearchBuilder(table)
    sbuilder.add_term("example", field_ids=field_ids)
    q = sbuilder.get_queryset()
    assert len(q.filter(id=inserted_row.id)) == 1

    RowHandler().update_row_by_id(
        user=user,
        table=table,
        row_id=inserted_row.id,
        values={
            long_text_field["field"].id: "foobar",
            email_field["field"].id: "bar@foo.com",
        },
    )
    # post update: example not searchable
    run_on_commit()
    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)

    sbuilder = SearchBuilder(table)
    sbuilder.add_term("example", field_ids=field_ids)
    q = sbuilder.get_queryset()
    assert len(q.filter(id=inserted_row.id)) == 0

    sbuilder = SearchBuilder(table)
    sbuilder.add_term("foobar", field_ids=[email_field["field"].id])
    q = sbuilder.get_queryset()

    assert len(q) == 0

    sbuilder.add_term("foobar", field_ids=[long_text_field["field"].id])
    q = sbuilder.get_queryset()

    assert len(q) == 1


@pytest.mark.django_db
def test_change_field_and_search_table(data_fixture, run_on_commit):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.READY},
    )

    run_on_commit()
    model: GeneratedTableModel = table.get_model()

    assert len(model.objects.all()) == 2

    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)

    email_field = model.get_field_object_by_user_field_name("email")
    assert len(search_table.objects.all()) > 0

    # ensure update is queryable
    sbuilder = SearchBuilder(table)
    sbuilder.add_term("test@example.com", field_ids=[email_field["field"].id])
    q = sbuilder.get_queryset()
    assert len(q) == 1

    FieldHandler().update_field(
        user=user,
        table=table,
        field=email_field["field"],
        new_type_name="number",
    )

    model = table.get_model()
    email_field = model.get_field_object_by_user_field_name("email")

    FieldHandler().update_field(
        user=user,
        table=table,
        field=email_field["field"],
        new_type_name="long_text",
    )

    run_on_commit()
    model = table.get_model()
    # email field has changed, so we need to
    email_field = model.get_field_object_by_user_field_name("email")

    sbuilder = SearchBuilder(table)
    sbuilder.add_term("test@example.com", field_ids=[email_field["field"].id])
    q = sbuilder.get_queryset()

    assert len(q) == 0
