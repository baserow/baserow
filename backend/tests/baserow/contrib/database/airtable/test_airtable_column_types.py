import pytest
import responses

from baserow.contrib.database.airtable.airtable_column_types import (
    CheckboxAirtableColumnType,
    CountAirtableColumnType,
    DateAirtableColumnType,
    ForeignKeyAirtableColumnType,
    FormulaAirtableColumnType,
    MultilineTextAirtableColumnType,
    MultipleAttachmentAirtableColumnType,
    MultiSelectAirtableColumnType,
    NumberAirtableColumnType,
    PhoneAirtableColumnType,
    RatingAirtableColumnType,
    RichTextTextAirtableColumnType,
    SelectAirtableColumnType,
    TextAirtableColumnType,
)
from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.exceptions import AirtableSkipCellValue
from baserow.contrib.database.airtable.import_report import (
    SCOPE_CELL,
    SCOPE_FIELD,
    AirtableImportReport,
)
from baserow.contrib.database.airtable.registry import airtable_column_type_registry
from baserow.contrib.database.fields.models import (
    AutonumberField,
    BooleanField,
    CountField,
    CreatedOnField,
    DateField,
    DurationField,
    EmailField,
    FileField,
    LastModifiedField,
    LinkRowField,
    LongTextField,
    MultipleSelectField,
    NumberField,
    PhoneNumberField,
    RatingField,
    SingleSelectField,
    TextField,
    URLField,
)
from baserow.contrib.database.fields.utils.duration import D_H, H_M, H_M_S


