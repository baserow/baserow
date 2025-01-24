import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.fields.field_types import FileFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FileField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.user_files.exceptions import (
    InvalidUserFileNameError,
    UserFileDoesNotExist,
)
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db
@pytest.mark.field_file
def test_file_field_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    user_file_1 = data_fixture.create_user_file()
    user_file_2 = data_fixture.create_user_file()
    user_file_3 = data_fixture.create_user_file()

    field_handler = FieldHandler()
    row_handler = RowHandler()

    file = field_handler.create_field(
        user=user, table=table, type_name="file", name="File"
    )

    assert FileField.objects.all().count() == 1
    model = table.get_model(attribute_names=True)

    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user, table=table, values={"file": "not_a_json"}, model=model
        )

    with pytest.raises(ValidationError):
        row_handler.create_row(user=user, table=table, values={"file": {}}, model=model)

    with pytest.raises(InvalidUserFileNameError):
        row_handler.create_row(
            user=user,
            table=table,
            values={"file": [{"name": "wrongfilename.jpg"}]},
            model=model,
        )

    with pytest.raises(UserFileDoesNotExist):
        row_handler.create_row(
            user=user,
            table=table,
            values={"file": [{"name": "file_name.jpg"}]},
            model=model,
        )

    row = row_handler.create_row(
        user=user,
        table=table,
        values={"file": [{"name": user_file_1.name}]},
        model=model,
    )
    assert row.file[0]["visible_name"] == user_file_1.original_name
    del row.file[0]["visible_name"]
    assert row.file[0] == user_file_1.serialize()

    row = row_handler.create_row(
        user=user,
        table=table,
        values={
            "file": [
                {"name": user_file_2.name},
                {"name": user_file_1.name},
                {"name": user_file_1.name},
            ]
        },
        model=model,
    )
    assert row.file[0]["visible_name"] == user_file_2.original_name
    assert row.file[1]["visible_name"] == user_file_1.original_name
    assert row.file[2]["visible_name"] == user_file_1.original_name
    del row.file[0]["visible_name"]
    del row.file[1]["visible_name"]
    del row.file[2]["visible_name"]
    assert row.file[0] == user_file_2.serialize()
    assert row.file[1] == user_file_1.serialize()
    assert row.file[2] == user_file_1.serialize()

    row = row_handler.create_row(
        user=user,
        table=table,
        values={
            "file": [
                {"name": user_file_1.name},
                {"name": user_file_3.name},
                {"name": user_file_2.name},
            ]
        },
        model=model,
    )
    assert row.file[0]["visible_name"] == user_file_1.original_name
    assert row.file[1]["visible_name"] == user_file_3.original_name
    assert row.file[2]["visible_name"] == user_file_2.original_name
    del row.file[0]["visible_name"]
    del row.file[1]["visible_name"]
    del row.file[2]["visible_name"]
    assert row.file[0] == user_file_1.serialize()
    assert row.file[1] == user_file_3.serialize()
    assert row.file[2] == user_file_2.serialize()

    # test for https://gitlab.com/baserow/baserow/-/issues/2906
    updated_rows = row_handler.update_rows(
        user=user,
        table=table,
        rows_values=[{"id": row.id, file.db_column: None}],
        send_realtime_update=False,
        send_webhook_events=False,
        skip_search_update=True,
    )

    assert updated_rows.updated_rows[0].id == row.id
    assert getattr(updated_rows.updated_rows[0], file.db_column) == []

    row = row_handler.update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={
            "file": [
                {"name": user_file_1.name, "visible_name": "not_original.jpg"},
            ]
        },
        model=model,
    )
    assert row.file[0]["visible_name"] == "not_original.jpg"
    del row.file[0]["visible_name"]
    assert row.file[0] == user_file_1.serialize()

    assert model.objects.all().count() == 3
    field_handler.delete_field(user=user, field=file)
    assert FileField.objects.all().count() == 0
    model.objects.all().delete()

    text = field_handler.create_field(
        user=user, table=table, type_name="text", name="Text"
    )
    model = table.get_model(attribute_names=True)

    row = row_handler.create_row(
        user=user, table=table, values={"text": "Some random text"}, model=model
    )
    row_handler.create_row(
        user=user, table=table, values={"text": '["Not compatible"]'}, model=model
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"text": json.dumps(user_file_1.serialize())},
        model=model,
    )

    file = field_handler.update_field(
        user=user, table=table, field=text, new_type_name="file", name="File"
    )
    model = table.get_model(attribute_names=True)
    results = model.objects.all()
    assert results[0].file == []
    assert results[1].file == []
    assert results[2].file == []

    row_handler.update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={
            "file": [
                {"name": user_file_1.name, "visible_name": "not_original.jpg"},
            ]
        },
        model=model,
    )

    field_handler.update_field(
        user=user, table=table, field=file, new_type_name="text", name="text"
    )
    model = table.get_model(attribute_names=True)
    results = model.objects.all()
    assert results[0].text is None
    assert results[1].text is None
    assert results[2].text is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_file
