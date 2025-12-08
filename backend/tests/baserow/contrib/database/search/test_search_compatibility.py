from io import BytesIO

from django.core.files.storage import FileSystemStorage
from django.db import transaction

import pytest
from PIL import Image

from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.user_files.handler import UserFileHandler

pytestmark = pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)


@pytest.mark.django_db(transaction=True)
def test_search_compatibility_between_current_and_postgres(data_fixture, tmpdir):
    query_searches = {
        "text": [
            ["Peter Evans", "Peter Evans"],  # full-text, compat exact
            ["Peter Ev", "Peter Ev"],  # full-text, compat partial
            ["peTeR   EV", "peTeR EV"]  # full-text, compat mixed case.
            # Compat can't handle multiple spaces.
        ],
        "long_text": [
            ["The quick brown fox jumps", "The quick brown fox jumps"],
            ["The quick bro", "The quick bro"],
            ["ThE QuICk BROWN ", "ThE QuICk BROWN "],
        ],
        "number": [
            ["123456789", "123456789"],
            ["1234", "1234"],
        ],
        "file": [
            ["photo of him", "photo of him"],
            ["photo of ", "photo of "],
            ["pHoTo OF ", "pHoTo OF "],
        ],
        "url": [
            ["https://baserow.io", "https://baserow.io"],
            ["https://base ", "https://base "],  # Compat does support trailing spaces
            # however, just not in the middle?
            ["HTtps://BASEROW.iO", "HTtps://BASEROW.iO"],
        ],
        "date": [
            ["01/06/2023", "01/06/2023"],
            ["01/06", "01/06"],
        ],
        "datetime": [
            ["01/06/2023", "01/06/2023"],
            ["01/06", "01/06"],
        ],
        "single_select": [
            ["Teal", "Teal"],
            ["Tea", "Tea"],
            ["Teal   ", "Teal    "],
        ],
        "multiple_select": [
            ["Ocean", "Ocean"],
            ["Ocea", "Ocea"],
            ["OcEAn   ", "OcEAn   "],
            ["Navy", "Navy"],
            ["Nav", "Nav"],
            ["NAvY   ", "NAvY   "],
        ],
        "multiple_collaborators": [
            ["Jeff", None],  # Compat search cannot search collaborators
            ["Jef", None],
            ["JeFF    ", None],
            ["Clive", None],
            ["Cli", None],
            ["ClIvE    ", None],
        ],
        "last_modified_by": [
            ["John Smith", "John Smith"],
            ["John Sm", "John Sm"],
            ["joHn SM", "joHn SM"],
        ],
    }
    with transaction.atomic():
        user = data_fixture.create_user(first_name="John Smith")
        database = data_fixture.create_database_application(user=user)
        table = TableHandler().create_table_and_fields(
            user=user,
            database=database,
            name=data_fixture.fake.name(),
            fields=[
                ("Name", "text", {}),
                ("Notes", "long_text", {}),
                ("Numbers", "number", {}),
                ("Thumbnails", "file", {}),
                ("URL", "url", {}),
                ("Email", "email", {}),
                ("Date", "date", {}),
                ("Datetime", "date", {}),
                ("Single select", "single_select", {}),
                ("Multiple select", "multiple_select", {}),
                (
                    "Multiple collaborators",
                    "multiple_collaborators",
                    {"notify_user_when_added": False},
                ),
                ("Last modified by", "last_modified_by", {}),
            ],
        )

        # Multiple collaborator field setup
        multiple_collaborators_field = table.field_set.get(
            name="Multiple collaborators"
        )
        collab_user1 = data_fixture.create_user(
            first_name="Jeff", workspace=database.workspace
        )
        collab_user2 = data_fixture.create_user(
            first_name="Clive", workspace=database.workspace
        )

        # File field setup
        storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
        image = Image.new("RGB", (400, 400), color="red")
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        user_file = UserFileHandler().upload_user_file(
            user, "clive.png", image_bytes, storage=storage
        )

        # Single select field setup
        single_select_field = table.field_set.get(name="Single select")
        single_select_option_1 = SelectOption.objects.create(
            field=single_select_field,
            order=1,
            value="Teal",
            color="blue",
        )
        single_select_field.select_options.set([single_select_option_1])

        # Multiple select field setup
        multiple_select_field = table.field_set.get(name="Multiple select")
        multiple_select_option_1 = SelectOption.objects.create(
            field=multiple_select_field,
            order=1,
            value="Ocean",
            color="blue",
        )
        multiple_select_option_2 = SelectOption.objects.create(
            field=multiple_select_field,
            order=2,
            value="Navy",
            color="blue",
        )
        multiple_select_field.select_options.set(
            [multiple_select_option_1, multiple_select_option_2]
        )

        text_field = table.field_set.get(name="Name")
        long_text_field = table.field_set.get(name="Notes")
        number_field = table.field_set.get(name="Numbers")
        file_field = table.field_set.get(name="Thumbnails")
        url_field = table.field_set.get(name="URL")
        email_field = table.field_set.get(name="Email")
        date_field = table.field_set.get(name="Date")
        datetime_field = table.field_set.get(name="Datetime")

        row = RowHandler().create_row(
            user=user,
            table=table,
            values={
                f"field_{text_field.id}": "Peter Evans",
                f"field_{long_text_field.id}": "The quick brown fox jumps "
                "over the lazy dog",
                f"field_{number_field.id}": "123456789",
                f"field_{file_field.id}": [
                    {
                        "name": user_file.name,
                        "size": 48441,
                        "is_image": True,
                        "mime_type": "image/jpeg",
                        "image_width": 400,
                        "uploaded_at": "2023-04-25T13:26:36.926004+00:00",
                        "image_height": 400,
                        "visible_name": "A photo of him.",
                    }
                ],
                f"field_{url_field.id}": "https://baserow.io",
                f"field_{email_field.id}": "peter@baserow.io",
                f"field_{date_field.id}": "2023-06-01",
                f"field_{datetime_field.id}": "2023-06-01 15:00:00.327017+00",
                f"field_{single_select_field.id}": single_select_option_1.id,
                f"field_{multiple_select_field.id}": [
                    multiple_select_option_1.id,
                    multiple_select_option_2.id,
                ],
                f"field_{multiple_collaborators_field.id}": [
                    {"id": collab_user1.id},
                    {"id": collab_user2.id},
                ],
            },
        )

    model = table.get_model()
    for field_type, queries in query_searches.items():
        for pg_query, compat_query in queries:
            assert (
                model.objects.filter(pk=row.pk).pg_search(pg_query).exists()
            ), f"Unable to match Postgres query '{pg_query}'."
            if compat_query is not None:
                assert (
                    model.objects.filter(pk=row.pk).compat_search(compat_query).exists()
                ), f"Unable to match compatibility query '{compat_query}'."


