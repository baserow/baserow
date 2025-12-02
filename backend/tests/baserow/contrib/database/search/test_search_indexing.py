import random
import string
from io import BytesIO

from django.core.files.storage import FileSystemStorage

import pytest
from PIL import Image

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.user_files.handler import UserFileHandler

pytestmark = pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)


@pytest.mark.django_db(transaction=True)
def test_textfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Name", "text", {}),
        ],
    )
    field = table.field_set.get(name="Name")
    row = RowHandler().force_create_row(
        user=user, table=table, values={f"field_{field.id}": "Jeff"}
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("Jeff")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_longtextfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Notes", "long_text", {}),
        ],
    )
    field = table.field_set.get(name="Notes")
    row = RowHandler().force_create_row(
        user=user, table=table, values={f"field_{field.id}": "I like cheese a lot."}
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("cheese")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_numberfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Number", "number", {}),
        ],
    )
    field = table.field_set.get(name="Number")
    row = RowHandler().force_create_row(
        user=user, table=table, values={f"field_{field.id}": 123456789}
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("123456789")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_filefield_get_search_expression(data_fixture, tmpdir):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Thumbnails", "file", {}),
        ],
    )
    field = table.field_set.get(name="Thumbnails")

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    image = Image.new("RGB", (400, 400), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    user_file = UserFileHandler().upload_user_file(
        user, "clive.png", image_bytes, storage=storage
    )

    row = RowHandler().force_create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": [
                {
                    "name": user_file.name,
                    "size": 48441,
                    "is_image": True,
                    "mime_type": "image/jpeg",
                    "image_width": 400,
                    "uploaded_at": "2023-04-25T13:26:36.926004+00:00",
                    "image_height": 400,
                    "visible_name": "Clive",
                }
            ]
        },
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("Clive")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_urlfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("URL", "url", {}),
        ],
    )
    field = table.field_set.get(name="URL")
    row = RowHandler().force_create_row(
        user=user, table=table, values={f"field_{field.id}": "https://baserow.io"}
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("https://baserow.io")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_emailfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Email", "email", {}),
        ],
    )
    field = table.field_set.get(name="Email")
    row = RowHandler().force_create_row(
        user=user, table=table, values={f"field_{field.id}": "dev@baserow.io"}
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("dev@baserow.io")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_datefield_without_time_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Date", "date", {}),
        ],
    )
    field = table.field_set.get(name="Date")
    row = RowHandler().force_create_row(
        user=user, table=table, values={f"field_{field.id}": "1974-08-26"}
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("26/08/1974")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_datefield_with_time_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Datetime", "date", {}),
        ],
    )
    field = table.field_set.get(name="Datetime")
    row = RowHandler().force_create_row(
        user=user,
        table=table,
        values={f"field_{field.id}": "2023-05-09 15:00:00.327017+00"},
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("09/05/2023")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_singleselectfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(
        user=user, name="Single Select", table=table, tsvector_column_created=True
    )
    select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Jeff",
        color="blue",
    )
    single_select_field.select_options.set([select_option_1])

    table = single_select_field.table

    row = RowHandler().force_create_row(
        user=user,
        table=table,
        values={f"field_{single_select_field.id}": select_option_1.id},
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("Jeff")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.django_db(transaction=True)
def test_multiselectfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        user=user, table=table, tsvector_column_created=True
    )
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Jeff",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=2,
        value="Clive",
        color="blue",
    )
    select_option_3 = SelectOption.objects.create(
        field=multiple_select_field,
        order=3,
        value="Steve",
        color="blue",
    )
    multiple_select_field.select_options.set(
        [select_option_1, select_option_2, select_option_3]
    )

    table = multiple_select_field.table
    row = RowHandler().force_create_row(
        user=user,
        table=table,
        values={
            f"field_{multiple_select_field.id}": [
                select_option_1.id,
                select_option_2.id,
            ]
        },
    )
    model = table.get_model()

    qs = model.objects.all().pg_search("jeff")
    assert qs.get().id == row.id

    qs = model.objects.all().pg_search("clive")
    assert qs.get().id == row.id

    assert not model.objects.all().pg_search("steve").exists()


