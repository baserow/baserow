from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.shortcuts import reverse

import pytest
from faker import Faker
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    CreatedOnField,
    DateField,
    EmailField,
    FileField,
    FormulaField,
    LastModifiedField,
    LongTextField,
    LookupField,
    MultipleSelectField,
    NumberField,
    PhoneNumberField,
    SelectOption,
    URLField,
)


@pytest.mark.django_db
def test_text_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Old name", text_default="Default"
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": text_field.id}),
        {"name": "New name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["text_default"] == "Default"


@pytest.mark.django_db
def test_long_text_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    fake = Faker()
    text = fake.text()

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Long text", "type": "long_text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "long_text"
    assert LongTextField.objects.all().count() == 1
    field_id = response_json["id"]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_id}),
        {"name": "Long text 2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": text},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == text

    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.long_text_2 == text

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.long_text_2 == ""

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] is None

    row = model.objects.all().last()
    assert row.long_text_2 is None

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] is None

    row = model.objects.all().last()
    assert row.long_text_2 is None

    url = reverse("api:database:fields:item", kwargs={"field_id": field_id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert LongTextField.objects.all().count() == 0


@pytest.mark.django_db
def test_url_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "URL", "type": "url"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "url"
    assert URLField.objects.all().count() == 1
    field_id = response_json["id"]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_id}),
        {"name": "URL2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": "https://test.nl"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == "https://test.nl"

    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.url2 == "https://test.nl"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.url2 == ""

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.url2 == ""

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.url2 == ""

    url = reverse("api:database:fields:item", kwargs={"field_id": field_id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert URLField.objects.all().count() == 0


@pytest.mark.django_db
def test_date_field_type_invalid_force_timezone_offset(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    date_field = data_fixture.create_date_field(table=table)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "date",
            "type": "date",
            "date_include_time": True,
            "date_force_timezone_offset": 60,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "date_force_timezone_offset" in response.json()["detail"]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": date_field.id}),
        {"date_force_timezone_offset": 60},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "date_force_timezone_offset" in response.json()["detail"]

    date_field.date_include_time = True
    date_field.save()


@pytest.mark.django_db
def test_date_field_type_force_timezone_offset(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    datetime_field = data_fixture.create_date_field(table=table, date_include_time=True)
    table_model = table.get_model()

    row_1 = table_model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-01 00:00Z"}
    )
    row_2 = table_model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-01 23:30Z"}
    )
    row_3 = table_model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-02 15:00Z"}
    )
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()

    utc_offset = 60
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": datetime_field.id}),
        {
            "date_force_timezone": "Europe/Rome",
            "date_force_timezone_offset": utc_offset,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    def row_datetime_updated(row):
        prev_datetime = getattr(row, f"field_{datetime_field.id}")
        row.refresh_from_db()
        new_datetime = getattr(row, f"field_{datetime_field.id}")
        return new_datetime == (prev_datetime + timedelta(minutes=utc_offset))

    # all the rows has been updated, adding 60 minutes to the time
    assert row_datetime_updated(row_1)
    assert row_datetime_updated(row_2)
    assert row_datetime_updated(row_3)

    # the offset can be negative
    utc_offset = -180
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": datetime_field.id}),
        {"date_force_timezone": "Etc/GMT-2", "date_force_timezone_offset": utc_offset},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # all the rows has been updated, adding 60 minutes to the time
    assert row_datetime_updated(row_1)
    assert row_datetime_updated(row_2)
    assert row_datetime_updated(row_3)


@pytest.mark.django_db
def test_date_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Date", "type": "date"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "date"
    assert DateField.objects.all().count() == 1
    date_field_id = response_json["id"]

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Datetime", "type": "date", "date_include_time": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "date"
    assert DateField.objects.all().count() == 2
    date_time_field_id = response_json["id"]

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{date_field_id}": "2020-04-01 12:00",
            f"field_{date_time_field_id}": "2020-04-44",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"][f"field_{date_field_id}"][0]["code"] == "invalid"
    assert response_json["detail"][f"field_{date_time_field_id}"][0]["code"] == (
        "invalid"
    )

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{date_field_id}": "2020-04-01",
            f"field_{date_time_field_id}": "2020-04-01 14:30:20",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{date_field_id}"] == "2020-04-01"
    assert response_json[f"field_{date_time_field_id}"] == "2020-04-01T14:30:20Z"

    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.date == date(2020, 4, 1)
    assert row.datetime == datetime(2020, 4, 1, 14, 30, 20, tzinfo=timezone.utc)

    url = reverse("api:database:fields:item", kwargs={"field_id": date_time_field_id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert DateField.objects.all().count() == 1


@pytest.mark.django_db
def test_email_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Email", "type": "email"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "email"
    assert EmailField.objects.all().count() == 1
    field_id = response_json["id"]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_id}),
        {"name": "Email2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": "test@test.nl"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == "test@test.nl"

    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.email2 == "test@test.nl"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.email2 == ""

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.email2 == ""

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.email2 == ""

    email = reverse("api:database:fields:item", kwargs={"field_id": field_id})
    response = api_client.delete(email, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert EmailField.objects.all().count() == 0


@pytest.mark.django_db
def test_file_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    grid = data_fixture.create_grid_view(table=table)
    with freeze_time("2020-01-01 12:00"):
        user_file_1 = data_fixture.create_user_file(
            original_name="test.txt",
            original_extension="txt",
            unique="sdafi6WtHfnDrU6S1lQKh9PdC7PeafCA",
            size=10,
            mime_type="text/plain",
            is_image=True,
            image_width=1920,
            image_height=1080,
            sha256_hash=(
                "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
            ),
        )

    user_file_2 = data_fixture.create_user_file()
    user_file_3 = data_fixture.create_user_file()

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "File", "type": "file"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "file"
    assert FileField.objects.all().count() == 1
    field_id = response_json["id"]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_id}),
        {"name": "File2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == []

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == []

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": [{"without_name": "test"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": [{"name": "an__invalid__name.jpg"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"][f"field_{field_id}"][0]["code"] == "invalid"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": [{"name": "not_existing.jpg"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"] == "The user files ['not_existing.jpg'] do not exist."
    )

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": [{"name": user_file_1.name, "is_image": True}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert (
        response_json[f"field_{field_id}"][0]["visible_name"]
        == user_file_1.original_name
    )
    assert response_json[f"field_{field_id}"][0]["name"] == (
        "sdafi6WtHfnDrU6S1lQKh9PdC7PeafCA_"
        "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e.txt"
    )
    assert response_json[f"field_{field_id}"][0]["size"] == 10
    assert response_json[f"field_{field_id}"][0]["mime_type"] == "text/plain"
    assert response_json[f"field_{field_id}"][0]["is_image"] is True
    assert response_json[f"field_{field_id}"][0]["image_width"] == 1920
    assert response_json[f"field_{field_id}"][0]["image_height"] == 1080
    assert response_json[f"field_{field_id}"][0]["uploaded_at"] == (
        "2020-01-01T12:00:00+00:00"
    )
    assert "localhost:8000" in response_json[f"field_{field_id}"][0]["url"]
    assert len(response_json[f"field_{field_id}"][0]["thumbnails"]) == 1
    assert (
        "localhost:8000"
        in response_json[f"field_{field_id}"][0]["thumbnails"]["tiny"]["url"]
    )
    assert (
        "sdafi6WtHfnDrU6S1lQKh9PdC7PeafCA_"
        "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e.txt"
        in response_json[f"field_{field_id}"][0]["thumbnails"]["tiny"]["url"]
    )
    assert "tiny" in response_json[f"field_{field_id}"][0]["thumbnails"]["tiny"]["url"]
    assert response_json[f"field_{field_id}"][0]["thumbnails"]["tiny"]["width"] == 21
    assert response_json[f"field_{field_id}"][0]["thumbnails"]["tiny"]["height"] == 21
    assert "original_name" not in response_json
    assert "original_extension" not in response_json
    assert "sha256_hash" not in response_json

    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": response_json["id"]},
        ),
        {
            f"field_{field_id}": [
                {"name": user_file_3.name},
                {"name": user_file_2.name, "visible_name": "new_name_1.txt"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[f"field_{field_id}"][0]["name"] == user_file_3.name
    assert (
        response_json[f"field_{field_id}"][0]["visible_name"]
        == user_file_3.original_name
    )
    assert "localhost:8000" in response_json[f"field_{field_id}"][0]["url"]
    assert response_json[f"field_{field_id}"][0]["is_image"] is False
    assert response_json[f"field_{field_id}"][0]["image_width"] is None
    assert response_json[f"field_{field_id}"][0]["image_height"] is None
    assert response_json[f"field_{field_id}"][0]["thumbnails"] is None
    assert response_json[f"field_{field_id}"][1]["name"] == user_file_2.name
    assert response_json[f"field_{field_id}"][1]["visible_name"] == "new_name_1.txt"

    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": response_json["id"]},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": response_json["id"]},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[f"field_{field_id}"][0]["name"] == user_file_3.name
    assert (
        response_json[f"field_{field_id}"][0]["visible_name"]
        == user_file_3.original_name
    )
    assert "localhost:8000" in response_json[f"field_{field_id}"][0]["url"]
    assert response_json[f"field_{field_id}"][1]["name"] == user_file_2.name
    assert response_json[f"field_{field_id}"][1]["visible_name"] == "new_name_1.txt"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) == 3
    assert response_json["results"][0][f"field_{field_id}"] == []
    assert response_json["results"][1][f"field_{field_id}"] == []
    assert (
        response_json["results"][2][f"field_{field_id}"][0]["name"] == user_file_3.name
    )
    assert (
        "localhost:8000" in response_json["results"][2][f"field_{field_id}"][0]["url"]
    )
    assert (
        response_json["results"][2][f"field_{field_id}"][1]["name"] == user_file_2.name
    )

    # We also need to check if the grid view returns the correct url because the
    # request context must be provided there in order to work.
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) == 3
    assert response_json["results"][0][f"field_{field_id}"] == []
    assert response_json["results"][1][f"field_{field_id}"] == []
    assert (
        response_json["results"][2][f"field_{field_id}"][0]["name"] == user_file_3.name
    )
    assert (
        "localhost:8000" in response_json["results"][2][f"field_{field_id}"][0]["url"]
    )
    assert (
        response_json["results"][2][f"field_{field_id}"][1]["name"] == user_file_2.name
    )


@pytest.mark.django_db
def test_number_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    # Create a positive integer field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "PositiveInt",
            "type": "number",
            "number_decimal_places": 0,
            "number_negative": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Make sure the field was created properly
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "number"
    assert NumberField.objects.all().count() == 1
    positive_int_field_id = response_json["id"]

    # Create a negative integer field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "NegativeInt",
            "type": "number",
            "number_decimal_places": 0,
            "number_negative": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Make sure the field was created properly
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "number"
    assert NumberField.objects.all().count() == 2
    negative_int_field_id = response_json["id"]

    # Create a positive decimal field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "PositiveDecimal",
            "type": "number",
            "number_negative": False,
            "number_decimal_places": 2,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Make sure the field was created properly
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "number"
    assert NumberField.objects.all().count() == 3
    positive_decimal_field_id = response_json["id"]

    # Create a negative decimal field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "NegativeDecimal",
            "type": "number",
            "number_negative": True,
            "number_decimal_places": 2,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Make sure the field was created properly
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "number"
    assert NumberField.objects.all().count() == 4
    negative_decimal_field_id = response_json["id"]

    # Test re-writing the name of a field. 'PositiveInt' is now called 'PositiveIntEdit'
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": positive_int_field_id}),
        {"name": "PositiveIntEdit"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # Add a row with correct values
    valid_pos_int = "99999999999999999999999999999999999999999999999999"
    valid_neg_int = "-99999999999999999999999999999999999999999999999999"
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{positive_int_field_id}": valid_pos_int,
            f"field_{negative_int_field_id}": valid_neg_int,
            f"field_{positive_decimal_field_id}": 1000.00,
            f"field_{negative_decimal_field_id}": -1000.00,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{positive_int_field_id}"] == valid_pos_int
    assert response_json[f"field_{negative_int_field_id}"] == valid_neg_int
    assert response_json[f"field_{positive_decimal_field_id}"] == "1000.00"
    assert response_json[f"field_{negative_decimal_field_id}"] == "-1000.00"

    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.positiveintedit == Decimal(valid_pos_int)
    assert row.negativeint == Decimal(valid_neg_int)
    assert row.positivedecimal == Decimal(1000.00)
    assert row.negativedecimal == Decimal(-1000.00)

    # Add a row with Nones'
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{positive_int_field_id}": None,
            f"field_{negative_int_field_id}": None,
            f"field_{positive_decimal_field_id}": None,
            f"field_{negative_decimal_field_id}": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{positive_int_field_id}"] is None
    assert response_json[f"field_{negative_int_field_id}"] is None
    assert response_json[f"field_{positive_decimal_field_id}"] is None
    assert response_json[f"field_{negative_decimal_field_id}"] is None

    row = model.objects.all().last()
    assert row.positiveintedit is None
    assert row.negativeint is None
    assert row.positivedecimal is None
    assert row.negativedecimal is None

    # Add a row with an integer that's too big
    invalid_pos_int = "999999999999999999999999999999999999999999999999999"
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{positive_int_field_id}": invalid_pos_int,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"][f"field_{positive_int_field_id}"][0]["code"]
        == "max_digits"
    )

    # Add a row with an integer that's too small
    invalid_neg_int = "-9999999999999999999999999999999999999999999999999999"
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{negative_int_field_id}": invalid_neg_int,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"][f"field_{positive_int_field_id}"][0]["code"]
        == "max_digits"
    )


@pytest.mark.django_db
def test_phone_number_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "phone", "type": "phone_number"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "phone_number"
    assert PhoneNumberField.objects.all().count() == 1
    field_id = response_json["id"]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_id}),
        {"name": "Phone"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    expected_phone_number = "+44761198672"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": expected_phone_number},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == expected_phone_number

    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.phone == expected_phone_number

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.phone == ""

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_id}": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.phone == ""

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{field_id}"] == ""

    row = model.objects.all().last()
    assert row.phone == ""

    email = reverse("api:database:fields:item", kwargs={"field_id": field_id})
    response = api_client.delete(email, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert PhoneNumberField.objects.all().count() == 0


@pytest.mark.django_db
def test_last_modified_field_type(api_client, data_fixture):
    time_under_test = "2021-08-10 12:00"

    user = data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    # first add text field so that there is already a row with an
    # updated_on value
    text_field = data_fixture.create_text_field(user=user, table=table)

    with freeze_time(time_under_test):
        token = data_fixture.generate_token(user)
        api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            {f"field_{text_field.id}": "Test Text"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    # now add a last_modified field with datetime
    with freeze_time(time_under_test):
        response = api_client.post(
            reverse("api:database:fields:list", kwargs={"table_id": table.id}),
            {
                "name": "Last",
                "type": "last_modified",
                "date_include_time": True,
                "timezone": "Europe/Berlin",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "last_modified"
    assert LastModifiedField.objects.all().count() == 1
    last_modified_field_id = response_json["id"]
    assert last_modified_field_id

    # verify that the timestamp is the same as the updated_on column
    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.last == row.updated_on

    # change the text_field value so that we can verify that the
    # last_modified column gets updated as well
    with freeze_time(time_under_test):
        response = api_client.patch(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row.id},
            ),
            {f"field_{text_field.id}": "test_second"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response.json()
    assert response.status_code == HTTP_200_OK

    last_datetime = row.last
    updated_on_datetime = row.updated_on

    assert last_datetime == updated_on_datetime

    with freeze_time(time_under_test):
        response = api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            {
                f"field_{last_modified_field_id}": "2021-08-05",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    with freeze_time(time_under_test):
        response = api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            {
                f"field_{last_modified_field_id}": "2021-08-09T14:14:33.574356Z",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_created_on_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    # first add text field so that there is already a row with an
    # updated_on and a created_on value
    text_field = data_fixture.create_text_field(user=user, table=table)

    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{text_field.id}": "Test Text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # now add a created_on field with datetime
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Create",
            "type": "created_on",
            "date_include_time": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "created_on"
    assert CreatedOnField.objects.all().count() == 1
    created_on_field_id = response_json["id"]
    assert created_on_field_id

    # verify that the timestamp is the same as the updated_on column
    model = table.get_model(attribute_names=True)
    row = model.objects.all().last()
    assert row.create == row.created_on

    # change the text_field value so that we can verify that the
    # created_on column does NOT get updated
    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        {f"field_{text_field.id}": "test_second"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response.json()
    assert response.status_code == HTTP_200_OK

    row = model.objects.all().last()
    create_datetime = row.create
    created_on_datetime = row.created_on

    assert create_datetime == created_on_datetime

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{created_on_field_id}": "2021-08-05",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{created_on_field_id}": "2021-08-09T14:14:33.574356Z",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_multiple_select_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Multi 1",
            "type": "multiple_select",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    field_1_id = response_json["id"]
    assert response_json["name"] == "Multi 1"
    assert response_json["type"] == "multiple_select"
    assert response_json["select_options"] == []
    assert MultipleSelectField.objects.all().count() == 1
    assert SelectOption.objects.all().count() == 0

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Multi 2",
            "type": "multiple_select",
            "select_options": [{"value": "Option 1", "color": "red"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    field_2_id = response_json["id"]
    select_options = SelectOption.objects.all()
    assert len(select_options) == 1
    assert select_options[0].field_id == field_2_id
    assert select_options[0].value == "Option 1"
    assert select_options[0].color == "red"
    assert select_options[0].order == 0
    assert response_json["name"] == "Multi 2"
    assert response_json["type"] == "multiple_select"
    assert response_json["select_options"] == [
        {"id": select_options[0].id, "value": "Option 1", "color": "red"}
    ]
    assert MultipleSelectField.objects.all().count() == 2

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_2_id}),
        {"name": "New Multi 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "New Multi 1"
    assert response_json["type"] == "multiple_select"
    assert response_json["select_options"] == [
        {"id": select_options[0].id, "value": "Option 1", "color": "red"}
    ]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_2_id}),
        {
            "name": "New Multi 1",
            "select_options": [
                {"id": select_options[0].id, "value": "Option 1 B", "color": "red 2"},
                {"value": "Option 2 B", "color": "blue 2"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    select_options = SelectOption.objects.all()
    assert len(select_options) == 2
    assert response_json["select_options"] == [
        {"id": select_options[0].id, "value": "Option 1 B", "color": "red 2"},
        {"id": select_options[1].id, "value": "Option 2 B", "color": "blue 2"},
    ]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_2_id}),
        {"name": "New Multi 1", "select_options": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert SelectOption.objects.all().count() == 0
    assert response_json["select_options"] == []

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_2_id}),
        {
            "name": "New Multi 1",
            "select_options": [
                {"value": "Option 1 B", "color": "red 2"},
                {"value": "Option 2 B", "color": "blue 2"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    select_options = SelectOption.objects.all()
    assert len(select_options) == 2

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": field_2_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert MultipleSelectField.objects.all().count() == 1
    assert SelectOption.objects.all().count() == 0

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_1_id}),
        {
            "select_options": [
                {"value": "Option 1", "color": "red"},
                {"value": "Option 2", "color": "blue"},
                {"value": "Option 3", "color": "green"},
                {"value": "Option 4", "color": "yellow"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    select_options = SelectOption.objects.all()
    assert len(select_options) == 4

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_1_id}": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"][f"field_{field_1_id}"][0]["code"] == "not_a_list"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_1_id}": "MissingOption"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "The provided select option value 'MissingOption' is not a valid select "
        "option."
    )

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_1_id}": [999999]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "The provided select option value '999999' is not a valid select option."
    )

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_1_id}": [select_options[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[f"field_{field_1_id}"][0]["id"] == select_options[0].id
    assert response_json[f"field_{field_1_id}"][0]["value"] == "Option 1"
    assert response_json[f"field_{field_1_id}"][0]["color"] == "red"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_1_id}": [select_options[2].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    row_id = response.json()["id"]

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_id}
        ),
        {f"field_{field_1_id}": [select_options[2].id, select_options[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    model = table.get_model()
    rows = list(model.objects.all().enhance_by_fields())
    assert len(rows) == 2

    field_cell = getattr(rows[1], f"field_{field_1_id}").all()
    assert field_cell[0].id == select_options[2].id
    assert field_cell[1].id == select_options[0].id

    # Create second multiple select field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Another Multi Field",
            "type": "multiple_select",
            "select_options": [
                {"value": "Option 1", "color": "red"},
                {"value": "Option 2", "color": "blue"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    field_2_id = response_json["id"]
    field_2_select_options = response_json["select_options"]
    all_select_options = SelectOption.objects.all()
    assert len(all_select_options) == 6
    assert MultipleSelectField.objects.all().count() == 2

    # Make sure we can create a row with just one field
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{field_2_id}": [field_2_select_options[0]["id"]]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response.json()
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_formula_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "'test'"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "formula"
    assert FormulaField.objects.all().count() == 1
    formula_field_id = response_json["id"]
    assert formula_field_id

    # Create a row
    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    # Verify the value of the formula field is the sql expression evaluated for that row
    model = table.get_model(attribute_names=True)
    row = model.objects.get()
    assert row.formula == "test"

    # You cannot modify a formula field row value
    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        {f"field_{formula_field_id}": "test_second"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "Field of type formula is read only and should not be set manually."
    )

    # You cannot create a row with a formula field value
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{formula_field_id}": "some value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "Field of type formula is read only and should not be set manually."
    )

    # You cannot create a field with an invalid formula
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "drop database baserow;"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_WITH_FORMULA"
    assert "Invalid syntax" in response_json["detail"]

    # You cannot create a field calling an invalid function
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "version()"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_WITH_FORMULA"
    assert (
        response_json["detail"]
        == "Error with formula: version is not a valid function."
    )


@pytest.mark.django_db
def test_lookup_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="p", table=table, primary=True
    )
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    looked_up_field = data_fixture.create_single_select_field(
        table=table2, name="lookupfield"
    )
    option_a = data_fixture.create_select_option(
        field=looked_up_field, value="A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=looked_up_field, value="B", color="red"
    )
    table2_model = table2.get_model(attribute_names=True)
    table2_model.objects.create(lookupfield=option_a, primaryfield="primary a")
    table2_model.objects.create(lookupfield=option_b, primaryfield="primary b")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "lookupfield",
            "type": "lookup",
            "through_field_name": linkrowfield.name,
            "target_field_name": looked_up_field.name,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json["type"] == "lookup"
    assert LookupField.objects.all().count() == 1
    lookup_field_id = response_json["id"]
    assert lookup_field_id

    # Create a row
    api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    # Verify the value is empty as there are no fields to lookup
    table_model = table.get_model(attribute_names=True)
    row = table_model.objects.get()
    assert row.lookupfield == []

    # You cannot modify a lookup field row value
    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        {
            f"field_{lookup_field_id}": [
                {"value": {"value": "some value", "id": 1, "color": "red"}}
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "Field of type lookup is read only and should not be set manually."
    )

    # You cannot create a row with a lookup field value
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{lookup_field_id}": [
                {"value": {"value": "some value", "id": 1, "color": "red"}}
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]
        == "Field of type lookup is read only and should not be set manually."
    )

    # You cannot create a lookup field without specifying through values
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "invalid", "type": "lookup"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_THROUGH_FIELD"

    # You cannot create a lookup field without specifying target values
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "invalid", "type": "lookup", "through_field_id": linkrowfield.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_TARGET_FIELD"

    # You cannot create a lookup field with a link row field in another table
    other_table_linkrowfield = data_fixture.create_link_row_field()
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_id": other_table_linkrowfield.id,
            "target_field_id": looked_up_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_THROUGH_FIELD"

    # You cannot create a lookup field with through field which is not a link field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_id": table_primary_field.id,
            "target_field_id": looked_up_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_THROUGH_FIELD"

    # You cannot create a lookup field with through field name which is not a link field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_name": table_primary_field.name,
            "target_field_id": looked_up_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_THROUGH_FIELD"

    # You cannot create a lookup field with an unknown through field name
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_name": "unknown",
            "target_field_id": looked_up_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_THROUGH_FIELD"

    # You cannot create a lookup field with an trashed through field id
    trashed_link_field = data_fixture.create_link_row_field(
        trashed=True, table=table, name="trashed"
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_id": trashed_link_field.id,
            "target_field_id": looked_up_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_THROUGH_FIELD"

    # You cannot create a lookup field with an trashed through field name
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_name": trashed_link_field.name,
            "target_field_id": looked_up_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_THROUGH_FIELD"

    # You cannot create a lookup field with an unknown target field name
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_name": linkrowfield.name,
            "target_field_name": "unknown",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_TARGET_FIELD"

    # You cannot create a lookup field with an trashed target field id
    field_that_cant_be_used = data_fixture.create_text_field(
        table=table2, trashed=True, name="trashed_looked_up"
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_name": linkrowfield.name,
            "target_field_id": field_that_cant_be_used.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_TARGET_FIELD"

    # You cannot create a lookup field with an trashed target field name
    field_that_cant_be_used = data_fixture.create_text_field(
        table=table2, trashed=True, name="trashed_looked_up"
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_name": linkrowfield.name,
            "target_field_name": field_that_cant_be_used.name,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_LOOKUP_TARGET_FIELD"

    # You cannot create a lookup field with a target field that cant be used in
    # formulas
    field_that_cant_be_used = data_fixture.create_password_field(table=table2)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_name": linkrowfield.name,
            "target_field_name": field_that_cant_be_used.name,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_WITH_FORMULA"

    # You cannot create a lookup field with a through field with invalid id
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_id": linkrowfield.name,
            "target_field_name": looked_up_field.name,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    # You cannot create a lookup field with a through field with invalid id
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "invalid",
            "type": "lookup",
            "through_field_id": linkrowfield.id,
            "target_field_id": looked_up_field.name,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
