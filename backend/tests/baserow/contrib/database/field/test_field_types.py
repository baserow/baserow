import os
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import override_settings

import pytest
from faker import Faker

from baserow.contrib.database.fields.field_types import (
    LinkRowFieldType,
    LookupFieldType,
    PhoneNumberFieldType,
    TextFieldType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    EmailField,
    LongTextField,
    PhoneNumberField,
    URLField,
)
from baserow.contrib.database.fields.registries import FieldType, field_type_registry
from baserow.contrib.database.fields.utils import DeferredForeignKeyUpdater
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import setup_interesting_test_table

# Note: this is not a definitive list, just the ones
# that originate from `setup_interesting_test_table`.
COMPATIBLE_FIELD_TYPE_VIEW_FILTER_TYPES = {
    "text": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "contains_word",
        "doesnt_contain_word",
        "length_is_lower_than",
        "empty",
        "not_empty",
    ],
    "long_text": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "contains_word",
        "doesnt_contain_word",
        "length_is_lower_than",
        "empty",
        "not_empty",
    ],
    "url": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "contains_word",
        "doesnt_contain_word",
        "length_is_lower_than",
        "empty",
        "not_empty",
    ],
    "email": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "contains_word",
        "doesnt_contain_word",
        "length_is_lower_than",
        "empty",
        "not_empty",
    ],
    "number": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "higher_than",
        "higher_than_or_equal",
        "lower_than",
        "lower_than_or_equal",
        "is_even_and_whole",
        "empty",
        "not_empty",
    ],
    "rating": [
        "equal",
        "not_equal",
        "higher_than",
        "higher_than_or_equal",
        "lower_than",
        "lower_than_or_equal",
        "empty",
        "not_empty",
    ],
    "boolean": ["equal", "not_equal", "boolean", "empty", "not_empty"],
    "date": [
        "contains",
        "contains_not",
        "date_equal",
        "date_before",
        "date_before_or_equal",
        "date_after_days_ago",
        "date_after",
        "date_after_or_equal",
        "date_not_equal",
        "date_equals_today",
        "date_before_today",
        "date_after_today",
        "date_within_days",
        "date_within_weeks",
        "date_within_months",
        "date_equals_days_ago",
        "date_equals_months_ago",
        "date_equals_years_ago",
        "date_equals_week",
        "date_equals_month",
        "date_equals_day_of_month",
        "date_equals_year",
        "date_is",
        "date_is_not",
        "date_is_before",
        "date_is_on_or_before",
        "date_is_after",
        "date_is_on_or_after",
        "date_is_within",
        "empty",
        "not_empty",
    ],
    "last_modified": [
        "contains",
        "contains_not",
        "date_equal",
        "date_before",
        "date_before_or_equal",
        "date_after_days_ago",
        "date_after",
        "date_after_or_equal",
        "date_not_equal",
        "date_equals_today",
        "date_before_today",
        "date_after_today",
        "date_within_days",
        "date_within_weeks",
        "date_within_months",
        "date_equals_days_ago",
        "date_equals_months_ago",
        "date_equals_years_ago",
        "date_equals_week",
        "date_equals_month",
        "date_equals_day_of_month",
        "date_equals_year",
        "date_is",
        "date_is_not",
        "date_is_before",
        "date_is_on_or_before",
        "date_is_after",
        "date_is_on_or_after",
        "date_is_within",
        "empty",
        "not_empty",
    ],
    "created_on": [
        "contains",
        "contains_not",
        "date_equal",
        "date_before",
        "date_before_or_equal",
        "date_after_days_ago",
        "date_after",
        "date_after_or_equal",
        "date_not_equal",
        "date_equals_today",
        "date_before_today",
        "date_after_today",
        "date_within_days",
        "date_within_weeks",
        "date_within_months",
        "date_equals_days_ago",
        "date_equals_months_ago",
        "date_equals_years_ago",
        "date_equals_week",
        "date_equals_month",
        "date_equals_day_of_month",
        "date_equals_year",
        "date_is",
        "date_is_not",
        "date_is_before",
        "date_is_on_or_before",
        "date_is_after",
        "date_is_on_or_after",
        "date_is_within",
        "empty",
        "not_empty",
    ],
    "last_modified_by": ["user_is", "user_is_not"],
    "created_by": ["user_is", "user_is_not"],
    "duration": [
        "equal",
        "not_equal",
        "higher_than",
        "higher_than_or_equal",
        "lower_than",
        "lower_than_or_equal",
        "empty",
        "not_empty",
    ],
    "link_row": [
        "link_row_has",
        "link_row_has_not",
        "link_row_contains",
        "link_row_not_contains",
        "empty",
        "not_empty",
    ],
    "file": [
        "filename_contains",
        "files_lower_than",
        "has_file_type",
        "empty",
        "not_empty",
    ],
    "single_select": [
        "contains",
        "contains_not",
        "contains_word",
        "doesnt_contain_word",
        "single_select_equal",
        "single_select_not_equal",
        "single_select_is_any_of",
        "single_select_is_none_of",
        "empty",
        "not_empty",
    ],
    "multiple_select": [
        "contains",
        "contains_not",
        "contains_word",
        "doesnt_contain_word",
        "empty",
        "not_empty",
        "multiple_select_has",
        "multiple_select_has_not",
    ],
    "multiple_collaborators": [
        "empty",
        "not_empty",
        "multiple_collaborators_has",
        "multiple_collaborators_has_not",
    ],
    "phone_number": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "length_is_lower_than",
        "empty",
        "not_empty",
    ],
    "formula": [
        "empty",
        "not_empty",
        "multiple_collaborators_has",
        "multiple_collaborators_has_not",
    ],
    "count": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "higher_than",
        "higher_than_or_equal",
        "lower_than",
        "lower_than_or_equal",
        "is_even_and_whole",
        "empty",
        "not_empty",
    ],
    "rollup": [
        "equal",
        "not_equal",
        "higher_than",
        "higher_than_or_equal",
        "lower_than",
        "lower_than_or_equal",
        "empty",
        "not_empty",
    ],
    "lookup": ["empty", "not_empty"],
    "uuid": ["equal", "not_equal"],
    "autonumber": [
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "higher_than",
        "higher_than_or_equal",
        "lower_than",
        "lower_than_or_equal",
        "is_even_and_whole",
    ],
    "password": ["empty", "not_empty"],
}


