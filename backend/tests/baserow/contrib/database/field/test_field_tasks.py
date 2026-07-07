from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.database.fields.field_types import FormulaFieldType
from baserow.contrib.database.fields.periodic_field_update_handler import (
    PeriodicFieldUpdateHandler,
)
from baserow.contrib.database.fields.tasks import (
    _split_into_batches,
    _update_workspace_periodic_fields,
    delete_mentions_marked_for_deletion,
    run_periodic_fields_updates,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.core.cache import local_cache
from baserow.core.models import Workspace
from baserow.core.trash.handler import TrashHandler


def create_table_with_row_in_workspace(data_fixture, workspace):
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    formula_field = data_fixture.create_formula_field(
        table=table, formula="now()", date_include_time=True
    )
    return table.get_model(), formula_field


@pytest.mark.django_db
def test_run_periodic_fields_updates_dispatches_only_eligible_workspaces(
    data_fixture, settings
):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    user = data_fixture.create_user()

    with freeze_time("2020-01-01 0:00"):
        workspace = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, workspace)
        workspace_2 = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, workspace_2)

        # workspace 1 recently used -> eligible
        PeriodicFieldUpdateHandler.mark_workspace_as_recently_used(workspace.id)
        workspace.refresh_now()
        # workspace 2 refreshed just now and not recently used -> not eligible yet
        workspace_2.refresh_now()

    with (
        patch(
            "baserow.contrib.database.fields.tasks."
            "update_workspaces_periodic_fields.delay"
        ) as delay,
        freeze_time("2020-01-01 00:04"),
    ):
        run_periodic_fields_updates()

    dispatched = {wid for call in delay.call_args_list for wid in call.args[0]}
    assert workspace.id in dispatched
    assert workspace_2.id not in dispatched


