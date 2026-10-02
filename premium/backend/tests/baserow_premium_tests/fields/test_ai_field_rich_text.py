import io
from unittest.mock import patch
from zipfile import ZipFile

from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.exceptions import (
    IncompatiblePrimaryFieldTypeError,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field, TextField
from baserow.contrib.database.fields.utils.deferred_foreign_key_updater import (
    DeferredForeignKeyUpdater,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.jobs.handler import JobHandler
from baserow.core.notifications.models import Notification
from baserow.core.registries import ImportExportConfig
from baserow.core.user_files.models import UserFile
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid
from baserow_premium.fields.ai_field_output_types import (
    RICH_TEXT_PROMPT_INSTRUCTIONS,
)
from baserow_premium.fields.field_types import AIFieldType
from baserow_premium.fields.handler import AIFieldHandler
from baserow_premium.fields.job_types import AIValueGenerator
from baserow_premium.fields.models import AIField, GenerateAIValuesJob

MISSING_IMAGE_VALUE = "![chart][abc_chart.png]"
ESCAPED_IMAGE_VALUE = "![chart]\\[abc_chart.png]"
AI_FIELD_KWARGS = {
    "ai_generative_ai_type": "test_generative_ai",
    "ai_generative_ai_model": "test_1",
    "ai_prompt": "'Hi'",
}


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_with_rich_text_via_api(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "AI",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Hi'",
            "long_text_enable_rich_text": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["long_text_enable_rich_text"] is True


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_rich_text_is_disabled_by_default(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "AI",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Hi'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["long_text_enable_rich_text"] is False


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize(
    "template,escaped_template",
    [
        ("![x][{name}]", "![x]\\[{name}]"),
        ("![x][{name}](http://h/x.png)", "![x]\\[{name}]"),
        ("![foo ![x][{name}]", "![foo ![x]\\[{name}]"),
        ("![x](https://e.com/x.png)", "![x](https://e.com/x.png)"),
    ],
)
@pytest.mark.parametrize("user_file_exists", [False, True])
def test_rich_text_ai_field_stores_written_image_references_as_text(
    premium_data_fixture, api_client, template, escaped_template, user_file_exists
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    plain = premium_data_fixture.create_ai_field(table=table, name="plain")
    rich = premium_data_fixture.create_ai_field(
        table=table, name="rich", long_text_enable_rich_text=True
    )
    name = "abc_x.png"
    if user_file_exists:
        name = premium_data_fixture.create_user_file(is_image=True).name
    value = template.format(name=name)
    values = {plain.db_column: value, rich.db_column: value}
    handler = RowHandler()
    rows = handler.create_rows(user, table, [{}, {}, {}]).created_rows

    handler.update_row_by_id(user, table, rows[0].id, values)
    handler.update_rows(user, table, [{"id": rows[1].id, **values}])
    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": rows[2].id},
        ),
        values,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    escaped = escaped_template.format(name=name)
    assert response.status_code == HTTP_200_OK
    assert response.json()[rich.db_column] == escaped
    stored = table.get_model().objects.order_by("id")
    assert [
        (getattr(r, plain.db_column), getattr(r, rich.db_column)) for r in stored
    ] == [(value, escaped)] * 3


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("value", [None, ""])
def test_rich_text_ai_field_stores_empty_values_as_is(premium_data_fixture, value):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    rich = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=True
    )
    row = RowHandler().create_row(user, table, {rich.db_column: "text"})

    RowHandler().update_row_by_id(user, table, row.id, {rich.db_column: value})

    row.refresh_from_db()
    assert getattr(row, rich.db_column) == value


@pytest.mark.django_db
@pytest.mark.field_ai
def test_import_into_rich_text_ai_field_stores_image_references_as_text(
    premium_data_fixture, tmpdir
):
    table = premium_data_fixture.create_database_table()
    field = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=True
    )
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("abc_x.png", b"PNG_DATA")
    zip_buffer.seek(0)
    row = table.get_model()()
    value = {
        "content": "![x][abc_x.png]",
        "images": [{"name": "abc_x.png", "original_name": "x.png"}],
    }

    AIFieldType().set_import_serialized_value(
        row, field.db_column, value, {}, {}, ZipFile(zip_buffer), storage
    )

    assert getattr(row, field.db_column) == "![x]\\[abc_x.png]"
    assert not UserFile.objects.exists()
    assert tmpdir.listdir() == []


@pytest.mark.django_db
@pytest.mark.field_ai
def test_rich_text_ai_field_cannot_be_grouped_by(premium_data_fixture):
    plain = premium_data_fixture.create_ai_field()
    rich = premium_data_fixture.create_ai_field(long_text_enable_rich_text=True)

    assert AIFieldType().check_can_group_by(plain, "default") is True
    assert AIFieldType().check_can_group_by(rich, "default") is False


@pytest.mark.django_db
@pytest.mark.field_ai
def test_rich_text_ai_field_cannot_be_primary(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().create_field(
            user,
            table,
            "ai",
            name="rich",
            primary=True,
            long_text_enable_rich_text=True,
            **AI_FIELD_KWARGS,
        )
    choice = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="rich choice",
        primary=True,
        ai_output_type="choice",
        long_text_enable_rich_text=True,
        **AI_FIELD_KWARGS,
    )

    choice.refresh_from_db()
    assert choice.long_text_enable_rich_text is False


@pytest.mark.django_db
@pytest.mark.field_ai
def test_rich_text_flag_is_cleared_when_output_type_is_choice(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    handler = FieldHandler()

    choice = handler.create_field(
        user,
        table,
        "ai",
        name="choice",
        ai_output_type="choice",
        long_text_enable_rich_text=True,
        **AI_FIELD_KWARGS,
    )
    choice.refresh_from_db()
    assert choice.long_text_enable_rich_text is False

    handler.update_field(user, choice, long_text_enable_rich_text=True)
    choice.refresh_from_db()
    assert choice.long_text_enable_rich_text is False

    rich = handler.create_field(
        user,
        table,
        "ai",
        name="rich",
        long_text_enable_rich_text=True,
        **AI_FIELD_KWARGS,
    )
    handler.update_field(user, rich, ai_output_type="choice")
    rich.refresh_from_db()
    assert rich.long_text_enable_rich_text is False

    handler.update_field(user, rich, ai_output_type="text")
    rich.refresh_from_db()
    assert rich.long_text_enable_rich_text is False


@pytest.mark.django_db
@pytest.mark.field_ai
def test_rich_text_flag_is_kept_on_text_ai_field_update(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(table=table)

    FieldHandler().update_field(user, field, long_text_enable_rich_text=True)
    field.refresh_from_db()
    assert field.long_text_enable_rich_text is True

    FieldHandler().update_field(user, field, name="renamed")
    field.refresh_from_db()
    assert field.long_text_enable_rich_text is True


@pytest.mark.django_db
@pytest.mark.field_ai
def test_choice_ai_field_made_primary_then_switched_to_text_stays_plain(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_text_field(table=table, primary=True)
    choice = premium_data_fixture.create_ai_field(table=table, ai_output_type="choice")
    handler = FieldHandler()

    handler.update_field(user, choice, long_text_enable_rich_text=True)
    handler.change_primary_field(user, table, choice)
    handler.update_field(user, choice, ai_output_type="text")

    choice.refresh_from_db()
    assert choice.primary is True
    assert choice.ai_output_type == "text"
    assert choice.long_text_enable_rich_text is False


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.undo_redo
def test_undo_output_type_switch_restores_rich_text(premium_data_fixture):
    session_id = "session-id"
    user = premium_data_fixture.create_user(session_id=session_id)
    table = premium_data_fixture.create_database_table(user=user)
    rich = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=True
    )
    row = RowHandler().create_row(user, table, {rich.db_column: "**bold**"})
    scope = UpdateFieldActionType.scope(table.id)

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, rich, ai_output_type="choice"
    )
    actions = ActionHandler.undo(user, [scope], session_id)
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    rich.refresh_from_db()
    assert (rich.ai_output_type, rich.long_text_enable_rich_text) == ("text", True)
    row = table.get_model().objects.get(id=row.id)
    assert getattr(row, rich.db_column) == "**bold**"

    actions = ActionHandler.redo(user, [scope], session_id)
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    rich.refresh_from_db()
    assert (rich.ai_output_type, rich.long_text_enable_rich_text) == ("choice", False)

    actions = ActionHandler.undo(user, [scope], session_id)
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    rich.refresh_from_db()
    assert (rich.ai_output_type, rich.long_text_enable_rich_text) == ("text", True)


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize(
    "output_type,primary",
    [("choice", False), ("text", True)],
)
def test_import_clears_disallowed_rich_text_flag(
    premium_data_fixture, output_type, primary
):
    user = premium_data_fixture.create_user()
    source_table = premium_data_fixture.create_database_table(user=user)
    target_table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=source_table, ai_output_type=output_type
    )
    field_type = AIFieldType()
    serialized = field_type.export_serialized(field)
    serialized["long_text_enable_rich_text"] = True
    serialized["primary"] = primary

    imported = field_type.import_serialized(
        target_table,
        serialized,
        ImportExportConfig(include_permission_data=False),
        id_mapping={},
        deferred_fk_update_collector=DeferredForeignKeyUpdater(),
    )

    imported = AIField.objects.get(id=imported.id)
    assert imported.primary is primary
    assert imported.long_text_enable_rich_text is False


@pytest.mark.django_db
@pytest.mark.field_ai
def test_import_keeps_rich_text_flag_on_non_primary_text_ai_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=True
    )
    field_type = AIFieldType()

    imported = field_type.import_serialized(
        table,
        field_type.export_serialized(field),
        ImportExportConfig(include_permission_data=False),
        id_mapping={},
        deferred_fk_update_collector=DeferredForeignKeyUpdater(),
    )

    imported = AIField.objects.get(id=imported.id)
    assert imported.long_text_enable_rich_text is True


@pytest.mark.django_db
@pytest.mark.field_ai
def test_primary_choice_ai_field_switched_to_text_stays_plain(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    primary = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="primary",
        primary=True,
        ai_output_type="choice",
        long_text_enable_rich_text=True,
        **AI_FIELD_KWARGS,
    )

    FieldHandler().update_field(user, primary, ai_output_type="text")

    primary.refresh_from_db()
    assert primary.ai_output_type == "text"
    assert primary.long_text_enable_rich_text is False
    assert AIFieldType().can_be_primary_field(primary) is True


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize(
    "output_type,payload",
    [
        ("text", {"long_text_enable_rich_text": True}),
        ("choice", {"ai_output_type": "text", "long_text_enable_rich_text": True}),
    ],
)
def test_patch_primary_ai_field_to_rich_text_via_api_is_rejected(
    premium_data_fixture, api_client, output_type, payload
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    primary = premium_data_fixture.create_ai_field(
        table=table, primary=True, ai_output_type=output_type
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": primary.id}),
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE"
    primary.refresh_from_db()
    assert primary.long_text_enable_rich_text is False


@pytest.mark.django_db
@pytest.mark.field_ai
def test_convert_primary_field_to_rich_text_ai_via_api_is_rejected(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    primary = premium_data_fixture.create_text_field(table=table, primary=True)
    premium_data_fixture.register_fake_generate_ai_type()

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": primary.id}),
        {"type": "ai", "long_text_enable_rich_text": True, **AI_FIELD_KWARGS},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE"
    assert Field.objects.get(id=primary.id).specific_class is TextField


@pytest.mark.django_db
@pytest.mark.field_ai
def test_rich_text_ai_field_cannot_become_primary_via_api(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_text_field(table=table, primary=True)
    rich = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=True
    )

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table.id}
        ),
        {"new_primary_field_id": rich.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE"
    rich.refresh_from_db()
    assert rich.primary is False


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize(
    "output_type,rich_text,expected_prompt",
    [
        ("text", True, f"Hi\n\n{RICH_TEXT_PROMPT_INSTRUCTIONS}"),
        ("text", False, "Hi"),
        ("choice", True, "Hi"),
    ],
)
def test_prompt_asks_for_markdown_only_for_rich_text_output(
    premium_data_fixture, output_type, rich_text, expected_prompt
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_prompt="'Hi'",
        ai_output_type=output_type,
        long_text_enable_rich_text=rich_text,
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("test_generative_ai")

    with patch.object(model_type, "prompt", return_value="Hi") as mock_prompt:
        AIFieldHandler.generate_value_with_ai(field, row)

    assert mock_prompt.call_args.args[1] == expected_prompt


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize(
    "generated,rich_text,expected",
    [
        (f"see {MISSING_IMAGE_VALUE}", True, f"see {ESCAPED_IMAGE_VALUE}"),
        (f"see {MISSING_IMAGE_VALUE}", False, f"see {MISSING_IMAGE_VALUE}"),
        ("see ![a ![b][abc_c.png]", True, "see ![a ![b]\\[abc_c.png]"),
    ],
)
def test_generated_image_references_are_escaped_only_in_rich_text(
    premium_data_fixture, generated, rich_text, expected
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=rich_text
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("test_generative_ai")

    with patch.object(model_type, "prompt", return_value=generated):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id
        )

    assert job.state == "finished"
    row.refresh_from_db()
    stored = getattr(row, field.db_column)
    assert stored == expected
    RowHandler().update_row_by_id(user, table, row.id, {field.db_column: stored})
    row.refresh_from_db()
    assert getattr(row, field.db_column) == expected


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("rich_text", [False, True])
def test_generation_uses_rich_text_setting_changed_mid_job(
    premium_data_fixture, rich_text
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=not rich_text
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("test_generative_ai")
    prepare = AIValueGenerator.prepare

    def prepare_then_change_rich_text(generator: AIValueGenerator) -> None:
        prepare(generator)
        FieldHandler().update_field(user, field, long_text_enable_rich_text=rich_text)

    with (
        patch.object(AIValueGenerator, "prepare", prepare_then_change_rich_text),
        patch.object(model_type, "prompt", return_value=MISSING_IMAGE_VALUE),
    ):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id
        )

    assert job.state == "finished"
    row.refresh_from_db()
    expected = ESCAPED_IMAGE_VALUE if rich_text else MISSING_IMAGE_VALUE
    assert getattr(row, field.db_column) == expected


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("change", ["convert", "trash", "output_type"])
@pytest.mark.parametrize("output_type", ["text", "choice"])
def test_generation_stops_writing_when_field_no_longer_accepts_results(
    premium_data_fixture, change, output_type
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table, ai_output_type=output_type
    )
    existing = "Existing value"
    if output_type == "choice":
        existing = premium_data_fixture.create_select_option(
            field=field, value=existing, color="red"
        ).id
        premium_data_fixture.create_select_option(
            field=field, value="Generated value", color="blue"
        )
    RowHandler().create_rows(
        user, table, [{field.db_column: existing}, {field.db_column: existing}]
    )
    model = table.get_model()
    expected = []
    model_type = generative_ai_model_type_registry.get("test_generative_ai")
    prepare = AIValueGenerator.prepare

    def prepare_then_change_field(generator: AIValueGenerator) -> None:
        prepare(generator)
        if change == "convert":
            FieldHandler().update_field(user, field, new_type_name="long_text")
        elif change == "trash":
            FieldHandler().delete_field(user, field)
        else:
            FieldHandler().update_field(
                user,
                field,
                ai_output_type="choice" if output_type == "text" else "text",
            )
        expected.extend(model.objects.values_list(field.db_column, flat=True))

    with (
        patch.object(AIValueGenerator, "prepare", prepare_then_change_field),
        patch.object(model_type, "prompt", return_value="Generated value"),
    ):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id
        )

    assert job.state == "finished"
    assert job.error == ""
    assert list(model.objects.values_list(field.db_column, flat=True)) == expected


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("rich_text", [False, True])
@pytest.mark.parametrize("row_count", [1, 100])
def test_generation_has_no_separate_field_query_per_row(
    premium_data_fixture, rich_text, row_count
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=rich_text
    )
    RowHandler().create_rows(user, table, [{} for _ in range(row_count)])
    model_type = generative_ai_model_type_registry.get("test_generative_ai")

    with (
        patch.object(model_type, "prompt", return_value=MISSING_IMAGE_VALUE),
        CaptureQueriesContext(connection) as queries,
    ):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id
        )

    assert job.state == "finished"
    # Field retrieval during job creation/start is constant. The current setting
    # travels with the row SELECT instead of adding a field SELECT for every row.
    field_reads = [
        query["sql"]
        for query in queries
        if query["sql"].startswith('SELECT "database_field".')
        and '"baserow_premium_aifield"' in query["sql"]
    ]
    assert len(field_reads) == 2
    expected = ESCAPED_IMAGE_VALUE if rich_text else MISSING_IMAGE_VALUE
    assert (
        list(table.get_model().objects.values_list(field.db_column, flat=True))
        == [expected] * row_count
    )


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("output", ["plain", "rich", "choice"])
def test_generated_write_uses_same_query_count_as_ordinary_row_write(
    premium_data_fixture, output
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_output_type="choice" if output == "choice" else "text",
        long_text_enable_rich_text=output == "rich",
    )
    ordinary = "Ordinary value"
    generated = MISSING_IMAGE_VALUE
    if output == "choice":
        ordinary = premium_data_fixture.create_select_option(
            field=field, value=ordinary, color="red"
        )
        generated = premium_data_fixture.create_select_option(
            field=field, value="Generated value", color="blue"
        )
    neighbor = premium_data_fixture.create_single_select_field(table=table)
    neighbor_option = premium_data_fixture.create_select_option(
        field=neighbor, value="Neighbor", color="red"
    )
    row = RowHandler().create_row(user, table, {neighbor.db_column: neighbor_option.id})
    model = table.get_model()

    # Warm permission caches before comparing the two write paths.
    RowHandler().update_row_by_id(
        user,
        table,
        row.id,
        {field.db_column: ordinary},
        model=model,
        values_already_prepared=True,
    )
    with CaptureQueriesContext(connection) as ordinary_queries:
        RowHandler().update_row_by_id(
            user,
            table,
            row.id,
            {field.db_column: ordinary},
            model=model,
            values_already_prepared=True,
        )
    with CaptureQueriesContext(connection) as generated_queries:
        assert AIFieldHandler.update_generated_value(
            user, field, row.id, generated, model
        )

    assert len(generated_queries) == len(ordinary_queries)
    row.refresh_from_db()
    if output == "choice":
        assert getattr(row, field.db_column).id == generated.id
    else:
        expected = ESCAPED_IMAGE_VALUE if output == "rich" else MISSING_IMAGE_VALUE
        assert getattr(row, field.db_column) == expected


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("change", ["convert", "enable_rich_text"])
def test_generation_handles_field_changes_after_a_saved_result(
    premium_data_fixture, settings, change
):
    settings.BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS = 1
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(table=table)
    RowHandler().create_rows(user, table, [{}, {}])
    model_type = generative_ai_model_type_registry.get("test_generative_ai")
    handle_result = AIValueGenerator.handle_result

    def handle_result_then_change_field(generator, result):
        handle_result(generator, result)
        if generator.finished == 1:
            if change == "convert":
                FieldHandler().update_field(user, field, new_type_name="long_text")
            else:
                FieldHandler().update_field(
                    user, field, long_text_enable_rich_text=True
                )

    with (
        patch.object(
            AIValueGenerator, "handle_result", handle_result_then_change_field
        ),
        patch.object(
            model_type, "prompt", return_value=MISSING_IMAGE_VALUE
        ) as mock_prompt,
    ):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id
        )

    assert job.state == "finished"
    expected = (
        [MISSING_IMAGE_VALUE, None]
        if change == "convert"
        else [ESCAPED_IMAGE_VALUE, ESCAPED_IMAGE_VALUE]
    )
    assert (
        list(
            table.get_model()
            .objects.order_by("id")
            .values_list(field.db_column, flat=True)
        )
        == expected
    )
    if change == "enable_rich_text":
        # Only saved values adopt the new setting; the generation threads retain
        # the prompt configuration with which the job started.
        assert all(
            RICH_TEXT_PROMPT_INSTRUCTIONS not in call.args[1]
            for call in mock_prompt.call_args_list
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_mid_job_rich_text_escaping_survives_partial_generation_failure(
    premium_data_fixture, settings
):
    settings.BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS = 1
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(table=table)
    RowHandler().create_rows(user, table, [{}, {}, {}])
    model_type = generative_ai_model_type_registry.get("test_generative_ai")
    handle_result = AIValueGenerator.handle_result

    def handle_result_then_enable_rich_text(generator, result):
        handle_result(generator, result)
        if generator.finished == 1:
            FieldHandler().update_field(user, field, long_text_enable_rich_text=True)

    with (
        patch.object(
            AIValueGenerator, "handle_result", handle_result_then_enable_rich_text
        ),
        patch.object(
            model_type,
            "prompt",
            side_effect=[
                MISSING_IMAGE_VALUE,
                MISSING_IMAGE_VALUE,
                GenerativeAIPromptError("Provider unavailable"),
            ],
        ),
        pytest.raises(GenerativeAIPromptError, match="Provider unavailable"),
    ):
        JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id
        )

    assert GenerateAIValuesJob.objects.latest("id").state == "failed"
    assert list(
        table.get_model().objects.order_by("id").values_list(field.db_column, flat=True)
    ) == [ESCAPED_IMAGE_VALUE, ESCAPED_IMAGE_VALUE, None]


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.undo_redo
def test_enabling_rich_text_escapes_existing_image_references(premium_data_fixture):
    session_id = "session-id"
    user = premium_data_fixture.create_user(session_id=session_id)
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(table=table)
    user_file = premium_data_fixture.create_user_file(is_image=True)
    code = f"`{MISSING_IMAGE_VALUE}`"
    originals = [
        MISSING_IMAGE_VALUE,
        f"![y][{user_file.name}]",
        code,
        "plain",
        f"{MISSING_IMAGE_VALUE}(http://h/x.png)",
        "![foo ![x][abc_x.png]",
    ]
    rows = (
        RowHandler()
        .create_rows(user, table, [{field.db_column: v} for v in originals])
        .created_rows
    )
    table.get_model().objects.filter(id=rows[0].id).update(trashed=True)
    scopes = [UpdateFieldActionType.scope(table.id)]

    def stored_values() -> list[str]:
        model = table.get_model()
        return [
            getattr(model.objects_and_trash.get(id=row.id), field.db_column)
            for row in rows
        ]

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, field, long_text_enable_rich_text=True
    )

    assert stored_values() == [
        ESCAPED_IMAGE_VALUE,
        f"![y]\\[{user_file.name}]",
        code,
        "plain",
        f"{ESCAPED_IMAGE_VALUE}(http://h/x.png)",
        "![foo ![x]\\[abc_x.png]",
    ]

    actions = ActionHandler.undo(user, scopes, session_id)

    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    field.refresh_from_db()
    assert field.long_text_enable_rich_text is False
    assert stored_values() == originals


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.undo_redo
def test_switching_choice_to_rich_text_escapes_existing_image_references(
    premium_data_fixture,
):
    session_id = "session-id"
    user = premium_data_fixture.create_user(session_id=session_id)
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(table=table, ai_output_type="choice")
    option = premium_data_fixture.create_select_option(
        field=field, value=MISSING_IMAGE_VALUE
    )
    row = RowHandler().create_row(user, table, {field.db_column: option.id})
    scopes = [UpdateFieldActionType.scope(table.id)]

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, field, ai_output_type="text", long_text_enable_rich_text=True
    )

    row = table.get_model().objects.get(id=row.id)
    assert getattr(row, field.db_column) == ESCAPED_IMAGE_VALUE

    actions = ActionHandler.undo(user, scopes, session_id)

    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    field.refresh_from_db()
    assert (field.ai_output_type, field.long_text_enable_rich_text) == (
        "choice",
        False,
    )
    row = table.get_model().objects.get(id=row.id)
    assert getattr(row, field.db_column).value == MISSING_IMAGE_VALUE


@pytest.mark.django_db
@pytest.mark.field_ai
def test_mention_in_rich_text_ai_field_does_not_notify(premium_data_fixture):
    user = premium_data_fixture.create_user()
    member = premium_data_fixture.create_user()
    workspace = premium_data_fixture.create_workspace(members=[user, member])
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    long_text = premium_data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )
    ai = premium_data_fixture.create_ai_field(
        table=table, long_text_enable_rich_text=True
    )
    row = RowHandler().create_row(user, table, {})
    mention = f"Hello @{member.id}"

    RowHandler().update_row_by_id(
        user, table, row.id, {long_text.db_column: mention, ai.db_column: mention}
    )

    assert list(RichTextFieldMention.objects.values_list("field_id", flat=True)) == [
        long_text.id
    ]
    assert list(Notification.objects.values_list("data__field_id", flat=True)) == [
        long_text.id
    ]