@pytest.mark.django_db(transaction=True)
def test_collaboratorfield_get_search_expression(data_fixture):
    workspace = data_fixture.create_workspace()
    creator = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=creator, workspace=workspace
    )
    table = data_fixture.create_database_table(user=creator, database=database)

    user1 = data_fixture.create_user(first_name="Jeff", workspace=workspace)
    user2 = data_fixture.create_user(first_name="Clive", workspace=workspace)
    _ = data_fixture.create_user(first_name="Steve", workspace=workspace)

    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        table=table
    )

    row = RowHandler().force_create_row(
        user=creator,
        table=table,
        values={
            f"field_{multiple_collaborators_field.id}": [
                {"id": user1.id},
                {"id": user2.id},
            ]
        },
    )
    model = table.get_model()

    qs = model.objects.all().pg_search("jeff")
    assert qs.get().id == row.id

    qs = model.objects.all().pg_search("clive")
    assert qs.get().id == row.id

    assert not model.objects.all().pg_search("steve").exists()


@pytest.mark.django_db(transaction=True)
def test_lookupfield_get_search_expression(data_fixture):
    workspace = data_fixture.create_workspace()
    creator = data_fixture.create_user(workspace=workspace)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=creator)

    table_a_primary = table_a.field_set.get(primary=True)
    lookup_field = FieldHandler().create_field(
        creator,
        table_b,
        "lookup",
        name="lookup",
        through_field_id=link_field.link_row_related_field_id,
        target_field_id=table_a_primary.id,
    )
    assert not lookup_field.error

    table_a_row_1, table_a_row_2 = (
        RowHandler()
        .force_create_rows(
            user=creator,
            table=table_a,
            rows_values=[
                {
                    f"{link_field.db_column}": [],
                    f"{table_a_primary.db_column}": "jeff",
                },
                {
                    f"{link_field.db_column}": [],
                    f"{table_a_primary.db_column}": "clive",
                },
            ],
        )
        .created_rows
    )
    table_b_row_looking_up_jeff, table_b_looking_up_jeff_and_clive = (
        RowHandler()
        .force_create_rows(
            user=creator,
            table=table_b,
            rows_values=[
                {
                    f"field_{link_field.link_row_related_field_id}": [
                        table_a_row_1.id,
                    ]
                },
                {
                    f"field_{link_field.link_row_related_field_id}": [
                        table_a_row_1.id,
                        table_a_row_2.id,
                    ]
                },
            ],
        )
        .created_rows
    )
    model = table_b.get_model()

    qs = list(model.objects.all().pg_search("jeff").values_list("id", flat=True))
    assert qs == [
        table_b_row_looking_up_jeff.id,
        table_b_looking_up_jeff_and_clive.id,
    ]

    qs = model.objects.all().pg_search("clive")
    assert qs.get().id == table_b_looking_up_jeff_and_clive.id

    assert not model.objects.all().pg_search("steve").exists()


@pytest.mark.django_db(transaction=True)
def test_linkrowfield_get_search_expression(data_fixture):
    workspace = data_fixture.create_workspace()
    creator = data_fixture.create_user(workspace=workspace)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=creator)

    table_a_primary = table_a.field_set.get(primary=True)

    table_a_row_1, table_a_row_2 = (
        RowHandler()
        .force_create_rows(
            user=creator,
            table=table_a,
            rows_values=[
                {
                    f"{link_field.db_column}": [],
                    f"{table_a_primary.db_column}": "jeff",
                },
                {
                    f"{link_field.db_column}": [],
                    f"{table_a_primary.db_column}": "clive",
                },
            ],
        )
        .created_rows
    )

    table_b_row_linking_to_jeff, table_b_linking_to_jeff_and_clive = (
        RowHandler()
        .force_create_rows(
            user=creator,
            table=table_b,
            rows_values=[
                {
                    f"field_{link_field.link_row_related_field_id}": [
                        table_a_row_1.id,
                    ]
                },
                {
                    f"field_{link_field.link_row_related_field_id}": [
                        table_a_row_1.id,
                        table_a_row_2.id,
                    ]
                },
            ],
        )
        .created_rows
    )
    model = table_b.get_model()

    qs = list(model.objects.all().pg_search("jeff").values_list("id", flat=True))
    assert qs == [
        table_b_row_linking_to_jeff.id,
        table_b_linking_to_jeff_and_clive.id,
    ]

    qs = model.objects.all().pg_search("clive")
    assert qs.get().id == table_b_linking_to_jeff_and_clive.id

    assert not model.objects.all().pg_search("steve").exists()