@pytest.mark.django_db
def test_run_periodic_fields_updates_dispatch_false_runs_inline(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    workspace = _workspace_with_now_formula(data_fixture)

    with (
        patch(
            "baserow.contrib.database.fields.tasks."
            "update_workspaces_periodic_fields.delay"
        ) as delay,
        patch(
            "baserow.contrib.database.fields.tasks._update_workspace_periodic_fields"
        ) as inline,
        freeze_time("2023-02-27 10:30"),
    ):
        run_periodic_fields_updates(workspace_id=workspace.id, dispatch=False)

    delay.assert_not_called()
    inline.assert_called_once_with(workspace.id, True)


@pytest.mark.django_db
def test_run_periodic_field_type_update_per_non_existing_workspace_does_nothing(
    django_assert_num_queries,
):
    with django_assert_num_queries(1):
        run_periodic_fields_updates(workspace_id=9999)


@pytest.mark.django_db
def test_run_periodic_fields_updates(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    user = data_fixture.create_user()

    def create_table_with_row_in_workspace(workspace):
        database = data_fixture.create_database_application(workspace=workspace)
        table = data_fixture.create_database_table(database=database)
        formula_field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )
        return table.get_model(), formula_field

    # when the workspace is created the now field is set to the current time
    with freeze_time("2023-02-27 9:55"):
        workspace = data_fixture.create_workspace(user=user)
        table_model, formula_field = create_table_with_row_in_workspace(workspace)
        row = RowHandler().create_row(
            user=user, table=table_model.baserow_table, model=table_model
        )

        workspace_2 = data_fixture.create_workspace(user=user)
        table_model_2, formula_field_2 = create_table_with_row_in_workspace(workspace_2)
        row_2 = RowHandler().create_row(
            user=user, table=table_model_2.baserow_table, model=table_model_2
        )

    assert getattr(row, f"field_{formula_field.id}") == datetime(
        2023, 2, 27, 9, 55, 0, tzinfo=timezone.utc
    )
    assert getattr(row_2, f"field_{formula_field_2.id}") == datetime(
        2023, 2, 27, 9, 55, 0, tzinfo=timezone.utc
    )

    # the now field is updated to the current time by default
    # and all the values updated accordingly
    with freeze_time("2023-02-27 10:00"):
        run_periodic_fields_updates()

    workspace.refresh_from_db()
    workspace_2.refresh_from_db()

    assert workspace.now == datetime(2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc)
    assert workspace_2.now == datetime(2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc)

    # the task can be run without updating the now field
    with freeze_time("2023-02-27 10:15"):
        run_periodic_fields_updates(update_now=False)

    workspace.refresh_from_db()
    workspace_2.refresh_from_db()

    assert workspace.now == datetime(2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc)
    assert workspace_2.now == datetime(2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_run_periodic_field_type_update_per_workspace(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    with freeze_time("2023-02-27 10:00"):
        field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )

    row = RowHandler().create_row(user=user, table=table)

    assert getattr(row, f"field_{field.id}") == datetime(
        2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc
    )

    with freeze_time("2023-02-27 10:30"), local_cache.context():
        run_periodic_fields_updates(workspace_id=workspace.id)

        row.refresh_from_db()
        assert getattr(row, f"field_{field.id}") == datetime(
            2023, 2, 27, 10, 30, 0, tzinfo=timezone.utc
        )

        workspace.refresh_from_db()
        assert workspace.now == datetime(2023, 2, 27, 10, 30, tzinfo=timezone.utc)


def _workspace_with_now_formula(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    with freeze_time("2023-02-27 10:00"):
        data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )
    RowHandler().create_row(user=user, table=table)
    return workspace


@pytest.mark.django_db
def test_update_workspace_periodic_fields_updates_now_fields(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    with freeze_time("2023-02-27 10:00"):
        field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )
    row = RowHandler().create_row(user=user, table=table)

    with freeze_time("2023-02-27 10:30"), local_cache.context():
        _update_workspace_periodic_fields(workspace.id)

    row.refresh_from_db()
    assert getattr(row, f"field_{field.id}") == datetime(
        2023, 2, 27, 10, 30, 0, tzinfo=timezone.utc
    )


def test_split_into_batches():
    # one batch by default keeps everything together, in order
    assert _split_into_batches([1, 2, 3, 4, 5], 1) == [[1, 2, 3, 4, 5]]
    # splits into contiguous, evenly sized (ceil) batches
    assert _split_into_batches([1, 2, 3, 4, 5], 2) == [[1, 2, 3], [4, 5]]
    assert _split_into_batches([1, 2, 3], 3) == [[1], [2], [3]]
    # never returns more batches than items or any empty batch
    assert _split_into_batches([1, 2], 5) == [[1], [2]]
    assert _split_into_batches([], 3) == []


@pytest.mark.django_db
def test_run_periodic_fields_updates_splits_into_configured_batches(
    data_fixture, settings
):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    settings.PERIODIC_FIELD_UPDATE_BATCH_COUNT = 2
    user = data_fixture.create_user()

    with freeze_time("2023-02-27 09:00"):
        ws_a = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, ws_a)
        ws_b = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, ws_b)
        ws_c = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, ws_c)

    Workspace.objects.filter(id=ws_a.id).update(
        now=datetime(2023, 2, 27, 8, 0, tzinfo=timezone.utc)
    )
    Workspace.objects.filter(id=ws_b.id).update(
        now=datetime(2023, 2, 27, 7, 0, tzinfo=timezone.utc)
    )
    Workspace.objects.filter(id=ws_c.id).update(
        now=datetime(2023, 2, 27, 9, 0, tzinfo=timezone.utc)
    )

    with (
        patch(
            "baserow.contrib.database.fields.tasks."
            "update_workspaces_periodic_fields.delay"
        ) as delay,
        freeze_time("2023-02-27 10:00"),
    ):
        run_periodic_fields_updates()

    # 3 stalest-first workspaces split into 2 batches, each tagged with its index
    assert delay.call_count == 2
    assert delay.call_args_list[0].args[0] == [ws_b.id, ws_a.id]
    assert delay.call_args_list[0].kwargs["batch_index"] == 0
    assert delay.call_args_list[1].args[0] == [ws_c.id]
    assert delay.call_args_list[1].kwargs["batch_index"] == 1