@pytest.mark.django_db
def test_import_export_text_field(data_fixture):
    id_mapping = {}

    text_field = data_fixture.create_text_field(
        name="Text name", text_default="Text default"
    )
    text_field_type = field_type_registry.get_by_model(text_field)
    text_serialized = text_field_type.export_serialized(text_field)
    text_field_imported = text_field_type.import_serialized(
        text_field.table,
        text_serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )
    assert text_field.id != text_field_imported.id
    assert text_field.name == text_field_imported.name
    assert text_field.description == text_field_imported.description
    assert text_field.order == text_field_imported.order
    assert text_field.primary == text_field_imported.primary
    assert text_field.text_default == text_field_imported.text_default
    assert id_mapping["database_fields"][text_field.id] == text_field_imported.id


@pytest.mark.django_db
def test_import_export_text_field_with_description(data_fixture):
    id_mapping = {}

    text_field = data_fixture.create_text_field(
        name="Text name", text_default="", description="test"
    )
    text_field_type = field_type_registry.get_by_model(text_field)
    text_serialized = text_field_type.export_serialized(text_field)
    text_field_imported = text_field_type.import_serialized(
        text_field.table,
        text_serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )
    assert text_field.id != text_field_imported.id
    assert text_field.description == text_field_imported.description == "test"


@pytest.mark.django_db
def test_import_export_immutable_field(data_fixture):
    id_mapping = {}

    text_field = data_fixture.create_text_field(
        name="Text name",
        text_default="Text default",
        read_only=True,
        immutable_type=True,
        immutable_properties=True,
    )
    text_field_type = field_type_registry.get_by_model(text_field)
    text_serialized = text_field_type.export_serialized(text_field)
    text_field_imported = text_field_type.import_serialized(
        text_field.table,
        text_serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )
    assert text_field.id != text_field_imported.id
    assert text_field.name == text_field_imported.name
    assert text_field.order == text_field_imported.order
    assert text_field.primary == text_field_imported.primary
    assert text_field.text_default == text_field_imported.text_default
    assert text_field.immutable_type is text_field_imported.immutable_type is True
    assert (
        text_field.immutable_properties
        is text_field_imported.immutable_properties
        is True
    )
    assert text_field.read_only == text_field_imported.read_only is True
    assert id_mapping["database_fields"][text_field.id] == text_field_imported.id