@pytest.mark.django_db
@responses.activate
def test_unknown_column_type():
    airtable_field = {"id": "fldTn59fpliSFcwpFA9", "name": "Unknown", "type": "unknown"}
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert baserow_field is None
    assert baserow_field is None

    airtable_field = {
        "id": "fldTn59fpliSFcwpFA9",
        "name": "Unknown",
        "type": "formula",
        "typeOptions": {"displayType": "unknown"},
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert baserow_field is None
    assert baserow_field is None


@pytest.mark.django_db
@responses.activate
def test_airtable_import_text_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldwSc9PqedIhTSqhi5",
        "name": "Single line text",
        "type": "text",
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert baserow_field.text_default == ""
    assert len(import_report.items) == 0
    assert isinstance(baserow_field, TextField)
    assert isinstance(airtable_column_type, TextAirtableColumnType)

    with pytest.raises(AirtableSkipCellValue):
        assert (
            airtable_column_type.to_baserow_export_empty_value(
                {},
                {"name": "Test"},
                {"id": "row1"},
                airtable_field,
                baserow_field,
                {},
                AirtableImportConfig(),
                AirtableImportReport(),
            )
            == ""
        )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_text_column_preserve_default(data_fixture, api_client):
    airtable_field = {
        "id": "fldwSc9PqedIhTSqhi5",
        "name": "Single line text",
        "type": "text",
        "default": "test",
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert baserow_field.text_default == "test"
    assert len(import_report.items) == 0

    assert (
        airtable_column_type.to_baserow_export_empty_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == ""
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_checkbox_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldTn59fpliSFcwpFA9",
        "name": "Checkbox",
        "type": "checkbox",
        "typeOptions": {"color": "green", "icon": "check"},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 0
    assert isinstance(baserow_field, BooleanField)
    assert isinstance(airtable_column_type, CheckboxAirtableColumnType)


@pytest.mark.django_db
@responses.activate
def test_airtable_import_checkbox_column_with_default_value(data_fixture, api_client):
    airtable_field = {
        "id": "fldTn59fpliSFcwpFA9",
        "name": "Checkbox",
        "type": "checkbox",
        "typeOptions": {"color": "green", "icon": "check"},
        "default": True,
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert baserow_field.boolean_default is True
    assert len(import_report.items) == 0

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T14:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "true"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_checkbox_column_invalid_icon(data_fixture, api_client):
    airtable_field = {
        "id": "fldp1IFu0zdgRy70RoX",
        "name": "Checkbox",
        "type": "checkbox",
        "typeOptions": {"color": "green", "icon": "TEST"},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Checkbox"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""


@pytest.mark.django_db
@responses.activate
def test_airtable_import_checkbox_column_invalid_color(data_fixture, api_client):
    airtable_field = {
        "id": "fldp1IFu0zdgRy70RoX",
        "name": "Checkbox",
        "type": "checkbox",
        "typeOptions": {"color": "TEST", "icon": "check"},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Checkbox"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""


@pytest.mark.django_db
@responses.activate
def test_airtable_import_created_on_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldcTpJuoUVpsDNoszO",
        "name": "Created",
        "type": "formula",
        "typeOptions": {
            "isDateTime": False,
            "dateFormat": "Local",
            "displayType": "createdTime",
            "timeZone": "client",
            "formulaTextParsed": "CREATED_TIME()",
            "dependencies": {"referencedColumnIdsForValue": []},
            "resultType": "date",
            "resultIsArray": False,
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert isinstance(baserow_field, CreatedOnField)
    assert isinstance(airtable_column_type, FormulaAirtableColumnType)
    assert baserow_field.date_format == "ISO"
    assert baserow_field.date_include_time is False
    assert baserow_field.date_time_format == "24"
    assert baserow_field.date_force_timezone is None
    assert len(import_report.items) == 0

    airtable_field = {
        "id": "fldcTpJuoUVpsDNoszO",
        "name": "Created",
        "type": "formula",
        "typeOptions": {
            "isDateTime": True,
            "dateFormat": "European",
            "displayType": "createdTime",
            "timeZone": "Europe/Amsterdam",
            "formulaTextParsed": "CREATED_TIME()",
            "dependencies": {"referencedColumnIdsForValue": []},
            "resultType": "date",
            "resultIsArray": False,
            "timeFormat": "12hour",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, CreatedOnField)
    assert isinstance(airtable_column_type, FormulaAirtableColumnType)
    assert baserow_field.date_format == "EU"
    assert baserow_field.date_include_time is True
    assert baserow_field.date_time_format == "12"
    assert baserow_field.date_force_timezone == "Europe/Amsterdam"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T14:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_date_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldyAXIzheHfugGhuFD",
        "name": "ISO DATE",
        "type": "date",
        "typeOptions": {"isDateTime": False, "dateFormat": "US", "timeZone": "client"},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert isinstance(baserow_field, DateField)
    assert isinstance(airtable_column_type, DateAirtableColumnType)
    assert baserow_field.date_format == "US"
    assert baserow_field.date_include_time is False
    assert baserow_field.date_time_format == "24"
    assert len(import_report.items) == 0

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T14:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2022-01-03"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "0999-02-04T14:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "0999-02-04"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )

    import_report = AirtableImportReport()
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "+000000-06-19T21:09:30.000Z",
            {},
            AirtableImportConfig(),
            import_report,
        )
        is None
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == 'Row: "row1", field: "ISO DATE"'
    assert import_report.items[0].scope == SCOPE_CELL
    assert import_report.items[0].table == "Test"


@pytest.mark.django_db
def test_airtable_import_european_date_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldyAXIzheHfugGhuFD",
        "name": "EUROPE",
        "type": "date",
        "typeOptions": {
            "isDateTime": False,
            "dateFormat": "European",
            "timeFormat": "12hour",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, DateField)
    assert isinstance(airtable_column_type, DateAirtableColumnType)
    assert baserow_field.date_format == "EU"
    assert baserow_field.date_include_time is False
    assert baserow_field.date_time_format == "12"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T14:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2022-01-03"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2020-08-27T21:10:24.828Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2020-08-27"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_datetime_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldEB5dp0mNjVZu0VJI",
        "name": "Date",
        "type": "date",
        "typeOptions": {
            "isDateTime": True,
            "dateFormat": "Local",
            "timeFormat": "24hour",
            "timeZone": "client",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, DateField)
    assert isinstance(airtable_column_type, DateAirtableColumnType)
    assert baserow_field.date_format == "ISO"
    assert baserow_field.date_include_time is True
    assert baserow_field.date_time_format == "24"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T14:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2022-01-03T14:51:00+00:00"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2020-08-27T21:10:24.828Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2020-08-27T21:10:24.828000+00:00"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_datetime_with_default_timezone_column(
    data_fixture, api_client
):
    airtable_field = {
        "id": "fldEB5dp0mNjVZu0VJI",
        "name": "Date",
        "type": "date",
        "typeOptions": {
            "isDateTime": True,
            "dateFormat": "Local",
            "timeFormat": "24hour",
            "timeZone": "client",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, DateField)
    assert isinstance(airtable_column_type, DateAirtableColumnType)
    assert baserow_field.date_format == "ISO"
    assert baserow_field.date_include_time is True
    assert baserow_field.date_time_format == "24"
    assert baserow_field.date_force_timezone is None

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T23:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2022-01-03T23:51:00+00:00"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_datetime_with_different_default_timezone_column(
    data_fixture, api_client
):
    airtable_field = {
        "id": "fldEB5dp0mNjVZu0VJI",
        "name": "Date",
        "type": "date",
        "typeOptions": {
            "isDateTime": True,
            "dateFormat": "Local",
            "timeFormat": "24hour",
            "timeZone": "Europe/Amsterdam",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, DateField)
    assert isinstance(airtable_column_type, DateAirtableColumnType)
    assert baserow_field.date_format == "ISO"
    assert baserow_field.date_include_time is True
    assert baserow_field.date_time_format == "24"
    assert baserow_field.date_force_timezone == "Europe/Amsterdam"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T23:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2022-01-03T23:51:00+00:00"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_datetime_edge_case_1(data_fixture, api_client):
    airtable_field = {
        "id": "fldEB5dp0mNjVZu0VJI",
        "name": "Date",
        "type": "date",
        "typeOptions": {
            "isDateTime": True,
            "dateFormat": "Local",
            "timeFormat": "24hour",
            "timeZone": "client",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, DateField)
    assert isinstance(airtable_column_type, DateAirtableColumnType)
    assert baserow_field.date_format == "ISO"
    assert baserow_field.date_include_time is True
    assert baserow_field.date_time_format == "24"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "+020222-03-28T00:00:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_datetime_with_default_value(data_fixture, api_client):
    airtable_field = {
        "id": "fldEB5dp0mNjVZu0VJI",
        "name": "Date",
        "type": "date",
        "default": "test",
        "typeOptions": {
            "isDateTime": True,
            "dateFormat": "Local",
            "timeFormat": "24hour",
            "timeZone": "client",
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Date"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""


@pytest.mark.django_db
@responses.activate
def test_airtable_import_email_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldNdoAZRim39AxR9Eg",
        "name": "Email",
        "type": "text",
        "typeOptions": {"validatorName": "email"},
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, EmailField)
    assert isinstance(airtable_column_type, TextAirtableColumnType)

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "NOT_EMAIL",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == ""
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "test@test.nl",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "test@test.nl"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_multiple_attachment_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldwdy4qWUvC5PmW5yd",
        "name": "Attachment",
        "type": "multipleAttachment",
        "typeOptions": {"unreversed": True},
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, FileField)
    assert isinstance(airtable_column_type, MultipleAttachmentAirtableColumnType)

    files_to_download = {}
    assert airtable_column_type.to_baserow_export_serialized_value(
        {},
        {"name": "Test"},
        {
            "id": "row1",
            "airtable_record_id": "row1",
        },
        airtable_field,
        baserow_field,
        [
            {
                "id": "attecVDNr3x7oE8Bj",
                "url": "https://dl.airtable.com/.attachments/70e50b90fb83997d25e64937979b6b5b/f3f62d23/file-sample.txt",
                "filename": "file-sample.txt",
                "uploadsDmzS3Key": "YbuBlXi8SP2cMzT8F3Yo_file-sample.txt",
                "servingS3Key": ".attachments/70e50b90fb83997d25e64937979b6b5b/f3f62d23/file-sample.txt",
                "type": "application/pdf",
                "size": 142786,
                "smallThumbUrl": "https://dl.airtable.com/.attachmentThumbnails/1af3d5cef7ef07f39ec87eb18cbcf343/dbc2b9ab",
                "smallThumbWidth": 25,
                "smallThumbHeight": 36,
                "largeThumbUrl": "https://dl.airtable.com/.attachmentThumbnails/ff0f3e6624ec60eb0c22b82fec23ee9a/9bf8fc2b",
                "largeThumbWidth": 362,
                "largeThumbHeight": 512,
            },
            {
                "id": "attFE9KxOeLxbFn58",
                "url": "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc",
                "filename": "file-sample_500kB.doc",
                "type": "application/msword",
                "size": 503296,
            },
        ],
        files_to_download,
        AirtableImportConfig(),
        AirtableImportReport(),
    ) == [
        {
            "name": "70e50b90fb83997d25e64937979b6b5b_f3f62d23_file-sample.txt",
            "visible_name": "file-sample.txt",
            "original_name": "file-sample.txt",
        },
        {
            "name": "e93dc201ce27080d9ad9df5775527d09_93e85b28_file-sample_500kB.doc",
            "visible_name": "file-sample_500kB.doc",
            "original_name": "file-sample_500kB.doc",
        },
    ]
    assert len(files_to_download) == 2
    file1 = files_to_download[
        "70e50b90fb83997d25e64937979b6b5b_f3f62d23_file-sample.txt"
    ]
    assert file1.url == (
        "https://dl.airtable.com/.attachments/70e50b90fb83997d25e64937979b6b5b/f3f62d23/file-sample.txt"
    )
    assert file1.row_id == "row1"
    assert file1.column_id == "fldwdy4qWUvC5PmW5yd"
    assert file1.attachment_id == "attecVDNr3x7oE8Bj"
    assert file1.type == "fetch"

    file2 = files_to_download[
        "e93dc201ce27080d9ad9df5775527d09_93e85b28_file-sample_500kB.doc"
    ]
    assert (
        file2.url
        == "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_multiple_attachment_column_skip_files(
    data_fixture, api_client
):
    airtable_field = {
        "id": "fldwdy4qWUvC5PmW5yd",
        "name": "Attachment",
        "type": "multipleAttachment",
        "typeOptions": {"unreversed": True},
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(skip_files=True),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, FileField)
    assert isinstance(airtable_column_type, MultipleAttachmentAirtableColumnType)

    files_to_download = {}
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            [
                {
                    "id": "attecVDNr3x7oE8Bj",
                    "url": "https://dl.airtable.com/.attachments/70e50b90fb83997d25e64937979b6b5b/f3f62d23/file-sample.txt",
                    "filename": "file-sample.txt",
                    "uploadsDmzS3Key": "YbuBlXi8SP2cMzT8F3Yo_file-sample.txt",
                    "servingS3Key": ".attachments/70e50b90fb83997d25e64937979b6b5b/f3f62d23/file-sample.txt",
                    "type": "application/pdf",
                    "size": 142786,
                    "smallThumbUrl": "https://dl.airtable.com/.attachmentThumbnails/1af3d5cef7ef07f39ec87eb18cbcf343/dbc2b9ab",
                    "smallThumbWidth": 25,
                    "smallThumbHeight": 36,
                    "largeThumbUrl": "https://dl.airtable.com/.attachmentThumbnails/ff0f3e6624ec60eb0c22b82fec23ee9a/9bf8fc2b",
                    "largeThumbWidth": 362,
                    "largeThumbHeight": 512,
                },
                {
                    "id": "attFE9KxOeLxbFn58",
                    "url": "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc",
                    "filename": "file-sample_500kB.doc",
                    "type": "application/msword",
                    "size": 503296,
                },
            ],
            files_to_download,
            AirtableImportConfig(skip_files=True),
            AirtableImportReport(),
        )
        == []
    )
    assert files_to_download == {}


@pytest.mark.django_db
@responses.activate
def test_airtable_import_last_modified_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldws6n8xdrEJrMxJFJ",
        "name": "Last",
        "type": "formula",
        "typeOptions": {
            "isDateTime": False,
            "dateFormat": "Local",
            "displayType": "lastModifiedTime",
            "timeZone": "client",
            "formulaTextParsed": "LAST_MODIFIED_TIME()",
            "dependencies": {
                "referencedColumnIdsForValue": [],
                "dependsOnAllColumnModifications": True,
            },
            "resultType": "date",
            "resultIsArray": False,
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert isinstance(baserow_field, LastModifiedField)
    assert isinstance(airtable_column_type, FormulaAirtableColumnType)
    assert baserow_field.date_format == "ISO"
    assert baserow_field.date_include_time is False
    assert baserow_field.date_time_format == "24"
    assert baserow_field.date_force_timezone is None
    assert len(import_report.items) == 0

    airtable_field = {
        "id": "fldws6n8xdrEJrMxJFJ",
        "name": "Last",
        "type": "formula",
        "typeOptions": {
            "isDateTime": True,
            "dateFormat": "US",
            "displayType": "lastModifiedTime",
            "timeZone": "Europe/Amsterdam",
            "formulaTextParsed": "LAST_MODIFIED_TIME()",
            "dependencies": {
                "referencedColumnIdsForValue": [],
                "dependsOnAllColumnModifications": True,
            },
            "resultType": "date",
            "resultIsArray": False,
            "timeFormat": "12hour",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, LastModifiedField)
    assert isinstance(airtable_column_type, FormulaAirtableColumnType)
    assert baserow_field.date_format == "US"
    assert baserow_field.date_include_time is True
    assert baserow_field.date_time_format == "12"
    assert baserow_field.date_force_timezone == "Europe/Amsterdam"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "2022-01-03T14:51:00.000Z",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "2022-01-03T14:51:00+00:00"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_last_modified_column_depending_fields(
    data_fixture, api_client
):
    airtable_field = {
        "id": "fldws6n8xdrEJrMxJFJ",
        "name": "Last",
        "type": "formula",
        "typeOptions": {
            "isDateTime": False,
            "dateFormat": "Local",
            "displayType": "lastModifiedTime",
            "timeZone": "client",
            "formulaTextParsed": "LAST_MODIFIED_TIME()",
            "dependencies": {
                "referencedColumnIdsForValue": [],
                "referencedColumnIdsForModification": ["fld123445678"],
                "dependsOnAllColumnModifications": False,
            },
            "resultType": "date",
            "resultIsArray": False,
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert isinstance(baserow_field, LastModifiedField)
    assert isinstance(airtable_column_type, FormulaAirtableColumnType)
    assert baserow_field.date_format == "ISO"
    assert baserow_field.date_include_time is False
    assert baserow_field.date_time_format == "24"
    assert baserow_field.date_force_timezone is None
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Last"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""


@pytest.mark.django_db
@responses.activate
def test_airtable_import_foreign_key_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldQcEaGEe7xuhUEuPL",
        "name": "Link to Users",
        "type": "foreignKey",
        "typeOptions": {
            "foreignTableId": "tblRpq315qnnIcg5IjI",
            "relationship": "many",
            "unreversed": True,
            "symmetricColumnId": "fldFh5wIL430N62LN6t",
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {"id": "tblxxx"}, airtable_field, AirtableImportConfig(), import_report
    )
    assert len(import_report.items) == 0
    assert isinstance(baserow_field, LinkRowField)
    assert isinstance(airtable_column_type, ForeignKeyAirtableColumnType)
    assert baserow_field.link_row_table_id == "tblRpq315qnnIcg5IjI"
    assert baserow_field.link_row_related_field_id == "fldFh5wIL430N62LN6t"

    assert airtable_column_type.to_baserow_export_serialized_value(
        {
            "tblRpq315qnnIcg5IjI": {
                "recWkle1IOXcLmhILmO": 1,
                "rec5pdtuKyE71lfK1Ah": 2,
            }
        },
        {"name": "Test"},
        {"id": "row1"},
        airtable_field,
        baserow_field,
        [
            {
                "foreignRowId": "recWkle1IOXcLmhILmO",
                "foreignRowDisplayName": "Bram 1",
            },
            {
                "foreignRowId": "rec5pdtuKyE71lfK1Ah",
                "foreignRowDisplayName": "Bram 2",
            },
        ],
        {},
        AirtableImportConfig(),
        AirtableImportReport(),
    ) == [1, 2]

    # missing value
    import_report = AirtableImportReport()
    assert airtable_column_type.to_baserow_export_serialized_value(
        {
            "tblRpq315qnnIcg5IjI": {
                "recWkle1IOXcLmhILmO": 1,
            }
        },
        {"name": "Test"},
        {"id": "row1"},
        airtable_field,
        baserow_field,
        [
            {
                "foreignRowId": "recWkle1IOXcLmhILmO",
                "foreignRowDisplayName": "Bram 1",
            },
            {
                "foreignRowId": "rec5pdtuKyE71lfK1Ah",
                "foreignRowDisplayName": "Bram 2",
            },
        ],
        {},
        AirtableImportConfig(),
        import_report,
    ) == [1]
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == 'Row: "row1", field: "Link to Users"'
    assert import_report.items[0].scope == SCOPE_CELL
    assert import_report.items[0].table == "Test"

    # link to same table row
    airtable_field = {
        "id": "fldQcEaGEe7xuhUEuPL",
        "name": "Link to Users",
        "type": "foreignKey",
        "typeOptions": {
            "foreignTableId": "tblRpq315qnnIcg5IjI",
            "relationship": "many",
            "unreversed": True,
            "symmetricColumnId": "fldQcEaGEe7xuhUEuPL",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {"id": "tblRpq315qnnIcg5IjI"},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, LinkRowField)
    assert isinstance(airtable_column_type, ForeignKeyAirtableColumnType)
    assert baserow_field.link_row_table_id == "tblRpq315qnnIcg5IjI"
    assert baserow_field.link_row_related_field_id == "fldQcEaGEe7xuhUEuPL"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_foreign_key_column_failed_import(data_fixture, api_client):
    airtable_field = {
        "id": "fldQcEaGEe7xuhUEuPL",
        "name": "Link to Users",
        "type": "foreignKey",
        "typeOptions": {
            "foreignTableId": "tblRpq315qnnIcg5IjI",
            "relationship": "one",
            "unreversed": True,
            "symmetricColumnId": "fldFh5wIL430N62LN6t",
            "viewIdForRecordSelection": "vw1234",
            "filtersForRecordSelection": [None],
            "aiMatchingOptions": {"isAutoFillEnabled": False},
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {"id": "tblxxx"}, airtable_field, AirtableImportConfig(), import_report
    )
    assert len(import_report.items) == 4
    assert import_report.items[0].object_name == "Link to Users"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""
    assert import_report.items[1].object_name == "Link to Users"
    assert import_report.items[1].scope == SCOPE_FIELD
    assert import_report.items[1].table == ""
    assert import_report.items[2].object_name == "Link to Users"
    assert import_report.items[2].scope == SCOPE_FIELD
    assert import_report.items[2].table == ""
    assert import_report.items[3].object_name == "Link to Users"
    assert import_report.items[3].scope == SCOPE_FIELD
    assert import_report.items[3].table == ""
    assert isinstance(baserow_field, LinkRowField)
    assert isinstance(airtable_column_type, ForeignKeyAirtableColumnType)
    assert baserow_field.link_row_table_id == "tblRpq315qnnIcg5IjI"
    assert baserow_field.link_row_related_field_id == "fldFh5wIL430N62LN6t"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_multiline_text_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldG9y88Zw7q7u4Z7i4",
        "name": "Name",
        "type": "multilineText",
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, LongTextField)
    assert isinstance(airtable_column_type, MultilineTextAirtableColumnType)

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "test",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "test"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_rich_text_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldG9y88Zw7q7u4Z7i4",
        "name": "Name",
        "type": "richText",
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, LongTextField)
    assert isinstance(airtable_column_type, RichTextTextAirtableColumnType)
    assert baserow_field.long_text_enable_rich_text is True

    content = {
        "otDocumentId": "otdHtbNg2tJKWj62WMn",
        "revision": 4,
        "documentValue": [
            {"insert": "Vestibulum", "attributes": {"bold": True}},
            {"insert": " ante ipsum primis in faucibus orci luctus et ultrices "},
            {"insert": "posuere", "attributes": {"italic": True}},
            {"insert": " cubilia curae; Class aptent taciti sociosqu ad litora."},
        ],
    }
    assert airtable_column_type.to_baserow_export_serialized_value(
        {},
        {"name": "Test"},
        {"id": "row1"},
        airtable_field,
        baserow_field,
        content,
        {},
        AirtableImportConfig(),
        AirtableImportReport(),
    ) == (
        "**Vestibulum** ante ipsum primis in faucibus orci luctus et ultrices "
        "_posuere_ cubilia curae; Class aptent taciti sociosqu ad litora."
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_rich_text_column_with_mention(data_fixture, api_client):
    airtable_field = {
        "id": "fldG9y88Zw7q7u4Z7i4",
        "name": "Name",
        "type": "richText",
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, LongTextField)
    assert isinstance(airtable_column_type, RichTextTextAirtableColumnType)
    assert baserow_field.long_text_enable_rich_text is True

    content = {
        "otDocumentId": "otdHtbNg2tJKWj62WMn",
        "revision": 4,
        "documentValue": [
            {"insert": "Vestibulum", "attributes": {"bold": True}},
            {"insert": " ante ipsum primis in faucibus orci luctus et ultrices "},
            {
                "insert": {
                    "mention": {
                        "mentionId": "menvWlZAaLd2v052j",
                        "userId": "usrr5CVJ5Lz8ErVZS",
                    }
                }
            },
            {"insert": " cubilia curae; Class aptent taciti sociosqu ad litora."},
        ],
    }
    assert airtable_column_type.to_baserow_export_serialized_value(
        {},
        {"name": "Test"},
        {"id": "row1"},
        airtable_field,
        baserow_field,
        content,
        {},
        AirtableImportConfig(),
        AirtableImportReport(),
    ) == (
        "**Vestibulum** ante ipsum primis in faucibus orci luctus et ultrices "
        "@usrr5CVJ5Lz8ErVZS cubilia curae; Class aptent taciti sociosqu ad litora."
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_multi_select_column(
    data_fixture, api_client, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    airtable_field = {
        "id": "fldURNo0cvi6YWYcYj1",
        "name": "Multiple select",
        "type": "multiSelect",
        "typeOptions": {
            "choiceOrder": ["sel5ekvuoNVvl03olMO", "selEOJmenvqEd6pndFQ"],
            "choices": {
                "selEOJmenvqEd6pndFQ": {
                    "id": "selEOJmenvqEd6pndFQ",
                    "color": "blue",
                    "name": "Option 1",
                },
                "sel5ekvuoNVvl03olMO": {
                    "id": "sel5ekvuoNVvl03olMO",
                    "color": "cyan",
                    "name": "Option 2",
                },
            },
            "disableColors": False,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, MultipleSelectField)
    assert isinstance(airtable_column_type, MultiSelectAirtableColumnType)

    baserow_field.table_id = table.id
    baserow_field.order = 999
    baserow_field.save()

    with django_assert_num_queries(0):
        select_options = list(baserow_field.select_options.all())

    assert len(select_options) == 2
    assert select_options[0].id == "fldURNo0cvi6YWYcYj1_selEOJmenvqEd6pndFQ"
    assert select_options[0].value == "Option 1"
    assert select_options[0].color == "light-blue"
    assert select_options[0].order == 1
    assert select_options[1].id == "fldURNo0cvi6YWYcYj1_sel5ekvuoNVvl03olMO"
    assert select_options[1].value == "Option 2"
    assert select_options[1].color == "light-cyan"
    assert select_options[1].order == 0


@pytest.mark.django_db
@responses.activate
def test_airtable_import_multi_select_column_with_default_value(
    data_fixture, api_client, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    airtable_field = {
        "id": "fldURNo0cvi6YWYcYj1",
        "name": "Multiple select",
        "type": "multiSelect",
        "default": ["selEOJmenvqEd6pndFQ", "sel5ekvuoNVvl03olMO"],
        "typeOptions": {
            "choiceOrder": ["sel5ekvuoNVvl03olMO", "selEOJmenvqEd6pndFQ"],
            "choices": {
                "selEOJmenvqEd6pndFQ": {
                    "id": "selEOJmenvqEd6pndFQ",
                    "color": "blue",
                    "name": "Option 1",
                },
                "sel5ekvuoNVvl03olMO": {
                    "id": "sel5ekvuoNVvl03olMO",
                    "color": "cyan",
                    "name": "Option 2",
                },
            },
            "disableColors": False,
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )

    assert isinstance(baserow_field, MultipleSelectField)
    assert isinstance(airtable_column_type, MultiSelectAirtableColumnType)

    assert baserow_field.multiple_select_default == [
        "fldURNo0cvi6YWYcYj1_selEOJmenvqEd6pndFQ",
        "fldURNo0cvi6YWYcYj1_sel5ekvuoNVvl03olMO",
    ]

    select_options = list(baserow_field._prefetched_objects_cache["select_options"])
    assert len(select_options) == 2
    assert select_options[0].id == "fldURNo0cvi6YWYcYj1_selEOJmenvqEd6pndFQ"
    assert select_options[0].value == "Option 1"
    assert select_options[0].color == "light-blue"
    assert select_options[1].id == "fldURNo0cvi6YWYcYj1_sel5ekvuoNVvl03olMO"
    assert select_options[1].value == "Option 2"
    assert select_options[1].color == "light-cyan"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_number_integer_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Number",
        "type": "number",
        "typeOptions": {
            "format": "integer",
            "negative": False,
            "validatorName": "positive",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, NumberField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.number_decimal_places == 0
    assert baserow_field.number_negative is False
    assert baserow_field.number_separator == ""
    assert baserow_field.number_prefix == ""
    assert baserow_field.number_suffix == ""

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "10",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "10"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            10,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "10"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "-10",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            -10,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_number_invalid_number(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Number",
        "type": "number",
        "typeOptions": {
            "format": "integer",
            "negative": False,
            "validatorName": "positive",
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )

    import_report = AirtableImportReport()
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "INVALID_NUMBER",
            {},
            AirtableImportConfig(),
            import_report,
        )
        is None
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == 'Row: "row1", field: "Number"'
    assert import_report.items[0].scope == SCOPE_CELL
    assert import_report.items[0].table == "Test"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_number_decimal_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Decimal",
        "type": "number",
        "typeOptions": {
            "format": "decimal",
            "precision": 0,
            "negative": False,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, NumberField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.number_decimal_places == 0
    assert baserow_field.number_negative is False

    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Decimal",
        "type": "number",
        "typeOptions": {
            "format": "decimal",
            "precision": 2,
            "negative": True,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, NumberField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.number_decimal_places == 2
    assert baserow_field.number_negative is True
    assert baserow_field.number_separator == ""
    assert baserow_field.number_prefix == ""
    assert baserow_field.number_suffix == ""

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "10.22",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "10.22"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            10,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "10"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "-10.555",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "-10.555"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            -10,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "-10"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )

    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Decimal",
        "type": "number",
        "typeOptions": {
            "format": "decimal",
            "precision": 11,
            "negative": True,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, NumberField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.number_decimal_places == 10
    assert baserow_field.number_negative is True
    assert baserow_field.number_separator == ""
    assert baserow_field.number_prefix == ""
    assert baserow_field.number_suffix == ""


@pytest.mark.django_db
@responses.activate
def test_airtable_import_currency_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Currency",
        "type": "number",
        "typeOptions": {
            "format": "currency",
            "precision": 3,
            "symbol": "$",
            "separatorFormat": "commaPeriod",
            "negative": False,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, NumberField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.number_decimal_places == 3
    assert baserow_field.number_negative is False
    assert baserow_field.number_separator == "COMMA_PERIOD"
    assert baserow_field.number_prefix == "$"
    assert baserow_field.number_suffix == ""

    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Currency",
        "type": "number",
        "typeOptions": {
            "format": "currency",
            "precision": 2,
            "symbol": "€",
            "separatorFormat": "spacePeriod",
            "negative": True,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, NumberField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.number_decimal_places == 2
    assert baserow_field.number_negative is True
    assert baserow_field.number_separator == "SPACE_PERIOD"
    assert baserow_field.number_prefix == "€"
    assert baserow_field.number_suffix == ""


@pytest.mark.django_db
@responses.activate
def test_airtable_import_currency_column_non_existing_separator_format(
    data_fixture, api_client
):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Currency",
        "type": "number",
        "typeOptions": {
            "format": "currency",
            "precision": 3,
            "symbol": "$",
            "separatorFormat": "TEST",
            "negative": False,
        },
    }
    import_report = AirtableImportReport()
    airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Currency"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""


@pytest.mark.django_db
@responses.activate
def test_airtable_import_percentage_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Currency",
        "type": "number",
        "typeOptions": {
            "format": "percentage",
            "precision": 1,
            "negative": False,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, NumberField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.number_decimal_places == 1
    assert baserow_field.number_negative is False
    assert baserow_field.number_separator == ""
    assert baserow_field.number_prefix == ""
    assert baserow_field.number_suffix == "%"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            0.5,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "50.0"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            0.5,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "50.0"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "0.05",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "5.00"
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_number_column_default_value(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Number",
        "type": "number",
        "default": 1,
        "typeOptions": {
            "format": "integer",
            "negative": False,
            "validatorName": "positive",
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert isinstance(baserow_field, NumberField)
    assert baserow_field.number_default == 1
    assert len(import_report.items) == 0

    # Test percentage default value
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Number",
        "type": "number",
        "default": 0.5,
        "typeOptions": {
            "format": "percentage",
            "negative": False,
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert isinstance(baserow_field, NumberField)
    assert baserow_field.number_default == 50.0
    assert len(import_report.items) == 0

    # Test decimal default value
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Number",
        "type": "number",
        "default": 1.23,
        "typeOptions": {
            "format": "decimal",
            "precision": 2,
            "negative": True,
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert isinstance(baserow_field, NumberField)
    assert baserow_field.number_default == 1.23
    assert len(import_report.items) == 0


@pytest.mark.django_db
@responses.activate
def test_airtable_import_days_duration_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Duration",
        "type": "number",
        "typeOptions": {
            "format": "durationInDays",
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {}, airtable_field, AirtableImportConfig(), import_report
    )
    assert len(import_report.items) == 0
    assert isinstance(baserow_field, DurationField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.duration_format == D_H

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            1,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == 86400  # 1 * 60 * 60 * 24
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_duration_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Duration",
        "type": "number",
        "typeOptions": {"format": "duration", "durationFormat": "h:mm"},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {}, airtable_field, AirtableImportConfig(), import_report
    )
    assert len(import_report.items) == 0
    assert isinstance(baserow_field, DurationField)
    assert isinstance(airtable_column_type, NumberAirtableColumnType)
    assert baserow_field.duration_format == H_M

    airtable_field["typeOptions"]["durationFormat"] = "h:mm:ss"
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {}, airtable_field, AirtableImportConfig(), import_report
    )
    assert baserow_field.duration_format == H_M_S

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            None,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            1,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == 1
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_duration_column_max_value(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Duration",
        "type": "number",
        "typeOptions": {"format": "duration", "durationFormat": "h:mm"},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {}, airtable_field, AirtableImportConfig(), import_report
    )

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            86399999913601,
            {},
            AirtableImportConfig(),
            import_report,
        )
        is None
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == 'Row: "row1", field: "Duration"'
    assert import_report.items[0].scope == SCOPE_CELL
    assert import_report.items[0].table == "Test"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_duration_column_max_negative_value(data_fixture, api_client):
    airtable_field = {
        "id": "fldZBmr4L45mhjILhlA",
        "name": "Duration",
        "type": "number",
        "typeOptions": {"format": "duration", "durationFormat": "h:mm"},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {}, airtable_field, AirtableImportConfig(), import_report
    )

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            -86399999913601,
            {},
            AirtableImportConfig(),
            import_report,
        )
        is None
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == 'Row: "row1", field: "Duration"'
    assert import_report.items[0].scope == SCOPE_CELL
    assert import_report.items[0].table == "Test"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_phone_column(data_fixture, api_client):
    airtable_field = {"id": "fldkrPuYJTqq7vSJ7Oh", "name": "Phone", "type": "phone"}
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, PhoneNumberField)
    assert isinstance(airtable_column_type, PhoneAirtableColumnType)

    import_report = AirtableImportReport()
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "NOT_PHONE",
            {},
            AirtableImportConfig(),
            import_report,
        )
        == ""
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == 'Row: "row1", field: "Phone"'
    assert import_report.items[0].scope == SCOPE_CELL
    assert import_report.items[0].table == "Test"
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "1234",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "1234"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_rating_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldp1IFu0zdgRy70RoX",
        "name": "Rating",
        "type": "rating",
        "typeOptions": {"color": "blue", "icon": "heart", "max": 5},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 0
    assert isinstance(baserow_field, RatingField)
    assert isinstance(airtable_column_type, RatingAirtableColumnType)
    assert baserow_field.max_value == 5
    assert baserow_field.color == "dark-blue"
    assert baserow_field.style == "heart"
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            5,
            {},
            AirtableImportConfig(),
            import_report,
        )
        == 5
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_rating_column_invalid_icon(data_fixture, api_client):
    airtable_field = {
        "id": "fldp1IFu0zdgRy70RoX",
        "name": "Rating",
        "type": "rating",
        "typeOptions": {"color": "blue", "icon": "TEST", "max": 5},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Rating"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""
    assert baserow_field.max_value == 5
    assert baserow_field.color == "dark-blue"
    assert baserow_field.style == "star"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_rating_column_invalid_color(data_fixture, api_client):
    airtable_field = {
        "id": "fldp1IFu0zdgRy70RoX",
        "name": "Rating",
        "type": "rating",
        "typeOptions": {"color": "TEST", "icon": "heart", "max": 5},
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == "Rating"
    assert import_report.items[0].scope == SCOPE_FIELD
    assert import_report.items[0].table == ""
    assert baserow_field.max_value == 5
    assert baserow_field.color == "dark-blue"
    assert baserow_field.style == "heart"


@pytest.mark.django_db
@responses.activate
def test_airtable_import_select_column(
    data_fixture, api_client, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    airtable_field = {
        "id": "fldRd2Vkzgsf6X4z6B4",
        "name": "Single select",
        "type": "select",
        "typeOptions": {
            "choiceOrder": ["selbh6rEWaaiyQvWyfg", "selvZgpWhbkeRVphROT"],
            "choices": {
                "selbh6rEWaaiyQvWyfg": {
                    "id": "selbh6rEWaaiyQvWyfg",
                    "color": "blue",
                    "name": "Option A",
                },
                "selvZgpWhbkeRVphROT": {
                    "id": "selvZgpWhbkeRVphROT",
                    "color": "cyan",
                    "name": "Option B",
                },
            },
            "disableColors": False,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, SingleSelectField)
    assert isinstance(airtable_column_type, SelectAirtableColumnType)

    baserow_field.table_id = table.id
    baserow_field.order = 999
    baserow_field.save()

    with django_assert_num_queries(0):
        select_options = list(baserow_field.select_options.all())

    assert len(select_options) == 2
    assert select_options[0].id == "fldRd2Vkzgsf6X4z6B4_selbh6rEWaaiyQvWyfg"
    assert select_options[0].value == "Option A"
    assert select_options[0].color == "light-blue"
    assert select_options[0].order == 0
    assert select_options[1].id == "fldRd2Vkzgsf6X4z6B4_selvZgpWhbkeRVphROT"
    assert select_options[1].value == "Option B"
    assert select_options[1].color == "light-cyan"
    assert select_options[1].order == 1


@pytest.mark.django_db
@responses.activate
def test_airtable_import_select_column_with_default_value(
    data_fixture, api_client, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    airtable_field = {
        "id": "fldRd2Vkzgsf6X4z6B4",
        "name": "Single select",
        "type": "select",
        "default": "selbh6rEWaaiyQvWyfg",
        "typeOptions": {
            "choiceOrder": ["selbh6rEWaaiyQvWyfg", "selvZgpWhbkeRVphROT"],
            "choices": {
                "selbh6rEWaaiyQvWyfg": {
                    "id": "selbh6rEWaaiyQvWyfg",
                    "color": "blue",
                    "name": "Option A",
                },
                "selvZgpWhbkeRVphROT": {
                    "id": "selvZgpWhbkeRVphROT",
                    "color": "cyan",
                    "name": "Option B",
                },
            },
            "disableColors": False,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, SingleSelectField)
    assert isinstance(airtable_column_type, SelectAirtableColumnType)

    assert (
        baserow_field.single_select_default == "fldRd2Vkzgsf6X4z6B4_selbh6rEWaaiyQvWyfg"
    )

    select_options = list(baserow_field._prefetched_objects_cache["select_options"])
    assert len(select_options) == 2
    assert select_options[0].id == "fldRd2Vkzgsf6X4z6B4_selbh6rEWaaiyQvWyfg"
    assert select_options[0].value == "Option A"
    assert select_options[0].color == "light-blue"
    assert select_options[0].order == 0
    assert select_options[1].id == "fldRd2Vkzgsf6X4z6B4_selvZgpWhbkeRVphROT"
    assert select_options[1].value == "Option B"
    assert select_options[1].color == "light-cyan"
    assert select_options[1].order == 1


@pytest.mark.django_db
@responses.activate
def test_airtable_import_url_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldG9y88Zw7q7u4Z7i4",
        "name": "Name",
        "type": "text",
        "typeOptions": {"validatorName": "url"},
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, URLField)
    assert isinstance(airtable_column_type, TextAirtableColumnType)

    import_report = AirtableImportReport()
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "NOT_URL",
            {},
            AirtableImportConfig(),
            import_report,
        )
        == ""
    )
    assert len(import_report.items) == 1
    assert import_report.items[0].object_name == 'Row: "row1", field: "Name"'
    assert import_report.items[0].scope == SCOPE_CELL
    assert import_report.items[0].table == "Test"

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "https://test.nl",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "https://test.nl"
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_count_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldG9y88Zw7q7u4Z7i4",
        "name": "Count",
        "type": "count",
        "typeOptions": {
            "relationColumnId": "fldABC88Zw7q7u4Z7i4",
            "dependencies": [],
            "resultType": "number",
            "resultIsArray": False,
        },
    }
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert isinstance(baserow_field, CountField)
    assert isinstance(airtable_column_type, CountAirtableColumnType)

    assert baserow_field.through_field_id == "fldABC88Zw7q7u4Z7i4"
    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            "1",
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        is None
    )


@pytest.mark.django_db
@responses.activate
def test_airtable_import_autonumber_column(data_fixture, api_client):
    airtable_field = {
        "id": "fldG9y88Zw7q7u4Z7i4",
        "name": "ID",
        "type": "autoNumber",
        "typeOptions": {
            "maxUsedAutoNumber": 8,
        },
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        AirtableImportReport(),
    )
    assert len(import_report.items) == 0
    assert isinstance(baserow_field, AutonumberField)

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            1,
            {},
            AirtableImportConfig(),
            import_report,
        )
        == 1
    )
    assert len(import_report.items) == 0


@pytest.mark.django_db
@responses.activate
def test_airtable_import_checkbox_column_empty_value_with_default(
    data_fixture, api_client
):
    airtable_field = {
        "id": "fldp1IFu0zdgRy70RoX",
        "name": "Checkbox",
        "type": "checkbox",
        "typeOptions": {"color": "green", "icon": "check"},
        "default": True,
    }
    import_report = AirtableImportReport()
    (
        baserow_field,
        airtable_column_type,
    ) = airtable_column_type_registry.from_airtable_column_to_serialized(
        {},
        airtable_field,
        AirtableImportConfig(),
        import_report,
    )
    assert baserow_field.boolean_default is True
    assert len(import_report.items) == 0

    assert (
        airtable_column_type.to_baserow_export_empty_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "false"
    )

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            True,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "true"
    )

    assert (
        airtable_column_type.to_baserow_export_serialized_value(
            {},
            {"name": "Test"},
            {"id": "row1"},
            airtable_field,
            baserow_field,
            False,
            {},
            AirtableImportConfig(),
            AirtableImportReport(),
        )
        == "false"
    )