@pytest.mark.django_db
def test_update_workspace_periodic_fields_skips_missing_workspace():
    with patch(
        "baserow.contrib.database.fields.tasks."
        "_run_periodic_field_type_update_per_workspace"
    ) as inner:
        _update_workspace_periodic_fields(9999999)
    inner.assert_not_called()


@pytest.mark.django_db
def test_update_workspace_periodic_fields_records_histogram(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    workspace = _workspace_with_now_formula(data_fixture)

    with patch(
        "baserow.contrib.database.fields.tasks.periodic_field_update_workspace_duration"
    ) as hist:
        with freeze_time("2023-02-27 10:30"), local_cache.context():
            _update_workspace_periodic_fields(workspace.id)

    hist.record.assert_called_once()


@pytest.mark.django_db
def test_run_periodic_fields_updates_dispatches_stalest_first(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    user = data_fixture.create_user()

    with freeze_time("2023-02-27 09:00"):
        ws_a = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, ws_a)
        ws_b = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, ws_b)
        ws_c = data_fixture.create_workspace(user=user)
        create_table_with_row_in_workspace(data_fixture, ws_c)

    # b is the most out-of-date, then a, then c
    Workspace.objects.filter(id=ws_a.id).update(
        now=datetime(2023, 2, 27, 8, 0, tzinfo=timezone.utc)
    )
    Workspace.objects.filter(id=ws_b.id).update(
        now=datetime(2023, 2, 27, 7, 0, tzinfo=timezone.utc)
    )
    Workspace.objects.filter(id=ws_c.id).update(
        now=datetime(2023, 2, 27, 9, 0, tzinfo=timezone.utc)
    )

    with (
        patch(
            "baserow.contrib.database.fields.tasks."
            "update_workspaces_periodic_fields.delay"
        ) as delay,
        freeze_time("2023-02-27 10:00"),
    ):
        run_periodic_fields_updates()

    # default single batch keeps the most out-of-date workspaces first
    assert delay.call_count == 1
    assert delay.call_args_list[0].args[0] == [ws_b.id, ws_a.id, ws_c.id]


