import pytest

from baserow.contrib.database.airtable.utils import (
    extract_share_id_from_url,
    get_airtable_row_primary_value,
)


def test_extract_share_id_from_url():
    with pytest.raises(ValueError):
        extract_share_id_from_url("test")

    assert (
        extract_share_id_from_url("https://airtable.com/shrxxxxxxxxxxxxxx")
        == "shrxxxxxxxxxxxxxx"
    )
    assert (
        extract_share_id_from_url("https://airtable.com/appxxxxxxxxxxxxxx")
        == "appxxxxxxxxxxxxxx"
    )
    assert (
        extract_share_id_from_url("https://airtable.com/shrXxmp0WmqsTkFWTzv")
        == "shrXxmp0WmqsTkFWTzv"
    )

    long_share_id = (
        "shr22aXe5Hj32sPJB/tblU0bav59SSEyOkU/"
        "viwyUDJYyQPYuFj1F?blocks=bipEYER8Qq7fLoPbr"
    )
    assert (
        extract_share_id_from_url(f"https://airtable.com/{long_share_id}")
        == long_share_id
    )


def test_get_airtable_row_primary_value_with_primary_field():
    airtable_table = {
        "name": "Test",
        "primaryColumnId": "fldG9y88Zw7q7u4Z7i4",
    }
    airtable_row = {
        "id": "id1",
        "cellValuesByColumnId": {"fldG9y88Zw7q7u4Z7i4": "name1"},
    }
    assert get_airtable_row_primary_value(airtable_table, airtable_row) == "name1"


def test_get_airtable_row_primary_value_without_primary_field():
    airtable_table = {
        "name": "Test",
        "primaryColumnId": "fldG9y88Zw7q7u4Z7i4",
    }
    airtable_row = {"id": "id1"}
    assert get_airtable_row_primary_value(airtable_table, airtable_row) == "id1"


def test_get_airtable_row_primary_value_without_primary_column_id_in_table():
    airtable_table = {
        "name": "Test",
        "primaryColumnId": "test",
    }
    airtable_row = {"id": "id1"}
    assert get_airtable_row_primary_value(airtable_table, airtable_row) == "id1"