@pytest.mark.django_db
def test_import_export_formula_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    first_table = data_fixture.create_database_table(user=user)
    second_table = data_fixture.create_database_table(user=user)
    id_mapping = {}

    text_field = data_fixture.create_text_field(
        table=first_table, name="Text name", text_default="Text default"
    )
    formula_field = data_fixture.create_formula_field(
        table=first_table,
        name="formula field",
        formula=f"field('{text_field.name}')",
        formula_type="text",
    )
    formula_field_type = field_type_registry.get_by_model(formula_field)
    formula_serialized = formula_field_type.export_serialized(formula_field)
    assert formula_serialized["formula"] == "field('Text name')"

    text_field_in_diff_table = data_fixture.create_text_field(
        table=second_table, name="Text name", text_default="Text default"
    )
    formula_field_imported = formula_field_type.import_serialized(
        text_field_in_diff_table.table,
        formula_serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )
    assert formula_field.id != formula_field_imported.id
    assert formula_field.name == formula_field_imported.name
    assert formula_field.order == formula_field_imported.order
    assert formula_field.primary == formula_field_imported.primary
    assert formula_field_imported.formula == f"field('Text name')"
    assert id_mapping["database_fields"][formula_field.id] == formula_field_imported.id


@pytest.mark.django_db
def test_long_text_field_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, order=1, name="name")

    handler = FieldHandler()
    handler.create_field(
        user=user, table=table, type_name="long_text", name="description"
    )
    field = handler.update_field(user=user, field=field, new_type_name="long_text")

    assert len(LongTextField.objects.all()) == 2

    fake = Faker()
    text = fake.text()
    model = table.get_model(attribute_names=True)
    row = model.objects.create(description=text, name="Test")

    assert row.description == text
    assert row.name == "Test"

    handler.delete_field(user=user, field=field)
    assert len(LongTextField.objects.all()) == 1