@pytest.mark.django_db
def test_run_periodic_fields_updates_records_dispatch_metric(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    _workspace_with_now_formula(data_fixture)

    with (
        patch(
            "baserow.contrib.database.fields.tasks."
            "periodic_field_update_dispatch_duration"
        ) as hist,
        patch(
            "baserow.contrib.database.fields.tasks."
            "update_workspaces_periodic_fields.delay"
        ),
        freeze_time("2023-02-27 10:30"),
    ):
        run_periodic_fields_updates()

    hist.record.assert_called_once()


@pytest.mark.django_db
def test_run_periodic_fields_updates_inline_skips_dispatch_metric(
    data_fixture, settings
):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    workspace = _workspace_with_now_formula(data_fixture)

    # dispatch=False (management command) must not pollute the dispatch metric
    with (
        patch(
            "baserow.contrib.database.fields.tasks."
            "periodic_field_update_dispatch_duration"
        ) as hist,
        patch(
            "baserow.contrib.database.fields.tasks._update_workspace_periodic_fields"
        ),
        freeze_time("2023-02-27 10:30"),
    ):
        run_periodic_fields_updates(workspace_id=workspace.id, dispatch=False)

    hist.record.assert_not_called()


@pytest.mark.django_db
def test_update_workspace_periodic_fields_warns_when_slow(data_fixture, settings):
    from loguru import logger

    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    workspace = _workspace_with_now_formula(data_fixture)

    messages = []
    sink_id = logger.add(messages.append, level="WARNING")
    try:
        # threshold 0 makes any duration count as slow
        with (
            patch(
                "baserow.contrib.database.fields.tasks."
                "SLOW_WORKSPACE_LOG_THRESHOLD_SECONDS",
                0,
            ),
            freeze_time("2023-02-27 10:30"),
            local_cache.context(),
        ):
            _update_workspace_periodic_fields(workspace.id)
    finally:
        logger.remove(sink_id)

    slow_logs = [m for m in messages if "took" in str(m)]
    assert len(slow_logs) == 1
    assert str(workspace.id) in str(slow_logs[0])


@pytest.mark.django_db
def test_run_field_type_updates_dependant_fields(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    with freeze_time("2023-02-27 10:15"):
        field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )
        dependant = data_fixture.create_formula_field(
            table=table, formula=f"field('{field.name}')", date_include_time=True
        )
        dependant_2 = data_fixture.create_formula_field(
            table=table, formula=f"field('{dependant.name}')", date_include_time=True
        )

    table_model = table.get_model()
    row = RowHandler().create_row(user=user, table=table, model=table_model)

    assert getattr(row, f"field_{field.id}") == datetime(
        2023, 2, 27, 10, 15, 0, tzinfo=timezone.utc
    )
    assert getattr(row, f"field_{dependant.id}") == datetime(
        2023, 2, 27, 10, 15, 0, tzinfo=timezone.utc
    )
    assert getattr(row, f"field_{dependant_2.id}") == datetime(
        2023, 2, 27, 10, 15, 0, tzinfo=timezone.utc
    )

    with freeze_time("2023-02-27 10:45"), local_cache.context():
        run_periodic_fields_updates(workspace_id=workspace.id)

        row.refresh_from_db()
        assert getattr(row, f"field_{field.id}") == datetime(
            2023, 2, 27, 10, 45, 0, tzinfo=timezone.utc
        )
        assert getattr(row, f"field_{dependant.id}") == datetime(
            2023, 2, 27, 10, 45, 0, tzinfo=timezone.utc
        )
        assert getattr(row, f"field_{dependant_2.id}") == datetime(
            2023, 2, 27, 10, 45, 0, tzinfo=timezone.utc
        )


@pytest.mark.django_db
def test_workspace_updated_last_will_be_updated_first_this_time(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 0
    user = data_fixture.create_user()

    def create_table_with_now_in_workspace(workspace):
        database = data_fixture.create_database_application(workspace=workspace)
        table = data_fixture.create_database_table(database=database)
        formula_field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )
        return table.get_model(), formula_field

    # when the workspace is created the now field is set to the current time
    now = datetime.now(tz=timezone.utc)
    workspace_updated_most_recently = data_fixture.create_workspace(user=user)
    workspace_updated_most_recently.now = now
    workspace_updated_most_recently.save()
    table_model, formula_field = create_table_with_now_in_workspace(
        workspace_updated_most_recently
    )
    row = table_model.objects.create()

    a_day_ago = datetime.now(tz=timezone.utc) - timedelta(days=1)
    workspace_that_should_be_updated_first_this_time = data_fixture.create_workspace(
        user=user
    )
    workspace_that_should_be_updated_first_this_time.now = a_day_ago
    workspace_that_should_be_updated_first_this_time.save()
    table_model_2, formula_field_2 = create_table_with_now_in_workspace(
        workspace_that_should_be_updated_first_this_time
    )
    row_2 = table_model_2.objects.create()

    assert a_day_ago < now
    assert a_day_ago == workspace_that_should_be_updated_first_this_time.now
    assert (
        workspace_that_should_be_updated_first_this_time.now
        < workspace_updated_most_recently.now
    )

    run_periodic_fields_updates()

    workspace_updated_most_recently.refresh_from_db()
    workspace_that_should_be_updated_first_this_time.refresh_from_db()

    assert workspace_that_should_be_updated_first_this_time.now != a_day_ago
    assert workspace_updated_most_recently.now != now
    # The first workspace that got updated will have the lowest now value
    assert (
        workspace_that_should_be_updated_first_this_time.now
        < workspace_updated_most_recently.now
    )


@pytest.mark.django_db
def test_one_formula_failing_doesnt_block_others(data_fixture, settings):
    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 0
    user = data_fixture.create_user()

    def create_table_with_now_in_workspace(workspace):
        database = data_fixture.create_database_application(workspace=workspace)
        table = data_fixture.create_database_table(database=database)
        formula_field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )
        return table.get_model(), formula_field

    # when the workspace is created the now field is set to the current time
    now = datetime.now(tz=timezone.utc)
    second_updated_workspace = data_fixture.create_workspace(user=user)
    second_updated_workspace.now = now
    second_updated_workspace.save()
    table_model, working_other_formula = create_table_with_now_in_workspace(
        second_updated_workspace
    )
    row = RowHandler().create_row(
        user=user, table=table_model.baserow_table, model=table_model
    )

    a_day_ago = datetime.now(tz=timezone.utc) - timedelta(days=1)
    first_updated_workspace = data_fixture.create_workspace(user=user)
    first_updated_workspace.now = a_day_ago
    first_updated_workspace.save()
    table_model_2, broken_first_formula = create_table_with_now_in_workspace(
        first_updated_workspace
    )
    row_2 = RowHandler().create_row(
        user=user, table=table_model_2.baserow_table, model=table_model_2
    )
    broken_first_formula.internal_formula = "broken"
    broken_first_formula.save(recalculate=False)

    assert a_day_ago < now
    assert a_day_ago == first_updated_workspace.now
    assert first_updated_workspace.now < second_updated_workspace.now

    assert getattr(row, f"field_{working_other_formula.id}") == now
    assert getattr(row_2, f"field_{broken_first_formula.id}") == a_day_ago

    with local_cache.context():
        run_periodic_fields_updates()

    row_2.refresh_from_db()
    # It didn't get refreshed
    assert getattr(row_2, f"field_{broken_first_formula.id}") == a_day_ago
    row.refresh_from_db()
    # It did get refreshed
    assert getattr(row, f"field_{working_other_formula.id}") != now

    second_updated_workspace.refresh_from_db()
    first_updated_workspace.refresh_from_db()

    assert first_updated_workspace.now != a_day_ago
    assert second_updated_workspace.now != now
    assert first_updated_workspace.now < second_updated_workspace.now


