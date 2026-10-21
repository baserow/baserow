from io import BytesIO
from unittest.mock import patch

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.tasks import periodic_check_pending_search_data
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_files.handler import UserFileHandler
from baserow.test_utils.helpers import (
    PEOPLE_XLS,
    build_deeply_nested_docx,
    build_docx,
    build_pdf,
    build_slow_pdf,
)
from baserow_enterprise.semantic_search.handler import SemanticSearchHandler
from baserow_enterprise.semantic_search.models import (
    SemanticSearchField,
    SemanticSearchPendingUpdate,
)

from .utils import enable_search_data_updates, get_chunk_counts, index

pytestmark = enable_search_data_updates


def update_field(api_client, token, field, data):
    return api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


def update_row(api_client, token, table, row, values):
    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        {f"field_{field.id}": value for field, value in values.items()},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()


def list_fields(api_client, token, table):
    return api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    ).json()


@pytest.mark.django_db
def test_enable_semantic_search_indexes_the_field(
    api_client, data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Notes", "long_text")],
        rows=[["The quick brown fox"], ["A lazy dog"], [""]],
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = update_field(
            api_client, token, fields[0], {"semantic_search_enabled": True}
        )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["semantic_search_enabled"] is True
    assert get_chunk_counts(fields[0]) == {rows[0].id: 1, rows[1].id: 1}
    assert [
        (field["semantic_search_enabled"], field["semantic_search_status"])
        for field in list_fields(api_client, token, table)
    ] == [(True, "ready")]


@pytest.mark.django_db(transaction=True)
def test_changed_cells_are_indexed_again(api_client, data_fixture, semantic_search):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Notes", "long_text"), ("Other", "text")],
        rows=[["first", "a"], ["second", "b"]],
    )
    update_field(api_client, token, fields[0], {"semantic_search_enabled": True})
    semantic_search.embedded_texts.clear()

    update_row(api_client, token, table, rows[0], {fields[0]: "changed"})
    update_row(api_client, token, table, rows[1], {fields[1]: "c"})
    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{fields[0].id}": "A " + "long text " * 300},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Only the changed cell and the new cell, which is split into chunks, are
    # embedded.
    assert semantic_search.embedded_texts[0] == "changed"
    assert len(semantic_search.embedded_texts) == 5
    assert sorted(get_chunk_counts(fields[0]).values()) == [1, 1, 4]
    assert not SemanticSearchPendingUpdate.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_changed_cells_dont_change_the_status(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"]]
    )
    update_field(api_client, token, fields[0], {"semantic_search_enabled": True})

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        update_row(api_client, token, table, rows[0], {fields[0]: "changed"})

    assert get_chunk_counts(fields[0]) == {rows[0].id: 1}
    assert "changed" in semantic_search.embedded_texts
    assert not [
        call
        for call in broadcast.delay.call_args_list
        if call.args[1]["type"] == "semantic_search_field_status_updated"
    ]
    assert SemanticSearchField.objects.get().status == "ready"