@pytest.mark.django_db
def test_valid_url(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_database_table(user=user, database=table.database)
    field = data_fixture.create_text_field(table=table, order=1, name="name")
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field_handler.create_field(user=user, table=table, type_name="url", name="URL")
    assert len(URLField.objects.all()) == 1

    model = table.get_model(attribute_names=True)

    valid_urls = [
        "baserow.io",
        "ftp://baserow.io",
        "git://example.com/",
        "ws://baserow.io",
        "http://baserow.io",
        "https://baserow.io",
        "https://www.baserow.io",
        "HTTP://BASEROW.IO",
        "https://test.nl/test",
        "https://test.nl/test",
        "http://localhost",
        "//localhost",
        "https://test.nl/test?with=a-query&that=has-more",
        "https://test.nl/test",
        "http://-.~_!$&'()*+,;=%40:80%2f@example.com",
        "http://उदाहरण.परीक्षा",
        "http://foo.com/(something)?after=parens",
        "http://142.42.1.1/",
        "http://userid:password@example.com:65535/",
        "http://su--b.valid-----hyphens.com/",
        "//baserow.io/test",
        "127.0.0.1",
        "https://test.nl#test",
        "http://baserow.io/hrscywv4p/image/upload/c_fill,g_faces:center,"
        "h_128,w_128/yflwk7vffgwyyenftkr7.png",
        "https://gitlab.com/baserow/baserow/-/issues?row=nice/route",
        "https://web.archive.org/web/20210313191012/https://baserow.io/",
        "mailto:bram@baserow.io?test=test",
    ]
    invalid_urls = [
        "test",
        "test.",
        "localhost",
        "\nwww.test.nl",
        "www\n.test.nl",
        "www .test.nl",
        " www.test.nl",
    ]

    for invalid_url in invalid_urls:
        with pytest.raises(ValidationError):
            row_handler.create_row(
                user=user, table=table, values={"url": invalid_url}, model=model
            )

    for url in valid_urls:
        row_handler.create_row(
            user=user,
            table=table,
            values={"url": url, "name": url},
            model=model,
        )
    for bad_url in invalid_urls:
        row_handler.create_row(
            user=user,
            table=table,
            values={"url": "", "name": bad_url},
            model=model,
        )

    # Convert the text field to a url field so we can check how the conversion of
    # values went.
    field_handler.update_field(user=user, field=field, new_type_name="url")
    rows = model.objects.all()
    valid_urls_rows = rows[: len(valid_urls)]
    invalid_urls_rows = rows[len(valid_urls) :]

    for url, row in zip(valid_urls, valid_urls_rows):
        assert row.url == url
        assert row.name == url

    for row in invalid_urls_rows:
        assert row.url == ""
        assert row.name == ""


@pytest.mark.django_db
def test_valid_email(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_database_table(user=user, database=table.database)
    field = data_fixture.create_text_field(table=table, order=1, name="name")
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field_handler.create_field(user=user, table=table, type_name="email", name="email")

    model = table.get_model(attribute_names=True)

    invalid_emails = [
        "test@" + "a" * 246 + ".com",
        "@a",
        "a@",
        "not-an-email",
        "bram.test.nl",
        "invalid_email",
        "invalid@invalid@com",
        "\nhello@gmail.com",
        "asdds asdd@gmail.com",
    ]

    for invalid_email in invalid_emails:
        with pytest.raises(ValidationError):
            row_handler.create_row(
                user=user, table=table, values={"email": invalid_email}, model=model
            )

    valid_emails = [
        "test@" + "a" * 245 + ".com",
        "a@a",
        "用户@例子.广告",
        "अजय@डाटा.भारत",
        "квіточка@пошта.укр",
        "χρήστης@παράδειγμα.ελ",
        "Dörte@Sörensen.example.com",
        "коля@пример.рф",
        "bram@localhost",
        "bram@localhost.nl",
        "first_part_underscores_ok@hyphens-ok.com",
        "wierd@[1.1.1.1]",
        "bram.test.test@sub.domain.nl",
        "BRAM.test.test@sub.DOMAIN.nl",
    ]
    for email in valid_emails:
        row_handler.create_row(
            user=user,
            table=table,
            values={"email": email, "name": email},
            model=model,
        )
    for bad_email in invalid_emails:
        row_handler.create_row(
            user=user,
            table=table,
            values={"email": "", "name": bad_email},
            model=model,
        )

    # Convert the text field to a email field so we can check how the conversion of
    # values went.
    field_handler.update_field(user=user, field=field, new_type_name="email")
    rows = model.objects.all()
    valid_emails_rows = rows[: len(valid_emails)]
    invalid_emails_rows = rows[len(valid_emails) :]
    for email, row in zip(valid_emails, valid_emails_rows):
        assert row.email == email
        assert row.name == email

    for row in invalid_emails_rows:
        assert row.email == ""
        assert row.name == ""


@pytest.mark.django_db
def test_email_field_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_database_table(user=user, database=table.database)
    field = data_fixture.create_text_field(table=table, order=1, name="name")

    field_handler = FieldHandler()
    row_handler = RowHandler()

    field_2 = field_handler.create_field(
        user=user, table=table, type_name="email", name="email"
    )
    number = field_handler.create_field(
        user=user, table=table, type_name="number", name="number"
    )

    assert len(EmailField.objects.all()) == 1
    model = table.get_model(attribute_names=True)

    row_handler.create_row(
        user=user,
        table=table,
        values={
            "name": "a.very.STRANGE@email.address.coM",
            "email": "test@test.nl",
            "number": 5,
        },
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"name": "someuser", "email": "some@user.com", "number": 10},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"name": "http://www.baserow.io", "email": "bram@test.nl"},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"name": "NOT AN EMAIL", "email": "something@example.com"},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"name": "testing@nowhere.org", "email": ""},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            "email": None,
        },
        model=model,
    )

    # Convert the text field to a url field so we can check how the conversion of
    # values went.
    field_handler.update_field(user=user, field=field, new_type_name="email")
    field_handler.update_field(user=user, field=number, new_type_name="email")

    model = table.get_model(attribute_names=True)
    rows = model.objects.all()
    row_0, row_1, row_2, row_3, row_4, row_5 = rows

    assert row_0.name == "a.very.STRANGE@email.address.coM"
    assert row_0.email == "test@test.nl"
    assert row_0.number == ""

    assert row_1.name == ""
    assert row_1.email == "some@user.com"
    assert row_1.number == ""

    assert row_2.name == ""
    assert row_2.email == "bram@test.nl"
    assert row_2.number == ""

    assert row_3.name == ""
    assert row_3.email == "something@example.com"
    assert row_3.number == ""

    assert row_4.name == "testing@nowhere.org"
    assert row_4.email == ""
    assert row_4.number == ""

    assert row_5.name == ""
    assert row_5.email == ""
    assert row_5.number == ""

    field_handler.delete_field(user=user, field=field_2)
    assert len(EmailField.objects.all()) == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_phone_number_field_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_database_table(user=user, database=table.database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    text_field = field_handler.create_field(
        user=user, table=table, order=1, type_name="text", name="name"
    )
    phone_number_field = field_handler.create_field(
        user=user, table=table, type_name="phone_number", name="phonenumber"
    )
    email_field = field_handler.create_field(
        user=user, table=table, type_name="email", name="email"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, number_negative=True, name="number"
    )

    assert len(PhoneNumberField.objects.all()) == 1
    model = table.get_model(attribute_names=True)

    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user,
            table=table,
            values={"phonenumber": "invalid phone number"},
            model=model,
        )

    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user,
            table=table,
            values={"phonenumber": "Phone: 2312321 2349432 "},
            model=model,
        )
    with pytest.raises(ValidationError):
        row_handler.create_row(
            user=user,
            table=table,
            values={
                "phonenumber": "1" * (PhoneNumberFieldType.MAX_PHONE_NUMBER_LENGTH + 1)
            },
            model=model,
        )

    max_length_phone_number = "1" * PhoneNumberFieldType.MAX_PHONE_NUMBER_LENGTH
    row_handler.create_row(
        user=user,
        table=table,
        values={
            "name": "+45(1424) 322314 324234",
            "phonenumber": max_length_phone_number,
            "number": 1234534532,
            "email": "a_valid_email_to_be_blanked_after_conversion@email.com",
        },
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            "name": "some text which should be blanked out after conversion",
            "phonenumber": "1234567890 NnXx,+._*()#=;/ -",
            "number": 0,
        },
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            "name": max_length_phone_number,
            "phonenumber": "",
            "number": -10230450,
        },
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            "phonenumber": None,
            "name": "1" * (PhoneNumberFieldType.MAX_PHONE_NUMBER_LENGTH + 1),
        },
        model=model,
    )
    row_handler.create_row(user=user, table=table, values={}, model=model)

    # No actual database type change occurs here as a phone number field is also a text
    # field. Instead the after_update hook is being used to clear out invalid
    # phone numbers.
    field_handler.update_field(
        user=user, field=text_field, new_type_name="phone_number"
    )

    field_handler.update_field(
        user=user, field=number_field, new_type_name="phone_number"
    )
    field_handler.update_field(
        user=user, field=email_field, new_type_name="phone_number"
    )

    model = table.get_model(attribute_names=True)
    rows = model.objects.all()
    row_0, row_1, row_2, row_3, _ = rows

    assert row_0.name == "+45(1424) 322314 324234"
    assert row_0.phonenumber == max_length_phone_number
    assert row_0.number == "1234534532"
    assert row_0.email == ""

    assert row_1.name == ""
    assert row_1.phonenumber == "1234567890 NnXx,+._*()#=;/ -"
    assert row_1.number == "0"

    assert row_2.name == max_length_phone_number
    assert row_2.phonenumber == ""
    assert row_2.number == "-10230450"

    assert row_3.name == ""
    assert row_3.phonenumber == ""
    assert row_3.number == ""

    field_handler.delete_field(user=user, field=phone_number_field)
    assert len(PhoneNumberField.objects.all()) == 3