@pytest.mark.django_db
def test_all_formula_that_needs_updates_are_periodically_updated(data_fixture):
    workspace = data_fixture.create_workspace()

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    with freeze_time("2023-02-27 10:15"):
        now_field = data_fixture.create_formula_field(
            name="now", table=table, formula="now()", date_include_time=True
        )
        data_fixture.create_formula_field(
            name="ref_now",
            table=table,
            formula=f"field('{now_field.name}')",
            date_include_time=True,
        )

        date_field = data_fixture.create_date_field(table=table, date_include_time=True)
        data_fixture.create_formula_field(
            name="now_vs_date",
            table=table,
            formula=f"now() > field('{date_field.name}')",
            date_include_time=True,
        )

        assert FormulaFieldType().get_fields_needing_periodic_update().count() == 2


@pytest.mark.django_db
def test_run_periodic_field_type_doesnt_update_trashed_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    original_datetime = datetime(2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc)

    with freeze_time(original_datetime):
        field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )

    row = RowHandler().create_row(user=user, table=table)

    assert getattr(row, f"field_{field.id}") == original_datetime

    TrashHandler.trash(user, workspace, database, table)

    with freeze_time("2023-02-27 10:30"):
        run_periodic_fields_updates(workspace_id=workspace.id)

        row.refresh_from_db()
        assert getattr(row, f"field_{field.id}") == original_datetime

        assert FormulaFieldType().get_fields_needing_periodic_update().count() == 0