@pytest.mark.django_db
def test_status_changes_are_broadcast(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        with django_capture_on_commit_callbacks(execute=True):
            FieldHandler().update_field(user, field, semantic_search_enabled=True)

    payloads = [call.args[1] for call in broadcast.delay.call_args_list]
    # The field starts indexing, which is part of the updated field.
    assert payloads[0]["type"] == "field_updated"
    assert payloads[0]["field"]["semantic_search_status"] == "indexing"
    assert payloads[-1] == {
        "type": "semantic_search_field_status_updated",
        "field_id": field.id,
        "semantic_search_status": "ready",
    }


@pytest.mark.django_db
def test_enable_semantic_search_requires_license(
    api_client, data_fixture, enterprise_data_fixture, semantic_search
):
    enterprise_data_fixture.delete_all_licenses()
    user, token = data_fixture.create_user_and_token()
    field = data_fixture.create_text_field(user=user)

    response = update_field(api_client, token, field, {"semantic_search_enabled": True})

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert not SemanticSearchField.objects.exists()


@pytest.mark.django_db
def test_enable_semantic_search_requires_embeddings_service(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        response = api_client.post(
            reverse("api:database:fields:list", kwargs={"table_id": table.id}),
            {"name": "Text", "type": "text", "semantic_search_enabled": True},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SEMANTIC_SEARCH_NOT_AVAILABLE"


@pytest.mark.django_db
def test_enable_semantic_search_requires_feature_flag(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"]]
    )

    with override_settings(FEATURE_FLAGS=[]):
        response = update_field(
            api_client, token, fields[0], {"semantic_search_enabled": True}
        )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SEMANTIC_SEARCH_NOT_AVAILABLE"
    assert not SemanticSearchField.objects.exists()


@pytest.mark.django_db
def test_enable_semantic_search_on_incompatible_field(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Number", "type": "number", "semantic_search_enabled": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SEMANTIC_SEARCH_NOT_SUPPORTED"


@pytest.mark.django_db(transaction=True)
def test_paused_without_license_or_service(
    api_client, data_fixture, enterprise_data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"]]
    )
    update_field(api_client, token, fields[0], {"semantic_search_enabled": True})

    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        status = list_fields(api_client, token, table)[0]["semantic_search_status"]
    assert status == "unavailable"

    enterprise_data_fixture.delete_all_licenses()
    semantic_search.embedded_texts.clear()
    update_row(api_client, token, table, rows[0], {fields[0]: "changed"})
    update_row(api_client, token, table, rows[0], {fields[0]: "changed again"})
    # Saving the field again doesn't require the license, because semantic search
    # is already enabled.
    response = update_field(
        api_client,
        token,
        fields[0],
        {"name": "Renamed", "semantic_search_enabled": True},
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["semantic_search_status"] == "paused"
    assert semantic_search.embedded_texts == []
    # The changes made while paused are processed as one update of all rows.
    assert list(
        SemanticSearchPendingUpdate.objects.values_list("row_id", flat=True)
    ) == [None]


@pytest.mark.django_db(transaction=True)
def test_paused_fields_dont_broadcast_their_stored_status(
    api_client, data_fixture, enterprise_data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"]]
    )
    update_field(api_client, token, fields[0], {"semantic_search_enabled": True})
    enterprise_data_fixture.delete_all_licenses()

    with patch("baserow.ws.registries.broadcast_to_channel_group") as broadcast:
        update_row(api_client, token, table, rows[0], {fields[0]: "changed"})

    # The stored status becomes `indexing`, but the field shows that it's paused.
    assert not [
        call.args[1]
        for call in broadcast.delay.call_args_list
        if call.args[1]["type"] == "semantic_search_field_status_updated"
    ]
    assert list_fields(api_client, token, table)[0]["semantic_search_status"] == (
        "paused"
    )


@pytest.mark.django_db(transaction=True)
def test_changes_arent_queued_without_vector_search(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"]]
    )
    update_field(api_client, token, fields[0], {"semantic_search_enabled": True})

    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        update_row(api_client, token, table, rows[0], {fields[0]: "changed"})

    assert not SemanticSearchPendingUpdate.objects_and_trash.exists()


@pytest.mark.django_db(transaction=True)
def test_rows_permanently_deleted_while_paused_lose_their_vectors(
    api_client, data_fixture, enterprise_data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"], ["second"]]
    )
    update_field(api_client, token, fields[0], {"semantic_search_enabled": True})
    enterprise_data_fixture.delete_all_licenses()

    RowHandler().delete_row_by_id(user, table, rows[0].id)
    TrashHandler.empty(user, table.database.workspace_id, table.database_id)
    TrashHandler.permanently_delete_marked_trash()
    # While paused, a change queues an update of all rows instead.
    update_row(api_client, token, table, rows[1], {fields[0]: "changed"})
    periodic_check_pending_search_data()

    assert get_chunk_counts(fields[0]) == {rows[1].id: 1}


@pytest.mark.django_db
def test_index_continues_where_it_stopped(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Notes", "text")],
        rows=[[f"value {number}"] for number in range(150)],
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)

    assert index(table, seconds=0) is False
    assert get_chunk_counts(fields[0]) == {}

    assert index(table) is True
    assert len(get_chunk_counts(fields[0])) == 150
    assert not SemanticSearchPendingUpdate.objects.exists()


@pytest.mark.django_db
def test_another_model_of_the_embeddings_service_embeds_cells_again(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["first"]]
    )
    with override_settings(BASEROW_EMBEDDINGS_API_URL="http://embeddings/model-a"):
        FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
        index(table)

    with override_settings(BASEROW_EMBEDDINGS_API_URL="http://embeddings/model-b"):
        SemanticSearchHandler().queue_full_updates(
            table, [SemanticSearchField.objects.get()]
        )
        index(table)

    assert semantic_search.embedded_texts == ["first", "first"]


@pytest.mark.django_db
@override_settings(
    BASEROW_SEMANTIC_SEARCH_CHUNK_SIZE=100,
    BASEROW_SEMANTIC_SEARCH_CHUNK_OVERLAP=10,
    BASEROW_SEMANTIC_SEARCH_MAX_CHUNKS_PER_CELL=3,
)
def test_long_cells_are_limited_to_the_maximum_chunks(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Notes", "long_text")],
        rows=[["word " * 1000] for _ in range(30)],
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)

    assert index(table) is True

    assert set(get_chunk_counts(fields[0]).values()) == {3}
    assert len(semantic_search.embedded_texts) == 90


@pytest.mark.django_db
def test_index_files(data_fixture, semantic_search, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_file_field(table=table)
    handler = UserFileHandler()
    with override_settings(MEDIA_ROOT=str(tmpdir)):
        text_file = handler.upload_user_file(
            user, "notes.txt", BytesIO(b"Meeting about the budget")
        )
        pdf_file = handler.upload_user_file(
            user, "report.pdf", BytesIO(build_pdf("Quarterly revenue"))
        )
        word_file = handler.upload_user_file(
            user,
            "minutes.docx",
            BytesIO(build_docx("<w:p><w:r><w:t>Hiring plan</w:t></w:r></w:p>")),
        )
        excel_file = handler.upload_user_file(user, "people.xls", BytesIO(PEOPLE_XLS))
        image_file = handler.upload_user_file(user, "holiday.png", BytesIO(b"png"))
        RowHandler().create_rows(
            user,
            table,
            [
                {
                    field.db_column: [
                        {"name": text_file.name, "visible_name": "notes.txt"},
                        {"name": pdf_file.name, "visible_name": "report.pdf"},
                        {"name": word_file.name, "visible_name": "minutes.docx"},
                        {"name": excel_file.name, "visible_name": "people.xls"},
                        {"name": image_file.name, "visible_name": "holiday.png"},
                    ]
                }
            ],
        )
        FieldHandler().update_field(user, field, semantic_search_enabled=True)

        assert index(table) is True

    assert semantic_search.embedded_texts == [
        "notes.txt\n\nMeeting about the budget",
        "report.pdf\n\nQuarterly revenue",
        "minutes.docx\n\nHiring plan",
        "people.xls\n\nPeople\nName\tAge\nAda\t36\nBob\t40",
        "holiday.png",
    ]


@pytest.mark.django_db
@override_settings(
    BASEROW_SEMANTIC_SEARCH_CHUNK_SIZE=100,
    BASEROW_SEMANTIC_SEARCH_MAX_CHUNKS_PER_CELL=1,
)
def test_files_beyond_the_text_limit_of_a_cell_arent_read(
    data_fixture, semantic_search, tmpdir
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_file_field(table=table)
    with override_settings(MEDIA_ROOT=str(tmpdir)):
        files = [
            UserFileHandler().upload_user_file(
                user, f"{number}.txt", BytesIO(b"text " * 100)
            )
            for number in range(3)
        ]
        RowHandler().create_rows(
            user, table, [{field.db_column: [{"name": file.name} for file in files]}]
        )
        FieldHandler().update_field(user, field, semantic_search_enabled=True)

        with patch.object(
            UserFileHandler,
            "extract_text",
            autospec=True,
            side_effect=UserFileHandler.extract_text,
        ) as extract_text:
            index(table)

    assert extract_text.call_count == 1


@pytest.mark.django_db
def test_soft_time_limit_isnt_swallowed_when_reading_files(
    data_fixture, semantic_search, tmpdir
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_file_field(table=table)
    with override_settings(MEDIA_ROOT=str(tmpdir)):
        file = UserFileHandler().upload_user_file(user, "a.txt", BytesIO(b"text"))
        RowHandler().create_rows(
            user, table, [{field.db_column: [{"name": file.name}]}]
        )
    FieldHandler().update_field(user, field, semantic_search_enabled=True)

    # Celery raises this in whatever the task is doing when its time is up.
    with patch.object(
        UserFileHandler, "extract_text", side_effect=SoftTimeLimitExceeded()
    ):
        with pytest.raises(SoftTimeLimitExceeded):
            index(table)


@pytest.mark.django_db(transaction=True)
def test_index_formula_and_lookup_fields(api_client, data_fixture, semantic_search):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user, database=database, columns=[("Name", "text")], rows=[["hello"]]
    )
    other_table, other_fields, other_rows = data_fixture.build_table(
        user=user, database=database, columns=[("Name", "text")], rows=[["linked"]]
    )

    def create_field(data):
        return api_client.post(
            reverse("api:database:fields:list", kwargs={"table_id": table.id}),
            {"semantic_search_enabled": True, **data},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        ).json()

    link = data_fixture.create_link_row_field(
        table=table, name="Link", link_row_table=other_table
    )
    update_row(api_client, token, table, rows[0], {link: [other_rows[0].id]})
    create_field(
        {"name": "F", "type": "formula", "formula": "concat('x ', field('Name'))"}
    )
    create_field(
        {
            "name": "Lookup",
            "type": "lookup",
            "through_field_id": link.id,
            "target_field_id": other_fields[0].id,
        }
    )
    # Changing a referenced value changes the formula, so it's indexed again.
    update_row(api_client, token, table, rows[0], {fields[0]: "changed"})

    assert "x hello" in semantic_search.embedded_texts
    assert "x changed" in semantic_search.embedded_texts
    assert "linked" in semantic_search.embedded_texts


def create_text_rollup(data_fixture, user, table):
    other_table, other_fields, other_rows = data_fixture.build_table(
        user=user,
        database=table.database,
        columns=[("Name", "text")],
        rows=[["linked value"]],
    )
    link = data_fixture.create_link_row_field(
        table=table, name="Link", link_row_table=other_table
    )
    rollup = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="Rollup",
        through_field_id=link.id,
        target_field_id=other_fields[0].id,
        rollup_function="max",
    )
    return rollup, {link.db_column: [other_rows[0].id]}, "linked value"


@pytest.mark.parametrize(
    "create_field",
    [
        lambda data_fixture, premium_data_fixture, user, table: (
            data_fixture.create_email_field(table=table),
            "person@example.com",
            "person@example.com",
        ),
        lambda data_fixture, premium_data_fixture, user, table: (
            data_fixture.create_phone_number_field(table=table),
            "+31 6 12345678",
            "+31 6 12345678",
        ),
        lambda data_fixture, premium_data_fixture, user, table: (
            data_fixture.create_url_field(table=table),
            "https://baserow.io",
            "https://baserow.io",
        ),
        lambda data_fixture, premium_data_fixture, user, table: (
            data_fixture.create_long_text_field(
                table=table, long_text_enable_rich_text=True
            ),
            "**Parcel** arrived damaged",
            "**Parcel** arrived damaged",
        ),
        lambda data_fixture, premium_data_fixture, user, table: (
            premium_data_fixture.create_ai_field(table=table, ai_prompt="'summary'"),
            "Generated summary",
            "Generated summary",
        ),
        lambda data_fixture, premium_data_fixture, user, table: create_text_rollup(
            data_fixture, user, table
        ),
    ],
    ids=["email", "phone_number", "url", "rich_text", "ai", "rollup"],
)
@pytest.mark.django_db
def test_index_field_types(
    api_client, data_fixture, premium_data_fixture, semantic_search, create_field
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["first"]]
    )
    field, value, expected_text = create_field(
        data_fixture, premium_data_fixture, user, table
    )
    values = value if isinstance(value, dict) else {field.db_column: value}
    RowHandler().update_row_by_id(user, table, rows[0].id, values)

    response = update_field(api_client, token, field, {"semantic_search_enabled": True})
    index(table)

    assert response.status_code == HTTP_200_OK, response.json()
    assert get_chunk_counts(field) == {rows[0].id: 1}
    assert expected_text in semantic_search.embedded_texts


@pytest.mark.django_db
def test_enable_semantic_search_on_ai_field_without_text_output(
    api_client, data_fixture, premium_data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table, ai_prompt="'category'", ai_output_type="choice"
    )

    response = update_field(api_client, token, field, {"semantic_search_enabled": True})

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SEMANTIC_SEARCH_NOT_SUPPORTED"


@pytest.mark.django_db
def test_converting_to_incompatible_type_disables_semantic_search(
    api_client, data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["1"]]
    )
    with django_capture_on_commit_callbacks(execute=True):
        update_field(api_client, token, fields[0], {"semantic_search_enabled": True})
    assert get_chunk_counts(fields[0])

    with django_capture_on_commit_callbacks(execute=True):
        response = update_field(api_client, token, fields[0], {"type": "number"})

    assert response.json()["semantic_search_enabled"] is False
    assert not SemanticSearchField.objects.exists()
    periodic_check_pending_search_data()
    assert get_chunk_counts(fields[0]) == {}


@pytest.mark.django_db
def test_formula_that_stops_being_text_disables_semantic_search(
    api_client, data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["1"]]
    )
    formula = FieldHandler().create_field(
        user, table, "formula", name="Copy", formula="field('Notes')"
    )
    update_field(
        api_client,
        token,
        formula,
        {"formula": "field('Notes')", "semantic_search_enabled": True},
    )
    index(table)
    assert get_chunk_counts(formula)

    # The formula isn't updated itself, but its result becomes a number.
    with django_capture_on_commit_callbacks(execute=True):
        response = update_field(api_client, token, fields[0], {"type": "number"})

    assert [
        related_field["semantic_search_enabled"]
        for related_field in response.json()["related_fields"]
    ] == [False]
    assert not SemanticSearchField.objects.exists()
    periodic_check_pending_search_data()
    assert get_chunk_counts(formula) == {}


@pytest.mark.django_db
def test_files_that_couldnt_be_read_are_read_again(
    data_fixture, semantic_search, tmpdir
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_file_field(table=table)
    handler = UserFileHandler()
    with override_settings(MEDIA_ROOT=str(tmpdir)):
        user_file = handler.upload_user_file(
            user, "notes.txt", BytesIO(b"Meeting about the budget")
        )
        path = tmpdir.join(handler.user_file_path(user_file.name))
        content = path.read_binary()
        RowHandler().create_rows(
            user,
            table,
            [
                {
                    field.db_column: [
                        {"name": user_file.name, "visible_name": "notes.txt"}
                    ]
                }
            ],
        )
        FieldHandler().update_field(user, field, semantic_search_enabled=True)

        # The storage is unavailable while the field is indexed.
        path.remove()
        index(table)
        assert semantic_search.embedded_texts == ["notes.txt"]

        path.write_binary(content)
        semantic_search.embedded_texts.clear()
        SemanticSearchHandler().queue_full_updates(
            table, [SemanticSearchField.objects.get()]
        )
        index(table)

    assert semantic_search.embedded_texts == ["notes.txt\n\nMeeting about the budget"]


@pytest.mark.django_db
def test_hostile_files_are_only_searchable_by_their_name(
    data_fixture, semantic_search, tmpdir
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_file_field(table=table)
    handler = UserFileHandler()
    with (
        override_settings(MEDIA_ROOT=str(tmpdir)),
        # Shorter than reading the slow PDF takes, which then also leaves no time
        # for the next file of the cell.
        patch(
            "baserow_enterprise.semantic_search.semantic_search_field_types."
            "FILE_EXTRACTION_SECONDS_PER_CELL",
            2,
        ),
    ):
        nested_docx = handler.upload_user_file(
            user, "nested.docx", BytesIO(build_deeply_nested_docx())
        )
        slow_pdf = handler.upload_user_file(user, "slow.pdf", BytesIO(build_slow_pdf()))
        text_file = handler.upload_user_file(
            user, "notes.txt", BytesIO(b"Meeting about the budget")
        )
        RowHandler().create_rows(
            user,
            table,
            [
                {
                    field.db_column: [
                        {"name": nested_docx.name, "visible_name": "nested.docx"}
                    ]
                },
                {
                    field.db_column: [
                        {"name": slow_pdf.name, "visible_name": "slow.pdf"},
                        {"name": text_file.name, "visible_name": "notes.txt"},
                    ]
                },
                {
                    field.db_column: [
                        {"name": text_file.name, "visible_name": "notes.txt"}
                    ]
                },
            ],
        )
        FieldHandler().update_field(user, field, semantic_search_enabled=True)

        assert index(table) is True

    assert semantic_search.embedded_texts == [
        "nested.docx",
        "slow.pdf",
        "notes.txt",
        "notes.txt\n\nMeeting about the budget",
    ]
    assert SemanticSearchField.objects.get().status == "ready"


@pytest.mark.django_db
def test_changed_file_settings_index_files_again(data_fixture, semantic_search, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_file_field(table=table)
    handler = UserFileHandler()
    with override_settings(MEDIA_ROOT=str(tmpdir)):
        user_file = handler.upload_user_file(
            user, "notes.txt", BytesIO(b"Meeting about the budget")
        )
        RowHandler().create_rows(
            user,
            table,
            [
                {
                    field.db_column: [
                        {
                            "name": user_file.name,
                            "visible_name": "notes.txt",
                            "size": user_file.size,
                        }
                    ]
                }
            ],
        )
        with override_settings(BASEROW_SEMANTIC_SEARCH_MAX_FILE_SIZE_MB=0):
            FieldHandler().update_field(user, field, semantic_search_enabled=True)
            index(table)
        assert semantic_search.embedded_texts == ["notes.txt"]

        semantic_search.embedded_texts.clear()
        SemanticSearchHandler().queue_full_updates(
            table, [SemanticSearchField.objects.get()]
        )
        index(table)

    assert semantic_search.embedded_texts == ["notes.txt\n\nMeeting about the budget"]


@pytest.mark.django_db
def test_disable_semantic_search_deletes_vectors(
    api_client, data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["value"]]
    )
    with django_capture_on_commit_callbacks(execute=True):
        update_field(api_client, token, fields[0], {"semantic_search_enabled": True})

    with django_capture_on_commit_callbacks(execute=True):
        update_field(api_client, token, fields[0], {"semantic_search_enabled": False})

    assert not SemanticSearchField.objects.exists()
    # Deleted by the periodic check, like the full-text search data.
    assert get_chunk_counts(fields[0]) == {rows[0].id: 1}
    periodic_check_pending_search_data()
    assert get_chunk_counts(fields[0]) == {}
    assert not SemanticSearchPendingUpdate.objects_and_trash.exists()


@pytest.mark.django_db
def test_disabling_while_indexing_doesnt_leave_vectors(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text")], rows=[["value"]]
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)

    def disabling_embedder(texts):
        # Someone disables semantic search while the texts are embedded.
        with django_capture_on_commit_callbacks(execute=True):
            FieldHandler().update_field(user, fields[0], semantic_search_enabled=False)
        return semantic_search(texts)

    with patch(
        "baserow_enterprise.semantic_search.handler.get_embedder",
        return_value=disabling_embedder,
    ):
        index(table)

    assert semantic_search.embedded_texts == ["value"]
    assert get_chunk_counts(fields[0]) == {}


@pytest.mark.django_db
def test_related_fields_dont_query_semantic_search_per_field(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Notes", "text"), ("Other", "text")], rows=[]
    )
    for field, dependants in [(fields[0], 1), (fields[1], 4)]:
        for number in range(dependants):
            FieldHandler().create_field(
                user,
                table,
                "formula",
                name=f"{field.name} {number}",
                formula=f"field('{field.name}')",
            )

    def count_semantic_search_queries(field) -> int:
        with CaptureQueriesContext(connection) as captured:
            response = update_field(
                api_client, token, field, {"name": f"{field.name} renamed"}
            )
        assert response.status_code == HTTP_200_OK
        assert response.json()["related_fields"]
        return sum(
            "semanticsearchfield" in query["sql"] for query in captured.captured_queries
        )

    assert count_semantic_search_queries(fields[0]) == (
        count_semantic_search_queries(fields[1])
    )


@pytest.mark.django_db
def test_listing_fields_doesnt_query_per_semantic_search_field(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    def count_queries():
        with CaptureQueriesContext(connection) as captured:
            list_fields(api_client, token, table)
        return len(captured)

    field = data_fixture.create_text_field(table=table)
    FieldHandler().update_field(user, field, semantic_search_enabled=True)
    count_queries()
    one_field_queries = count_queries()

    for _ in range(4):
        field = data_fixture.create_text_field(table=table)
        FieldHandler().update_field(user, field, semantic_search_enabled=True)

    assert count_queries() == one_field_queries