@pytest.mark.django_db
def test_human_readable_values(data_fixture):
    table, user, row, blank_row, context = setup_interesting_test_table(data_fixture)
    model = table.get_model()
    results = {}
    blank_results = {}
    for field in model._field_objects.values():
        value = field["type"].get_human_readable_value(
            getattr(row, field["name"]), field
        )
        results[field["field"].name] = value
        blank_value = field["type"].get_human_readable_value(
            getattr(blank_row, field["name"]), field
        )
        blank_results[field["field"].name] = blank_value

    blank_expected = {
        "boolean": "False",
        "date_eu": "",
        "date_us": "",
        "datetime_eu": "",
        "datetime_us": "",
        "datetime_eu_tzone_visible": "",
        "datetime_eu_tzone_hidden": "",
        "last_modified_date_eu": "02/01/2021",
        "last_modified_date_us": "01/02/2021",
        "last_modified_datetime_eu": "02/01/2021 12:00",
        "last_modified_datetime_us": "01/02/2021 12:00",
        "last_modified_datetime_eu_tzone": "02/01/2021 13:00",
        "created_on_date_eu": "02/01/2021",
        "created_on_date_us": "01/02/2021",
        "created_on_datetime_eu": "02/01/2021 12:00",
        "created_on_datetime_us": "01/02/2021 12:00",
        "created_on_datetime_eu_tzone": "02/01/2021 13:00",
        "decimal_link_row": "",
        "email": "",
        "file": "",
        "file_link_row": "",
        "link_row": "",
        "link_row_without_related": "",
        "long_text": "",
        "negative_decimal": "",
        "negative_int": "",
        "phone_number": "",
        "positive_decimal": "",
        "positive_int": "",
        "rating": "0",
        "self_link_row": "",
        "single_select": "",
        "multiple_select": "",
        "multiple_collaborators": "",
        "multiple_collaborators_link_row": "",
        "text": "",
        "url": "",
        "formula_bool": "True",
        "formula_date": "2020-01-01",
        "formula_dateinterval": "1d 0:00",
        "formula_decimal": "33.3333333333",
        "formula_email": "",
        "formula_int": "1",
        "formula_singleselect": "",
        "formula_text": "test FORMULA",
        "formula_link_url_only": "https://google.com",
        "formula_link_with_label": "label (https://google.com)",
        "formula_multipleselect": "",
        "formula_multiple_collaborators": "",
        "lookup": "",
        "multiple_collaborators_lookup": "",
        "autonumber": "1",
        "duration_rollup_sum": "0:00",
        "duration_rollup_avg": "0:00",
    }

    for key, value in blank_expected.items():
        assert blank_results[key] == value, (key, blank_results[key], value)

    expected = {
        "boolean": "True",
        "date_eu": "01/02/2020",
        "date_us": "02/01/2020",
        "datetime_eu": "01/02/2020 01:23",
        "datetime_us": "02/01/2020 01:23",
        "datetime_eu_tzone_visible": "01/02/2020 02:23",
        "datetime_eu_tzone_hidden": "01/02/2020 02:23",
        "last_modified_date_eu": "02/01/2021",
        "last_modified_date_us": "01/02/2021",
        "last_modified_datetime_eu": "02/01/2021 12:00",
        "last_modified_datetime_us": "01/02/2021 12:00",
        "last_modified_datetime_eu_tzone": "02/01/2021 13:00",
        "created_on_date_eu": "02/01/2021",
        "created_on_date_us": "01/02/2021",
        "created_on_datetime_eu": "02/01/2021 12:00",
        "created_on_datetime_us": "01/02/2021 12:00",
        "created_on_datetime_eu_tzone": "02/01/2021 13:00",
        "decimal_link_row": "1.234, -123.456, unnamed row 3",
        "email": "test@example.com",
        "file": "a.txt, b.txt",
        "file_link_row": "name.txt, unnamed row 2",
        "link_row": "linked_row_1, linked_row_2, ",
        "long_text": "long_text",
        "negative_decimal": "-1.2",
        "negative_int": "-1",
        "phone_number": "+4412345678",
        "positive_decimal": "1.2",
        "positive_int": "1",
        "rating": "3",
        "self_link_row": "unnamed row 1",
        "link_row_without_related": "linked_row_1, linked_row_2",
        "single_select": "A",
        "multiple_select": "D, C, E",
        "multiple_collaborators": "User2 <user2@example.com>, User3 <user3@example.com>",
        "multiple_collaborators_link_row": "User2 <user2@example.com>, User3 <user3@example.com>, User2 <user2@example.com>",
        "text": "text",
        "url": "https://www.google.com",
        "formula_bool": "True",
        "formula_date": "2020-01-01",
        "formula_dateinterval": "1d 0:00",
        "formula_decimal": "33.3333333333",
        "formula_email": "test@example.com",
        "formula_int": "1",
        "formula_singleselect": "A",
        "formula_text": "test FORMULA",
        "formula_link_url_only": "https://google.com",
        "formula_link_with_label": "label (https://google.com)",
        "formula_multipleselect": "C, D, E",
        "formula_multiple_collaborators": "User2 <user2@example.com>, User3 <user3@example.com>",
        "lookup": "linked_row_1, linked_row_2, ",
        "multiple_collaborators_lookup": "User2 <user2@example.com>, User3 <user3@example.com>, User2 <user2@example.com>",
        "autonumber": "2",
        "duration_rollup_sum": "0:04",
        "duration_rollup_avg": "0:02",
    }

    for key, value in expected.items():
        assert results[key] == value, (key, results[key], value)