@pytest.mark.django_db
def test_run_periodic_field_type_doesnt_update_trashed_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    original_datetime = datetime(2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc)

    with freeze_time(original_datetime):
        field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )

    row = RowHandler().create_row(user=user, table=table)

    assert getattr(row, f"field_{field.id}") == original_datetime

    TrashHandler.trash(user, workspace, database, database)

    with freeze_time("2023-02-27 10:30"):
        run_periodic_fields_updates(workspace_id=workspace.id)

        row.refresh_from_db()
        assert getattr(row, f"field_{field.id}") == original_datetime

        assert FormulaFieldType().get_fields_needing_periodic_update().count() == 0


@pytest.mark.django_db
def test_run_periodic_field_type_doesnt_update_trashed_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    original_datetime = datetime(2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc)

    with freeze_time(original_datetime):
        field = data_fixture.create_formula_field(
            table=table, formula="now()", date_include_time=True
        )

    row = RowHandler().create_row(user=user, table=table)

    assert getattr(row, f"field_{field.id}") == original_datetime

    TrashHandler.trash(user, workspace, None, workspace)

    with freeze_time("2023-02-27 10:30"):
        run_periodic_fields_updates(workspace_id=workspace.id)

        row.refresh_from_db()
        assert getattr(row, f"field_{field.id}") == original_datetime

        assert FormulaFieldType().get_fields_needing_periodic_update().count() == 0


@override_settings(STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES=60)
@pytest.mark.django_db
def test_run_delete_mentions_marked_for_deletion(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    rich_text_field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )
    model = table.get_model()

    # Create a user mention
    with freeze_time("2023-02-27 9:00"):
        row_1, row_2 = (
            RowHandler()
            .create_rows(
                user=user,
                table=table,
                rows_values=[
                    {f"field_{rich_text_field.id}": f"Hello @{user.id}!"},
                    {f"field_{rich_text_field.id}": f"Hi @{user.id}!"},
                ],
                model=model,
            )
            .created_rows
        )

    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 2
    assert mentions[0].marked_for_deletion_at is None
    assert mentions[1].marked_for_deletion_at is None

    with freeze_time("2023-02-27 10:00"):
        RowHandler().update_rows(
            user=user,
            table=table,
            rows_values=[{"id": row_1.id, f"field_{rich_text_field.id}": "Bye!"}],
            model=model,
        )

    mentions = RichTextFieldMention.objects.order_by("row_id")
    assert len(mentions) == 2
    assert mentions[0].marked_for_deletion_at == datetime(
        2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc
    )
    assert mentions[1].marked_for_deletion_at is None

    with freeze_time("2023-02-27 11:00"):
        RowHandler().update_rows(
            user,
            table,
            [{"id": row_2.id, f"field_{rich_text_field.id}": "Bye!"}],
        )

    mentions = RichTextFieldMention.objects.order_by("row_id")
    assert len(mentions) == 2
    assert mentions[0].marked_for_deletion_at == datetime(
        2023, 2, 27, 10, 0, 0, tzinfo=timezone.utc
    )
    assert mentions[1].marked_for_deletion_at == datetime(
        2023, 2, 27, 11, 0, 0, tzinfo=timezone.utc
    )

    # Since STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES=60, only mentions
    # marked for deletion before 10:30 will be deleted
    with freeze_time("2023-02-27 11:30"):
        delete_mentions_marked_for_deletion()

    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row_2.id
    assert mentions[0].marked_for_deletion_at == datetime(
        2023, 2, 27, 11, 0, 0, tzinfo=timezone.utc
    )

    # Delete also the other mention
    with freeze_time("2023-02-27 12:30"):
        delete_mentions_marked_for_deletion()

    assert RichTextFieldMention.objects.count() == 0