def test_import_export_file_field(data_fixture, tmpdir):
    user = data_fixture.create_user()
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_file_field(table=table, name="File")

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "test.txt", ContentFile(b"Hello World"), storage=storage
    )

    core_handler = CoreHandler()
    row_handler = RowHandler()
    model = table.get_model()

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": [{"name": user_file.name, "visible_name": "a.txt"}]
        },
        model=model,
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        values={},
        model=model,
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{field.id}": [{"name": user_file.name}]},
        model=model,
    )

    files_buffer = BytesIO()
    config = ImportExportConfig(include_permission_data=False)

    exported_applications = core_handler.export_workspace_applications(
        database.workspace,
        files_buffer=files_buffer,
        storage=storage,
        import_export_config=config,
    )

    # We expect that the exported zip file contains the user file used in the created
    # rows.
    with ZipFile(files_buffer, "r", ZIP_DEFLATED, False) as zip_file:
        assert zip_file.read(user_file.name) == b"Hello World"

    assert (
        exported_applications[0]["tables"][0]["rows"][0][f"field_{field.id}"][0]["name"]
        == user_file.name
    )
    assert (
        exported_applications[0]["tables"][0]["rows"][0][f"field_{field.id}"][0][
            "original_name"
        ]
        == user_file.name
    )
    assert exported_applications[0]["tables"][0]["rows"][1][f"field_{field.id}"] == []
    assert (
        exported_applications[0]["tables"][0]["rows"][2][f"field_{field.id}"][0]["name"]
        == user_file.name
    )

    # Change the original name for enforce that the file is re-uploaded when saved.
    exported_applications[0]["tables"][0]["rows"][0][f"field_{field.id}"][0][
        "original_name"
    ] = "test2.txt"
    exported_applications[0]["tables"][0]["rows"][2][f"field_{field.id}"][0][
        "original_name"
    ] = "test2.txt"

    imported_applications, id_mapping = core_handler.import_applications_to_workspace(
        imported_workspace, exported_applications, files_buffer, config, storage
    )
    imported_database = imported_applications[0]
    imported_tables = imported_database.table_set.all()
    imported_table = imported_tables[0]
    imported_field = imported_table.field_set.all().first().specific
    imported_user_file = UserFile.objects.all()[1]

    import_row_1 = row_handler.get_row(user=user, table=imported_table, row_id=row_1.id)
    import_row_2 = row_handler.get_row(user=user, table=imported_table, row_id=row_2.id)
    import_row_3 = row_handler.get_row(user=user, table=imported_table, row_id=row_3.id)

    assert len(getattr(import_row_1, f"field_{imported_field.id}")) == 1
    assert (
        getattr(import_row_1, f"field_{imported_field.id}")[0]["name"]
        == imported_user_file.name
    )
    assert (
        getattr(import_row_1, f"field_{imported_field.id}")[0]["visible_name"]
        == "a.txt"
    )
    assert len(getattr(import_row_2, f"field_{imported_field.id}")) == 0
    assert len(getattr(import_row_3, f"field_{imported_field.id}")) == 1
    assert (
        getattr(import_row_3, f"field_{imported_field.id}")[0]["name"]
        == imported_user_file.name
    )
    assert (
        getattr(import_row_3, f"field_{imported_field.id}")[0]["visible_name"]
        == "test.txt"
    )

    assert UserFile.objects.all().count() == 2
    assert user_file.name != imported_user_file.name
    file_path = tmpdir.join("user_files", imported_user_file.name)
    assert file_path.isfile()
    assert file_path.open().read() == "Hello World"


