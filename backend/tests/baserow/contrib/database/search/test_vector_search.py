from unittest.mock import patch

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import httpx
import pytest

from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.exceptions import (
    VectorSearchNotAvailableError,
    VectorSearchNotSupportedError,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.utils.deferred_foreign_key_updater import (
    DeferredForeignKeyUpdater,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.models import (
    PendingSearchValueUpdate,
    WorkspaceSearchTable,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.embeddings import (
    EMBEDDING_TEXT_LIMIT,
    BaserowEmbedder,
    EmbeddingsServiceError,
)
from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS, is_pgvector_enabled
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid

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


def _embedding_index_valid(workspace_id):
    """None when the HNSW index is absent, else whether it is usable."""

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT i.indisvalid FROM pg_index i "
            "JOIN pg_class c ON c.oid = i.indexrelid WHERE c.relname = %s",
            [f"database_search_workspace_{workspace_id}_embedding_idx"],
        )
        row = cursor.fetchone()
    return row[0] if row else None


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


@pytest.mark.django_db
def test_full_field_update_without_vector_search_adds_no_embedding_columns(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(table=table, name="Notes")
    RowHandler().create_rows(
        user, table, rows_values=[{f"field_{field.id}": "Some text"}]
    )
    SearchHandler.update_search_data(table)
    workspace_id = table.database.workspace_id

    # A full-field run, like the first one after upgrading.
    assert SearchHandler.update_embeddings(table, [field.id]) is True
    assert not WorkspaceSearchTable.objects.filter(workspace_id=workspace_id).exists()
    assert _embedding_index_valid(workspace_id) is None


@pytest.mark.django_db(transaction=True)
def test_embedding_index_is_built_concurrently_outside_a_transaction(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    workspace = data_fixture.create_workspace()
    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    try:
        assert not connection.in_atomic_block
        with CaptureQueriesContext(connection) as queries:
            assert SearchHandler.ensure_workspace_search_table_columns(workspace.id)
        assert any(
            "CREATE INDEX CONCURRENTLY" in q["sql"] for q in queries.captured_queries
        )
        assert _embedding_index_valid(workspace.id) is True
    finally:
        SearchHandler.delete_workspace_search_table_if_exists(workspace.id)


@pytest.mark.django_db
def test_deleting_the_search_table_forgets_its_embedding_columns(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    workspace = data_fixture.create_workspace()
    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    assert SearchHandler.ensure_workspace_search_table_columns(workspace.id) is True

    SearchHandler.delete_workspace_search_table_if_exists(workspace.id)
    assert SearchHandler.vector_search_ready(workspace.id) is False
    assert not WorkspaceSearchTable.objects.filter(workspace_id=workspace.id).exists()

    # A re-created table gets its columns and index again.
    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    assert SearchHandler.ensure_workspace_search_table_columns(workspace.id) is True
    assert _embedding_index_valid(workspace.id) is True


@pytest.mark.django_db
def test_vector_search_is_not_capped_by_the_default_hnsw_ef_search(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    with override_settings(BASEROW_EMBEDDINGS_API_URL=EMBEDDINGS_URL):
        first = FieldHandler().create_field(
            user, table, "long_text", name="First", vector_search_enabled=True
        )
        second = FieldHandler().create_field(
            user, table, "long_text", name="Second", vector_search_enabled=True
        )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{first.id}": f"Row {i}", f"field_{second.id}": f"Other {i}"}
            for i in range(60)
        ],
    )
    SearchHandler.update_search_data(table)

    def axis_embedder(texts):
        # Every text on its own axis: nothing is close to the query and no
        # two vectors are equal, so the count only depends on how many rows
        # the index scan hands back.
        vectors = []
        for text in texts:
            vector = [0.0] * DEFAULT_EMBEDDING_DIMENSIONS
            axis = 0 if text == "fruit" else 1 + hash(text) % 700
            vector[axis] = 1.0
            vectors.append(vector)
        return vectors

    SearchHandler.update_embeddings(
        table, [first.id, second.id], embedder=axis_embedder
    )
    with connection.cursor() as cursor:
        # A table this small would otherwise be scanned sequentially, which
        # hides the cap of the index scan.
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("SET LOCAL enable_sort = off")
    hits = SearchHandler.vector_search(
        table, first, "fruit", limit=50, embedder=axis_embedder
    )
    assert len(hits) == 50


@pytest.mark.django_db
def test_embedding_text_is_truncated_in_the_database(vector_table):
    user, table, field, rows = vector_table
    RowHandler().update_rows(
        user,
        table,
        [{"id": rows[0].id, f"field_{field.id}": "x" * (EMBEDDING_TEXT_LIMIT * 3)}],
    )
    SearchHandler.update_search_data(table, row_ids=[rows[0].id])
    embedder = CountingEmbedder()
    with CaptureQueriesContext(connection) as queries:
        SearchHandler.update_embeddings(
            table, [field.id], row_ids=[rows[0].id], embedder=embedder
        )
    assert embedder.calls == [["x" * EMBEDDING_TEXT_LIMIT]]
    assert any(f"LEFT(" in q["sql"] for q in queries.captured_queries)


@pytest.mark.django_db
def test_switching_the_embeddings_service_re_embeds_every_cell(vector_table):
    user, table, field, rows = vector_table
    embedder = CountingEmbedder()
    with override_settings(BASEROW_EMBEDDINGS_API_URL="http://first.test"):
        SearchHandler.update_embeddings(table, [field.id], embedder=embedder)
        SearchHandler.update_embeddings(table, [field.id], embedder=embedder)
    assert sum(len(call) for call in embedder.calls) == 3

    with override_settings(BASEROW_EMBEDDINGS_API_URL="http://second.test"):
        SearchHandler.update_embeddings(table, [field.id], embedder=embedder)
    assert sum(len(call) for call in embedder.calls) == 6


def test_embedder_hides_the_service_url_from_http_errors():
    def failing(request):
        return httpx.Response(500, text="internal error")

    def client(base_url):
        return httpx.Client(base_url=base_url, transport=httpx.MockTransport(failing))

    with patch("baserow.core.embeddings.httpxClient", client):
        with pytest.raises(EmbeddingsServiceError) as exc_info:
            BaserowEmbedder(EMBEDDINGS_URL)(["text"])
    assert EMBEDDINGS_URL not in str(exc_info.value)
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.django_db
def test_duplicating_and_exporting_a_field_keep_vector_search_enabled(
    vector_table, data_fixture
):
    user, table, field, rows = vector_table
    with override_settings(BASEROW_EMBEDDINGS_API_URL=EMBEDDINGS_URL):
        duplicate, _ = FieldHandler().duplicate_field(user, field)
    assert duplicate.vector_search_enabled is True

    field_type = field.get_type()
    exported = field_type.export_serialized(field)
    assert exported["vector_search_enabled"] is True
    other_table = data_fixture.create_database_table(user=user)
    imported = field_type.import_serialized(
        other_table,
        exported,
        ImportExportConfig(include_permission_data=False),
        {},
        DeferredForeignKeyUpdater(),
    )
    assert imported.vector_search_enabled is True


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_field_update_restores_vector_search_enabled(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    with override_settings(BASEROW_EMBEDDINGS_API_URL=EMBEDDINGS_URL):
        field = FieldHandler().create_field(
            user, table, "long_text", name="Notes", vector_search_enabled=True
        )
        action_type_registry.get_by_type(UpdateFieldActionType).do(
            user, field, vector_search_enabled=False
        )
        assert FieldHandler().get_field(field.id).vector_search_enabled is False

        actions = ActionHandler.undo(
            user, [UpdateFieldActionType.scope(table.id)], session_id
        )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    assert FieldHandler().get_field(field.id).vector_search_enabled is True
