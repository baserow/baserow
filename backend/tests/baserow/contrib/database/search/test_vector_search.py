from unittest.mock import patch

from django.db import connection
from django.test import override_settings

import pytest

from baserow.contrib.database.fields.exceptions import (
    VectorSearchNotAvailableError,
    VectorSearchNotSupportedError,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.models import (
    PendingSearchValueUpdate,
    WorkspaceSearchTable,
)
from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS, is_pgvector_enabled

EMBEDDINGS_URL = "http://embeddings.test"


def fake_embedder(texts):
    """Unit vectors on a different axis per topic, so cosine ranking is exact."""

    vectors = []
    for text in texts:
        vector = [0.0] * DEFAULT_EMBEDDING_DIMENSIONS
        lowered = text.lower()
        if "fruit" in lowered:
            vector[0] = 1.0
        elif "vehicle" in lowered:
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        vectors.append(vector)
    return vectors


class CountingEmbedder:
    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return fake_embedder(texts)


@pytest.fixture
def vector_table(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    with override_settings(BASEROW_EMBEDDINGS_API_URL=EMBEDDINGS_URL):
        field = FieldHandler().create_field(
            user, table, "long_text", name="Notes", vector_search_enabled=True
        )
    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": "A basket of fruit"},
                {f"field_{field.id}": "A vehicle in the garage"},
                {f"field_{field.id}": "Something else entirely"},
                {f"field_{field.id}": ""},
            ],
        )
        .created_rows
    )
    SearchHandler.update_search_data(table)
    return user, table, field, rows


def _search_rows(table, field):
    search_table = SearchHandler.get_workspace_search_table_name(
        table.database.workspace_id
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT row_id, embedding IS NOT NULL, embedding_hash FROM {search_table} "  # noqa: S608
            "WHERE field_id = %s ORDER BY row_id",
            [field.id],
        )
        return cursor.fetchall()


@pytest.mark.django_db
def test_vector_search_option_needs_a_supported_type_and_an_instance_setup(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    with pytest.raises(VectorSearchNotSupportedError):
        FieldHandler().create_field(
            user, table, "text", name="Name", vector_search_enabled=True
        )

    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        with pytest.raises(VectorSearchNotAvailableError):
            FieldHandler().create_field(
                user, table, "long_text", name="Notes", vector_search_enabled=True
            )

    # The API wraps a create in a transaction; here the failed attempt's row
    # remains, so another name is used.
    field = FieldHandler().create_field(user, table, "long_text", name="Notes 2")
    assert field.vector_search_enabled is False


@pytest.mark.django_db
def test_toggling_vector_search_schedules_a_full_field_update(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = FieldHandler().create_field(user, table, "long_text", name="Notes")

    with (
        override_settings(BASEROW_EMBEDDINGS_API_URL=EMBEDDINGS_URL),
        patch.object(SearchHandler, "schedule_update_search_data") as schedule,
    ):
        FieldHandler().update_field(user, field, vector_search_enabled=True)
        schedule.assert_called_once()
        assert [f.id for f in schedule.call_args.kwargs["fields"]] == [field.id]

        schedule.reset_mock()
        FieldHandler().update_field(user, field, name="Renamed")
        schedule.assert_not_called()


@pytest.mark.django_db
def test_search_table_gets_its_embedding_columns_once(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    workspace_id = table.database.workspace_id

    assert SearchHandler.vector_search_ready(workspace_id) is False
    assert SearchHandler.ensure_workspace_search_table_columns(workspace_id) is True
    assert SearchHandler.vector_search_ready(workspace_id) is True
    state = WorkspaceSearchTable.objects.get(workspace_id=workspace_id)
    assert state.embedding_columns_added is True

    search_table = SearchHandler.get_workspace_search_table_name(workspace_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_name IN ('embedding', 'embedding_hash')",
            [search_table],
        )
        assert {row[0] for row in cursor.fetchall()} == {"embedding", "embedding_hash"}
    # Running it again is a no-op.
    assert SearchHandler.ensure_workspace_search_table_columns(workspace_id) is True


@pytest.mark.django_db
def test_update_embeddings_stores_vectors_and_skips_unchanged_cells(vector_table):
    user, table, field, rows = vector_table
    embedder = CountingEmbedder()

    assert SearchHandler.update_embeddings(table, [field.id], embedder=embedder)
    # The empty cell gets a hash but no vector, so it is not embedded again.
    assert [
        (has_vector, bool(h)) for _, has_vector, h in _search_rows(table, field)
    ] == [
        (True, True),
        (True, True),
        (True, True),
        (False, True),
    ]
    assert sum(len(call) for call in embedder.calls) == 3

    assert SearchHandler.update_embeddings(table, [field.id], embedder=embedder)
    assert sum(len(call) for call in embedder.calls) == 3

    RowHandler().update_rows(
        user, table, [{"id": rows[2].id, f"field_{field.id}": "Fresh fruit"}]
    )
    SearchHandler.update_search_data(table, row_ids=[rows[2].id])
    assert SearchHandler.update_embeddings(
        table, [field.id], row_ids=[rows[2].id], embedder=embedder
    )
    assert embedder.calls[-1] == ["Fresh fruit"]


@pytest.mark.django_db
def test_vector_search_mixes_semantic_and_lexical_hits(vector_table):
    user, table, field, rows = vector_table
    SearchHandler.update_embeddings(table, [field.id], embedder=fake_embedder)

    with override_settings(BASEROW_EMBEDDINGS_API_URL=EMBEDDINGS_URL):
        hits = SearchHandler.vector_search(
            table, field, "fruit", limit=2, embedder=fake_embedder
        )
    assert hits[0] == (rows[0].id, 1.0)
    assert len(hits) == 2
    # "garage" is a lexical hit even though the fake vectors put it elsewhere.
    hits = SearchHandler.vector_search(
        table, field, "garage", limit=3, embedder=fake_embedder
    )
    assert rows[1].id in [row_id for row_id, _ in hits]
    assert (
        SearchHandler.vector_search(table, field, "   ", embedder=fake_embedder) == []
    )


@pytest.mark.django_db
def test_disabling_vector_search_clears_the_embeddings(vector_table):
    user, table, field, rows = vector_table
    SearchHandler.update_embeddings(table, [field.id], embedder=fake_embedder)
    assert all(has_vector for _, has_vector, _ in _search_rows(table, field)[:3])

    field = FieldHandler().update_field(user, field, vector_search_enabled=False)
    SearchHandler.update_embeddings(table, [field.id], embedder=fake_embedder)
    assert not any(has_vector for _, has_vector, _ in _search_rows(table, field))


@pytest.mark.django_db
def test_pending_updates_survive_a_failing_embeddings_service(vector_table):
    user, table, field, rows = vector_table
    PendingSearchValueUpdate.objects.create(field_id=field.id, row_id=None)

    def broken(texts):
        raise ConnectionError("down")

    with patch(
        "baserow.contrib.database.search.handler.get_embedder", return_value=broken
    ):
        # Completed from the task's point of view: nothing is rescheduled in a
        # tight loop, the periodic check retries later.
        assert SearchHandler.process_search_data_updates(table) is True
    assert PendingSearchValueUpdate.objects.filter(field_id=field.id).exists()

    with patch(
        "baserow.contrib.database.search.handler.get_embedder",
        return_value=fake_embedder,
    ):
        assert SearchHandler.process_search_data_updates(table) is True
    assert not PendingSearchValueUpdate.objects.filter(field_id=field.id).exists()
    assert all(has_vector for _, has_vector, _ in _search_rows(table, field)[:3])