@pytest.mark.django_db(transaction=True)
def test_searching_across_fields_in_full_text_prevented(data_fixture):
    with transaction.atomic():
        user = data_fixture.create_user()
        database = data_fixture.create_database_application(user=user)
        table = TableHandler().create_table_and_fields(
            user=user,
            database=database,
            name=data_fixture.fake.name(),
            fields=[
                ("First name", "text", {}),
                ("Last name", "text", {}),
            ],
        )
        first_name_field = table.field_set.get(name="First name")
        last_name_field = table.field_set.get(name="Last name")
        RowHandler().create_row(
            user=user,
            table=table,
            values={
                f"field_{first_name_field.id}": "Clive",
                f"field_{last_name_field.id}": "Perkins",
            },
        )
    model = table.get_model()
    qs = model.objects.all()
    assert qs.pg_search("Clive").exists()
    assert qs.pg_search("Perkins").exists()
    assert not qs.pg_search("Clive Perkins").exists()


@pytest.mark.django_db(transaction=True)
def test_cyrillic_search_is_case_insensitive(data_fixture):
    with transaction.atomic():
        user = data_fixture.create_user()
        database = data_fixture.create_database_application(user=user)
        table = TableHandler().create_table_and_fields(
            user=user,
            database=database,
            name=data_fixture.fake.name(),
            fields=[
                ("Ingredient", "text", {}),
            ],
        )
        field = table.field_set.get(name="Ingredient")
        row1 = RowHandler().create_row(
            user=user, table=table, values={f"field_{field.id}": "сир"}
        )
        row2 = RowHandler().create_row(
            user=user, table=table, values={f"field_{field.id}": "СИР"}
        )
    model = table.get_model()
    qs = model.objects.all()
    assert list(qs.pg_search("сир").order_by("id").values_list("id", flat=True)) == [
        row1.id,
        row2.id,
    ]
    assert list(qs.pg_search("СИР").order_by("id").values_list("id", flat=True)) == [
        row1.id,
        row2.id,
    ]