@pytest.mark.django_db
def test_import_export_lookup_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    target_field = data_fixture.create_text_field(name="target", table=table_b)
    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)
    row_1 = table_b_model.objects.create(primary="1", target="target 1")
    row_2 = table_b_model.objects.create(primary="2", target="target 2")

    row_a = table_a_model.objects.create(primary="a")
    row_a.link.add(row_1.id)
    row_a.link.add(row_2.id)
    row_a.save()

    lookup = FieldHandler().create_field(
        user,
        table_a,
        "lookup",
        name="lookup",
        through_field_name="link",
        target_field_name="target",
    )
    lookup_field_type = field_type_registry.get_by_model(lookup)
    lookup_serialized = lookup_field_type.export_serialized(lookup)
    assert lookup_serialized["target_field_id"] == target_field.id
    assert lookup_serialized["target_field_name"] == target_field.name
    assert lookup_serialized["through_field_id"] == link_field.id
    assert lookup_serialized["through_field_name"] == link_field.name

    id_mapping = {
        "database_fields": {
            link_field.id: link_field.id,
            target_field.id: target_field.id,
        }
    }

    lookup.name = "rename to prevent import clash"
    lookup.save()

    deferred_field_fk_updater = DeferredForeignKeyUpdater()
    lookup_field_imported = lookup_field_type.import_serialized(
        table_a,
        lookup_serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        deferred_field_fk_updater,
    )
    assert lookup.id != lookup_field_imported.id
    assert lookup_field_imported.name == "lookup"
    assert lookup_field_imported.order == lookup.order
    assert lookup_field_imported.primary == lookup.primary
    assert lookup_field_imported.formula == lookup.formula
    assert lookup_field_imported.through_field is None
    assert lookup_field_imported.target_field is None
    assert lookup_field_imported.through_field_name == lookup.through_field_name
    assert lookup_field_imported.target_field_name == lookup.target_field_name

    deferred_field_fk_updater.run_deferred_fk_updates(id_mapping, "database_fields")
    lookup_field_imported.refresh_from_db()
    assert lookup_field_imported.through_field == lookup.through_field
    assert lookup_field_imported.target_field == lookup.target_field
    assert lookup_field_imported.through_field_name == lookup.through_field_name
    assert lookup_field_imported.target_field_name == lookup.target_field_name

    assert id_mapping["database_fields"][lookup.id] == lookup_field_imported.id


