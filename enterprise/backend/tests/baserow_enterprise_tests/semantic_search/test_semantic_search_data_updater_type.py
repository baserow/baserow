import time
from unittest.mock import patch

from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.models import PendingSearchValueUpdate
from baserow.contrib.database.search.tasks import (
    periodic_check_pending_search_data,
    schedule_search_data_updater_task,
    schedule_update_search_data,
)
from baserow.core.embeddings import BaserowEmbedder
from baserow_enterprise.semantic_search.handler import SemanticSearchHandler
from baserow_enterprise.semantic_search.models import (
    SemanticSearchField,
    SemanticSearchPendingUpdate,
)
from baserow_enterprise.semantic_search.search_data_updater_types import (
    SemanticSearchDataUpdaterType,
)

from .utils import enable_search_data_updates, get_chunk_counts


@pytest.mark.django_db
def test_periodic_check_indexes_pending_semantic_search_updates(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Text", "text")], rows=[["first"], ["second"]]
    )
    # Queued, but the scheduled task is lost, like when a worker restarts.
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    assert get_chunk_counts(fields[0]) == {}

    periodic_check_pending_search_data()

    assert get_chunk_counts(fields[0]) == {row.id: 1 for row in rows}
    assert not SemanticSearchPendingUpdate.objects.exists()


@pytest.mark.django_db
@enable_search_data_updates
def test_full_text_search_doesnt_wait_for_semantic_search(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Text", "text")], rows=[["first"]]
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)

    # Semantic search can't index now, so its updates are kept.
    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        schedule_update_search_data(table.id, row_ids=[rows[0].id])

    search_model = SearchHandler.get_workspace_search_table_model(
        table.database.workspace_id
    )
    assert search_model.objects.filter(
        field_id=fields[0].id, row_id=rows[0].id
    ).exists()
    assert not PendingSearchValueUpdate.objects.exists()
    assert SemanticSearchPendingUpdate.objects.filter(field_id=fields[0].id).exists()


@pytest.mark.django_db
def test_queuing_changes_without_semantic_search_fields_only_checks_the_fields(
    data_fixture, semantic_search, django_assert_num_queries
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Text", "text")], rows=[["first"]]
    )
    search_data_updater_type = SemanticSearchHandler().get_search_data_updater_type()

    # The license isn't checked, because this runs for every change of every table.
    with django_assert_num_queries(1):
        queued = search_data_updater_type.queue(table, [fields[0].id], [rows[0].id])

    assert not queued
    assert not SemanticSearchPendingUpdate.objects.exists()


@pytest.mark.django_db
def test_rescheduling_only_starts_types_with_pending_updates(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Text", "text")], rows=[["first"]]
    )

    with patch.object(
        SemanticSearchDataUpdaterType,
        "update",
        autospec=True,
        side_effect=SemanticSearchDataUpdaterType.update,
    ) as update:
        # Like full-text search rescheduling itself after its time budget.
        schedule_update_search_data(table.id)
        assert update.call_count == 0

        FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
        schedule_update_search_data(table.id)
        assert update.call_count == 1

    assert get_chunk_counts(fields[0]) == {rows[0].id: 1}


@pytest.mark.django_db
@enable_search_data_updates
@override_settings(BASEROW_SEMANTIC_SEARCH_TASK_TIME_BUDGET_SECONDS=1)
def test_update_of_all_rows_continues_after_the_time_budget(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Notes", "text")],
        rows=[[f"value {number}"] for number in range(150)],
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    search_data_updater_type = SemanticSearchHandler().get_search_data_updater_type()

    def slow_embedder(texts):
        # The time budget runs out while the first texts are embedded.
        if not semantic_search.embedded_texts:
            time.sleep(1.1)
        return semantic_search(texts)

    with (
        patch(
            "baserow_enterprise.semantic_search.handler.get_embedder",
            return_value=slow_embedder,
        ),
        patch.object(schedule_search_data_updater_task, "apply_async") as reschedule,
    ):
        search_data_updater_type.update(table.id)

        reschedule.assert_called_once_with(
            (SemanticSearchDataUpdaterType.type, table.id), countdown=0
        )
        indexed_row_ids = list(get_chunk_counts(fields[0]))
        assert 0 < len(indexed_row_ids) < 150
        assert SemanticSearchPendingUpdate.objects.get().processed_until_row_id == (
            max(indexed_row_ids)
        )

        # Changing a row that was already indexed continues the update as well.
        with django_capture_on_commit_callbacks(execute=True):
            RowHandler().update_row_by_id(
                user, table, rows[0].id, {fields[0].db_column: "changed"}
            )

    assert get_chunk_counts(fields[0]) == {row.id: 1 for row in rows}
    assert sorted(semantic_search.embedded_texts) == sorted(
        [f"value {number}" for number in range(150)] + ["changed"]
    )
    assert not SemanticSearchPendingUpdate.objects.exists()


@pytest.mark.django_db
def test_failing_embeddings_service_is_retried_later(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"]]
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    search_data_updater_type = SemanticSearchHandler().get_search_data_updater_type()
    # Nothing listens on this port, so the real client fails to connect.
    unreachable_embedder = BaserowEmbedder("http://127.0.0.1:9")

    def run_updates(count: int = 1, embedder=None) -> list[int]:
        """
        :return: The countdowns after which the updates are retried.
        """

        with (
            patch(
                "baserow_enterprise.semantic_search.handler.get_embedder",
                return_value=embedder or semantic_search,
            ),
            patch.object(
                schedule_search_data_updater_task, "apply_async"
            ) as reschedule,
        ):
            for _ in range(count):
                search_data_updater_type.update(table.id)
        assert all(
            call.args[0] == (SemanticSearchDataUpdaterType.type, table.id)
            for call in reschedule.call_args_list
        )
        return [call.kwargs["countdown"] for call in reschedule.call_args_list]

    def change_row(value: str):
        RowHandler().update_row_by_id(
            user, table, rows[0].id, {fields[0].db_column: value}
        )
        search_data_updater_type.queue(table, [fields[0].id], [rows[0].id])

    with freeze_time() as frozen_time:
        assert run_updates() == []
        change_row("second")
        assert run_updates(embedder=unreachable_embedder) == [60]

        # Changes don't make it try before the retry.
        change_row("third")
        assert run_updates() == []
        assert semantic_search.embedded_texts == ["first"]

        frozen_time.tick(60)
        assert run_updates() == []
        assert semantic_search.embedded_texts == ["first", "third"]

        # A failure after a recovery is retried soon again.
        change_row("fourth")
        countdowns = []
        for _ in range(3):
            countdowns += run_updates(embedder=unreachable_embedder)
            frozen_time.tick(countdowns[-1])
        assert countdowns == [60, 120, 240]
        assert SemanticSearchField.objects.get().status == "error"
        assert SemanticSearchPendingUpdate.objects.exists()

        assert run_updates() == []
        assert SemanticSearchField.objects.get().status == "ready"
        assert semantic_search.embedded_texts == ["first", "third", "fourth"]