@pytest.mark.django_db
def test_get_set_export_serialized_value_file_field(
    data_fixture, tmpdir, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(table=table)
    file_field_name = f"field_{file_field.id}"
    file_field_type = field_type_registry.get_by_model(file_field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "test.txt", ContentFile(b"Hello World"), storage=storage
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{file_field.id}": [
                {"name": user_file.name, "visible_name": "a.txt"}
            ]
        },
        model=model,
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        values={},
        model=model,
    )

    with django_assert_num_queries(0):
        serialized_value = file_field_type.get_export_serialized_value(
            row_1, f"field_{file_field.id}", {}, files_zip=None, storage=None
        )
    assert serialized_value[0]["name"] == user_file.name
    assert serialized_value[0]["visible_name"] == "a.txt"
    assert serialized_value[0]["mime_type"] == "text/plain"

    with django_assert_num_queries(0):
        file_field_type.set_import_serialized_value(
            row_2,
            f"field_{file_field.id}",
            serialized_value,
            {},
            {},
            files_zip=None,
            storage=None,
        )
    row_2.save()
    row_2.refresh_from_db()

    assert getattr(row_2, f"field_{file_field.id}")[0]["name"] == user_file.name
    assert getattr(row_2, f"field_{file_field.id}")[0]["visible_name"] == "a.txt"
    assert getattr(row_2, f"field_{file_field.id}")[0]["mime_type"] == "text/plain"


@pytest.mark.django_db
@pytest.mark.field_file
@pytest.mark.row_history
def test_file_field_are_row_values_equal(
    data_fixture, tmpdir, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    file1 = handler.upload_user_file(
        user, "test.txt", ContentFile(b"Hello World"), storage=storage
    )
    file2 = handler.upload_user_file(
        user, "test2.txt", ContentFile(b"Hello World 2"), storage=storage
    )

    with django_assert_num_queries(0):
        assert (
            FileFieldType().are_row_values_equal(
                [{"name": file1.name}], [{"name": file1.name}]
            )
            is True
        )

        assert (
            FileFieldType().are_row_values_equal(
                [{"name": file1.name}, {"name": file2.name}],
                [{"name": file2.name}, {"name": file1.name}],
            )
            is True
        )

        assert FileFieldType().are_row_values_equal([], []) is True

        assert FileFieldType().are_row_values_equal([], [{"name": file1.name}]) is False

        assert (
            FileFieldType().are_row_values_equal(
                [{"name": file1.name}, {"name": file2.name}], [{"name": file1.name}]
            )
            is False
        )


@pytest.mark.django_db
@pytest.mark.field_file
def test_file_field_type_in_formulas(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    with freeze_time("2023-01-01 12:00:00"):
        user_file_1 = data_fixture.create_user_file(
            mime_type="text/plain", size=100, original_name="a.txt"
        )
        user_file_2 = data_fixture.create_user_file(
            is_image=True, image_width=200, image_height=300, original_name="b.gif"
        )
        user_file_3 = data_fixture.create_user_file()
    grid_view = data_fixture.create_grid_view(user=user, table=table)

    row_handler = RowHandler()

    file_field = FieldHandler().create_field(
        user, table, "file", name="file", primary=True
    )

    assert FileField.objects.all().count() == 1
    model = table.get_model()

    row = row_handler.create_row(
        user=user,
        table=table,
        values={
            file_field.db_column: [
                {"name": user_file_1.name},
                {"name": user_file_2.name},
            ]
        },
        model=model,
    )
    formula_field = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="file_formula",
        formula=f"field('{file_field.name}')",
    )
    row.refresh_from_db()
    file_values = getattr(row, file_field.db_column)
    expected_first_file_contents = {
        "image_height": None,
        "image_width": None,
        "is_image": False,
        "mime_type": "text/plain",
        "name": AnyStr(),
        "size": 100,
        "uploaded_at": "2023-01-01T12:00:00+00:00",
        "visible_name": "a.txt",
    }
    assert file_values[0] == expected_first_file_contents
    assert file_values[1] == {
        "image_height": 300,
        "image_width": 200,
        "is_image": True,
        "mime_type": "image/gif",
        "name": AnyStr(),
        "size": 100,
        "uploaded_at": "2023-01-01T12:00:00+00:00",
        "visible_name": "b.gif",
    }

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert (
        response_json["results"][0][formula_field.db_column][0]["visible_name"]
        == user_file_1.original_name
    )

    expected_first_file_serialized_contents = {
        "image_height": None,
        "image_width": None,
        "is_image": False,
        "mime_type": "text/plain",
        "name": AnyStr(),
        "size": 100,
        "thumbnails": None,
        "uploaded_at": "2023-01-01T12:00:00+00:00",
        "url": AnyStr(),
        "visible_name": "a.txt",
    }

    formula_to_expected = [
        (
            f"index(field('{file_field.name}'), 0)",
            expected_first_file_serialized_contents,
        ),
        (
            f"get_file_visible_name(index(field('{file_field.name}'), 0))",
            user_file_1.original_name,
        ),
        (f"is_image(index(field('{file_field.name}'), 0))", False),
        (f"get_image_height(index(field('{file_field.name}'), 0))", None),
        (f"get_image_width(index(field('{file_field.name}'), 0))", None),
        (f"get_file_size(index(field('{file_field.name}'), 0))", "100"),
        (f"get_file_mime_type(index(field('{file_field.name}'), 0))", "text/plain"),
        (f"is_image(index(field('{file_field.name}'), 1))", True),
        (f"get_image_height(index(field('{file_field.name}'), 1))", "300"),
        (f"get_image_width(index(field('{file_field.name}'), 1))", "200"),
    ]

    for formula, expected in formula_to_expected:
        formula_field = FieldHandler().update_field(
            user,
            formula_field,
            formula=formula,
        )
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
        response_json = response.json()
        assert response.status_code == HTTP_200_OK, response_json
        assert (
            response_json["results"][0][formula_field.db_column] == expected
        ), f"Failed for {formula} but was " + str(response_json["results"][0])

    formula_field3 = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="file_formula3",
        formula=f"get_file_count(field('{file_field.name}'))",
    )
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json["results"][0][formula_field3.db_column] == "2"