@pytest.mark.django_db
def test_lookup_field_get_field_dependencies_import_serialized_broken_lookup(
    data_fixture,
):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target_field = data_fixture.create_text_field(name="target", table=table_b)
    lookup_field = FieldHandler().create_field(
        user,
        table_a,
        "lookup",
        name="lookup",
        through_field_name="link",
        target_field_name="target",
    )

    serialized_field = LookupFieldType().export_serialized(lookup_field)
    serialized_fields_map = {
        link_field.id: LinkRowFieldType().export_serialized(link_field),
        target_field.id: TextFieldType().export_serialized(target_field),
    }
    primary_table_fields_map = {}

    # the dependencies are listed normally when lookup is valid
    field_deps = LookupFieldType().get_field_depdendencies_before_import_serialized(
        serialized_field, serialized_fields_map, primary_table_fields_map
    )
    assert field_deps == set(
        [
            (
                "target",
                "link",
            ),
        ]
    )

    # lookup is broken
    FieldHandler().delete_field(user, link_field)
    lookup_field.refresh_from_db()

    serialized_field = LookupFieldType().export_serialized(lookup_field)
    serialized_fields_map = {
        link_field.id: LinkRowFieldType().export_serialized(link_field),
        target_field.id: TextFieldType().export_serialized(target_field),
    }
    primary_table_fields_map = {}

    field_deps = LookupFieldType().get_field_depdendencies_before_import_serialized(
        serialized_field, serialized_fields_map, primary_table_fields_map
    )
    assert field_deps is None


def test_field_types_with_get_order_have_get_value_for_filter():
    for field_type in field_type_registry.get_all():
        if field_type.__class__.get_order.__code__ is not FieldType.get_order.__code__:
            assert (
                field_type.__class__.get_value_for_filter.__code__
                is not FieldType.get_value_for_filter.__code__
            )


def test_field_types_with_get_value_for_filter_have_get_order():
    for field_type in field_type_registry.get_all():
        if (
            field_type.__class__.get_value_for_filter.__code__
            is not FieldType.get_value_for_filter.__code__
        ):
            assert (
                field_type.__class__.get_order.__code__
                is not FieldType.get_order.__code__
            )


