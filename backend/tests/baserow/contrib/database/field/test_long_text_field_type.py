import pytest

from baserow.contrib.database.fields.exceptions import IncompatiblePrimaryFieldTypeError
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.contrib.database.trash.models import TrashedRows
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
@pytest.mark.field_long_text
def test_rich_text_field_cannot_be_primary(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().create_field(
            user=user,
            table=table,
            type_name="long_text",
            name="Primary",
            primary=True,
            long_text_enable_rich_text=True,
        )

    # A non rich text field can be used as primary field
    primary_field = FieldHandler().create_field(
        user=user, table=table, type_name="long_text", name="Primary", primary=True
    )

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().update_field(
            user=user,
            field=primary_field,
            new_type_name="long_text",
            long_text_enable_rich_text=True,
        )

    rich_text = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="long_text",
        name="Rich text",
        primary=False,
        long_text_enable_rich_text=True,
    )

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().change_primary_field(
            user=user, table=table, new_primary_field=rich_text
        )


@pytest.mark.django_db
def test_perm_deleting_rows_delete_rich_text_mentions(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )

    row_1, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user=user,
            table=table,
            rows_values=[
                {field.db_column: f"Hello @{user.id}!"},
                {field.db_column: f"Ciao @{user.id}!"},
                {field.db_column: f"Hola @{user.id}!"},
            ],
        )
        .created_rows
    )

    mentions = RichTextFieldMention.objects.all()
    assert mentions.count() == 3
    assert list(mentions.values_list("row_id", flat=True).order_by("row_id")) == [
        row_1.id,
        row_2.id,
        row_3.id,
    ]

    TrashHandler.permanently_delete(row_1, table.id)
    mentions = RichTextFieldMention.objects.all()
    assert mentions.count() == 2
    assert list(mentions.values_list("row_id", flat=True).order_by("row_id")) == [
        row_2.id,
        row_3.id,
    ]

    trashed_rows = TrashedRows.objects.create(row_ids=[row_2.id, row_3.id], table=table)

    TrashHandler.permanently_delete(trashed_rows, table.id)

    assert RichTextFieldMention.objects.all().count() == 0