@pytest.mark.django_db
@pytest.mark.field_file
def test_file_field_type_in_double_formula(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    user_file_1 = data_fixture.create_user_file(
        mime_type="text/plain", size=100, original_name="a.txt"
    )
    grid_view = data_fixture.create_grid_view(user=user, table=table)

    row_handler = RowHandler()

    file_field = FieldHandler().create_field(
        user, table, "file", name="file", primary=True
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            file_field.db_column: [
                {"name": user_file_1.name},
            ]
        },
    )
    formula_field_1 = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="file_formula",
        formula=f"field('{file_field.name}')",
    )
    formula_field_2 = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="file_formula_2",
        formula=f"field('{formula_field_1.name}')",
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    result = response_json["results"][0]

    assert (
        result[f"field_{formula_field_1.id}"] == result[f"field_{formula_field_2.id}"]
    )


@pytest.mark.django_db
@pytest.mark.field_file
def test_filtering_file_field_type(data_fixture, api_client, django_assert_num_queries):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    with freeze_time("2023-01-01 12:00:00"):
        user_file_1 = data_fixture.create_user_file(mime_type="text/plain", size=100)
        user_file_2 = data_fixture.create_user_file(
            is_image=True, image_width=200, image_height=300
        )
        user_file_3 = data_fixture.create_user_file()
    grid_view = data_fixture.create_grid_view(user=user, table=table)

    row_handler = RowHandler()

    file_field = FieldHandler().create_field(
        user, table, "file", name="file", primary=True
    )

    assert FileField.objects.all().count() == 1
    model = table.get_model(attribute_names=True)

    row = row_handler.create_row(
        user=user,
        table=table,
        values={"file": [{"name": user_file_1.name}, {"name": user_file_2.name}]},
        model=model,
    )
    assert row.file[0]["visible_name"] == user_file_1.original_name
    del row.file[0]["visible_name"]
    assert row.file[0] == user_file_1.serialize()

    data_fixture.create_view_filter(
        user,
        view=grid_view,
        field=file_field,
        type="has_file_type",
        value="image",
    )
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert (
        response_json["results"][0][file_field.db_column][0]["visible_name"]
        == user_file_1.original_name
    )


@pytest.mark.django_db
@pytest.mark.field_file
def test_filtering_file_formula_field_type(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    with freeze_time("2023-01-01 12:00:00"):
        user_file_1 = data_fixture.create_user_file(mime_type="text/plain", size=100)
        user_file_2 = data_fixture.create_user_file(
            is_image=True, image_width=200, image_height=300
        )
        user_file_3 = data_fixture.create_user_file()
    grid_view = data_fixture.create_grid_view(user=user, table=table)

    row_handler = RowHandler()

    file = FieldHandler().create_field(user, table, "file", name="file", primary=True)

    assert FileField.objects.all().count() == 1
    model = table.get_model(attribute_names=True)

    row = row_handler.create_row(
        user=user,
        table=table,
        values={"file": [{"name": user_file_1.name}, {"name": user_file_2.name}]},
        model=model,
    )
    assert row.file[0]["visible_name"] == user_file_1.original_name
    del row.file[0]["visible_name"]
    assert row.file[0] == user_file_1.serialize()

    formula_field = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="file_formula",
        formula=f"field('{file.name}')",
    )

    data_fixture.create_view_filter(
        user,
        view=grid_view,
        field=formula_field,
        type="has_file_type",
        value="image",
    )
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert (
        response_json["results"][0][formula_field.db_column][0]["visible_name"]
        == user_file_1.original_name
    )