@pytest.mark.django_db(transaction=True)
def test_linkrowfield_get_search_expression_to_formula_button(
    data_fixture,
):
    workspace = data_fixture.create_workspace()
    creator = data_fixture.create_user(workspace=workspace)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=creator)

    table_a_primary = table_a.field_set.get(primary=True).specific
    table_a_text_field = FieldHandler().create_field(
        creator, table_a, "text", name="text"
    )
    FieldHandler().update_field(
        creator,
        table_a_primary,
        "formula",
        formula="button(if(field('text') ='1', 'jeff', 'clive'), 'a')",
    )

    table_a_row_1, table_a_row_2 = (
        RowHandler()
        .force_create_rows(
            user=creator,
            table=table_a,
            rows_values=[
                {
                    f"{link_field.db_column}": [],
                    f"{table_a_text_field.db_column}": "1",
                },
                {
                    f"{link_field.db_column}": [],
                    f"{table_a_text_field.db_column}": "0",
                },
            ],
        )
        .created_rows
    )
    table_b_row_linking_to_jeff, table_b_linking_to_jeff_and_clive = (
        RowHandler()
        .force_create_rows(
            user=creator,
            table=table_b,
            rows_values=[
                {f"field_{link_field.link_row_related_field_id}": [table_a_row_1.id]},
                {
                    f"field_{link_field.link_row_related_field_id}": [
                        table_a_row_1.id,
                        table_a_row_2.id,
                    ]
                },
            ],
        )
        .created_rows
    )
    model = table_b.get_model()

    qs = list(model.objects.all().pg_search("jeff").values_list("id", flat=True))
    assert qs == [
        table_b_row_linking_to_jeff.id,
        table_b_linking_to_jeff_and_clive.id,
    ]

    qs = model.objects.all().pg_search("clive")
    assert qs.get().id == table_b_linking_to_jeff_and_clive.id

    assert not model.objects.all().pg_search("steve").exists()


def make_big_string(n: int) -> str:
    return bytes(
        random.choices(
            string.ascii_uppercase.encode("ascii") + (" " * 30).encode("ascii"), k=n
        )
    ).decode("ascii")


@pytest.mark.django_db(transaction=True)
def test_massive_textfield_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Name", "text", {}),
        ],
    )
    field = table.field_set.get(name="Name")
    row = RowHandler().force_create_row(
        user=user,
        table=table,
        values={f"field_{field.id}": "Jeff" + make_big_string(1048575 * 10)},
    )
    model = table.get_model()
    qs = model.objects.all().pg_search("Jeff")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id


@pytest.mark.field_last_modified_by
@pytest.mark.django_db(transaction=True)
def test_last_modified_by_field_get_search_expression(data_fixture):
    user_adam = data_fixture.create_user(email="user1@baserow.io", first_name="Adam")
    user_john_smith = data_fixture.create_user(
        email="user2@baserow.io", first_name="John Smith"
    )
    user_mary_black = data_fixture.create_user(
        email="user3@baserow.io", first_name="Mary Black"
    )

    database = data_fixture.create_database_application(user=user_adam)
    data_fixture.create_user_workspace(
        workspace=database.workspace, user=user_john_smith
    )
    data_fixture.create_user_workspace(
        workspace=database.workspace, user=user_mary_black
    )
    table = data_fixture.create_database_table(name="Search table", database=database)
    grid_view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_last_modified_by_field(
        user=user_adam, table=table, name="Last modified by"
    )
    model = table.get_model()

    row1 = model.objects.create(last_modified_by=user_mary_black)
    row2 = model.objects.create(last_modified_by=user_john_smith)
    row3 = model.objects.create(last_modified_by=user_adam)
    row4 = model.objects.create(last_modified_by=user_mary_black)
    row5 = model.objects.create(last_modified_by=None)

    SearchHandler.update_search_data(table=table)

    model = table.get_model()
    qs = model.objects.all().pg_search("Mary")
    assert qs.exists()
    matching_rows = list(qs)
    assert len(matching_rows) == 2
    assert matching_rows[0].id == row1.id
    assert matching_rows[1].id == row4.id


@pytest.mark.field_duration
@pytest.mark.django_db(transaction=True)
def test_duration_field_get_search_expression(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Duration", "duration", {"duration_format": "h:mm:ss.sss"}),
        ],
    )
    field = table.field_set.get(name="Duration")
    row = RowHandler().force_create_row(
        user=user, table=table, values={f"field_{field.id}": "1:53:46.789"}
    )

    model = table.get_model()
    qs = model.objects.all().pg_search("53")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id

    qs = model.objects.all().pg_search("1")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id

    qs = model.objects.all().pg_search("46")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id

    qs = model.objects.all().pg_search("789")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id

    qs = model.objects.all().pg_search("1:53:46.789")
    assert qs.exists()
    matching_row = qs.get()
    assert matching_row.id == row.id

    # Searching the number of seconds doesn't work
    qs = model.objects.all().pg_search(f"{83 * 60}")
    assert not qs.exists()