@pytest.mark.django_db
def test_text_field_type_get_order(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(
        dir_path + "/../../../../../../tests/all_chars.txt", mode="r", encoding="utf-8"
    ) as f:
        all_chars = f.read()
    with open(
        dir_path + "/../../../../../../tests/sorted_chars.txt",
        mode="r",
        encoding="utf-8",
    ) as f:
        sorted_chars = f.read()

    model.objects.bulk_create(
        [model(**{f"field_{field.id}": char}) for char in all_chars]
    )

    queryset = model.objects.all().order_by_fields_string(f"field_{field.id}")
    result = ""
    for char in queryset:
        result += getattr(char, f"field_{field.id}")

    assert result == sorted_chars


@pytest.mark.django_db
@override_settings(PG_FULLTEXT_SEARCH_ENABLED=False)
def test_tsv_not_created(data_fixture):
    id_mapping = {}

    table = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(
        name="Text name", text_default="Text default", table=table
    )
    text_field_type = field_type_registry.get_by_model(text_field)
    text_serialized = text_field_type.export_serialized(text_field)
    text_field_imported = text_field_type.import_serialized(
        table,
        text_serialized,
        ImportExportConfig(include_permission_data=True, reduce_disk_space_usage=False),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )
    assert text_field_imported.tsvector_column_created is False


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_field_type_prepare_db_value_with_invalid_values(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field_handler = FieldHandler()
    # those fields require additional configuration or accept any text
    # so they are not suitable for this test
    excluded = ["ai", "text", "long_text", "boolean", "link_row", "password"]

    test_payload = "invalid---"

    for field_type in [
        f
        for f in field_type_registry.get_all()
        if not f.read_only and f.type not in excluded
    ]:
        field_type_name = field_type.type
        field_name = f"Field {field_type_name}"
        field = field_handler.create_field(
            user=user,
            table=table,
            type_name=field_type.type,
            name=field_name,
        )

        with pytest.raises(ValidationError):
            field_type.prepare_value_for_db(field, test_payload)


@pytest.mark.parametrize(
    "field_type",
    [
        ft
        for ft in field_type_registry.get_all()
        if ft.type in COMPATIBLE_FIELD_TYPE_VIEW_FILTER_TYPES
    ],
)
@patch("baserow.contrib.database.fields.registries.FieldTypeRegistry.get_by_model")
def test_field_type_check_can_filter_by(mock_get_by_model, field_type):
    mock_get_by_model.return_value = field_type
    has_compatible_view_filters = (
        len(COMPATIBLE_FIELD_TYPE_VIEW_FILTER_TYPES[field_type.type]) > 0
    )
    assert (
        field_type.check_can_filter_by(Mock(type=field_type.type))
        == has_compatible_view_filters
    )


@pytest.mark.django_db
def test_number_field_type_export_with_nan_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()

    number_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="number",
        number_decimal_places=0,
    )

    field_type = field_type_registry.get_by_model(number_field)
    field_object = {"field": number_field, "type": field_type, "name": "number"}
    value = float("nan")
    export_value = field_type.get_export_value(value, field_object)

    assert export_value == "NaN"


@pytest.mark.django_db
def test_number_field_type_export_with_nan_value_and_formatting(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()

    number_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="number",
        number_decimal_places=0,
        number_prefix="$",
        number_suffix=" USD",
        number_separator="SPACE_COMMA",
    )

    field_type = field_type_registry.get_by_model(number_field)
    field_object = {"field": number_field, "type": field_type, "name": "number"}
    value = float("nan")
    export_value = field_type.get_export_value(value, field_object)

    assert export_value == "NaN"


@pytest.mark.django_db
def test_all_fields_with_db_index_have_index(data_fixture):
    table, user, row, blank_row, context = setup_interesting_test_table(data_fixture)
    field_handler = FieldHandler()
    model = table.get_model()
    for field_object in model._field_objects.values():
        field = field_object["field"]
        field_type = field_object["type"]
        if field_type.can_have_db_index(field):
            field_handler.update_field(
                user=user, table=table, field=field, db_index=True
            )

    table.refresh_from_db()
    model = table.get_model()
    table_name = model._meta.db_table

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = %s
        """,
            [table_name],
        )
        indexes = cursor.fetchall()

    for field_object in model._field_objects.values():
        field = field_object["field"]
        field_type = field_object["type"]
        if field_type.can_have_db_index(field):
            model_field = model._meta.get_field(field_object["name"])
            index_name = f"database_table_{table.id}_{model_field.db_column}_"
            assert any(
                indexdef[0].startswith(index_name) for indexdef in indexes
            ), f"{index_name} not found in indexes"