@pytest.mark.django_db
def test_link_row_fields_deps_are_excluded_from_periodic_updates(data_fixture):
    # Fixes https://gitlab.com/baserow/baserow/-/issues/3379
    with freeze_time("2023-01-01"):
        table_b = data_fixture.create_database_table()
        primary_b = data_fixture.create_formula_field(
            table=table_b, primary=True, formula="now()"
        )
        table_a = data_fixture.create_database_table(database=table_b.database)
        link_a_to_b = data_fixture.create_link_row_field(
            table=table_a, link_row_table=table_b
        )
        formula_a = data_fixture.create_formula_field(
            table=table_a,
            formula=f"join(datetime_format(field('{link_a_to_b.name}'), 'DD'), ',')",
        )
        row_b = RowHandler().force_create_row(None, table_b, {})
        row_a = RowHandler().force_create_row(
            None, table_a, {link_a_to_b.db_column: [row_b.id]}
        )

    with freeze_time("2023-01-02"), local_cache.context():
        run_periodic_fields_updates()

    row_a.refresh_from_db()
    assert getattr(row_a, formula_a.db_column) == "02"


@pytest.mark.django_db
def test_invalid_formula_is_skipped_by_periodic_update(data_fixture):
    table = data_fixture.create_database_table()
    date_field = data_fixture.create_date_field(table=table, date_include_time=True)
    bool_formula = data_fixture.create_formula_field(
        table=table,
        formula=f"today() > field('{date_field.name}')",
    )
    data_fixture.create_formula_field(
        table=table,
        formula=f"if(field('{bool_formula.name}'), 'YES', 'NO')",
    )

    assert bool_formula.needs_periodic_update is True
    assert bool_formula.formula_type == "boolean"

    bool_formula.mark_as_invalid_and_save("simulated invalid state")
    bool_formula.refresh_from_db()
    assert bool_formula.formula_type == "invalid"
    assert bool_formula.needs_periodic_update is True

    assert FormulaFieldType().get_fields_needing_periodic_update().exists() is False


@pytest.mark.django_db
def test_cross_table_dependent_formulas_update_when_multiple_tables_have_now(
    data_fixture,
):
    with freeze_time("2023-01-01"):
        database = data_fixture.create_database_application()

        table_b = data_fixture.create_database_table(database=database)
        primary_b = data_fixture.create_formula_field(
            table=table_b, primary=True, formula="now()"
        )

        table_a = data_fixture.create_database_table(database=database)
        link_a_to_b = data_fixture.create_link_row_field(
            table=table_a, link_row_table=table_b
        )
        formula_a = data_fixture.create_formula_field(
            table=table_a,
            formula=(f"join(datetime_format(field('{link_a_to_b.name}'), 'DD'), ',')"),
        )

        # Second formula with now()
        now_in_a = data_fixture.create_formula_field(
            table=table_a,
            formula="datetime_format(now(), 'YYYY-MM-DD')",
        )

        row_b = RowHandler().force_create_row(None, table_b, {})
        row_a = RowHandler().force_create_row(
            None, table_a, {link_a_to_b.db_column: [row_b.id]}
        )

    with freeze_time("2023-01-02"), local_cache.context():
        run_periodic_fields_updates()

    row_a.refresh_from_db()
    assert getattr(row_a, formula_a.db_column) == "02"


@pytest.mark.django_db
def test_run_periodic_fields_updates_command_runs_inline(data_fixture, settings):
    from django.core.management import call_command

    settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN = 5
    workspace = _workspace_with_now_formula(data_fixture)

    with patch(
        "baserow.contrib.database.fields.tasks._update_workspace_periodic_fields"
    ) as inline:
        with freeze_time("2023-02-27 10:30"):
            call_command("run_periodic_fields_updates", workspace_id=workspace.id)

    inline.assert_called_once_with(workspace.id, True)
