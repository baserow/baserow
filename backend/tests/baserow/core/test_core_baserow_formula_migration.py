import json
from unittest.mock import patch

from django.db import connection

import pytest

from baserow.core.formula import BaserowFormulaObject


def get_raw_table_value(field_name, table_name, pk) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {field_name} FROM {table_name} WHERE service_ptr_id = %s",
            [pk],
        )
        return cursor.fetchone()[0]


@pytest.mark.django_db
@patch("baserow.core.formula.field.FormulaField.db_type", return_value="text")
def test_create_text_formula_field_value(mock_db_type, data_fixture):
    # Create a service with a raw formula string.
    service = data_fixture.create_core_http_request_service(url="'http://google.com'")
    assert service.url == {
        "mode": "simple",
        "version": "1.0",
        "formula": "'http://google.com'",
    }
    raw_url = get_raw_table_value("url", service._meta.db_table, service.id)
    assert raw_url == '{"m": "simple", "v": "1.0", "f": "\'http://google.com\'"}'

    # Create a service with a formula context.
    service = data_fixture.create_core_http_request_service(
        url=BaserowFormulaObject(
            mode="simple", version="1.0", formula="'http://google.com'"
        )
    )
    assert service.url == {
        "mode": "simple",
        "version": "1.0",
        "formula": "'http://google.com'",
    }
    raw_url = get_raw_table_value("url", service._meta.db_table, service.id)
    assert raw_url == '{"m": "simple", "v": "1.0", "f": "\'http://google.com\'"}'

    # Create a service with a serialized object.
    service = data_fixture.create_core_http_request_service(
        url=json.dumps(
            {
                "m": "simple",
                "v": "1.0",
                "f": "'http://foobar.com'",
            }
        )
    )
    assert service.url == {
        "mode": "simple",
        "version": "1.0",
        "formula": "'http://foobar.com'",
    }
    raw_url = get_raw_table_value("url", service._meta.db_table, service.id)
    assert raw_url == '{"m": "simple", "v": "1.0", "f": "\'http://foobar.com\'"}'


@pytest.mark.django_db
@patch("baserow.core.formula.field.FormulaField.db_type", return_value="text")
def test_update_text_formula_field_value(mock_db_type, data_fixture):
    # Update a service with a raw formula string.
    service = data_fixture.create_core_http_request_service()
    service.url = "'http://google.com'"
    service.save()
    assert service.url == {
        "mode": "simple",
        "version": "1.0",
        "formula": "'http://google.com'",
    }
    raw_url = get_raw_table_value("url", service._meta.db_table, service.id)
    assert raw_url == '{"m": "simple", "v": "1.0", "f": "\'http://google.com\'"}'

    # Update a service with a formula context.
    service = data_fixture.create_core_http_request_service()
    service.url = BaserowFormulaObject(
        mode="simple", version="1.0", formula="'http://google.com'"
    )
    service.save()
    assert service.url == {
        "mode": "simple",
        "version": "1.0",
        "formula": "'http://google.com'",
    }
    raw_url = get_raw_table_value("url", service._meta.db_table, service.id)
    assert raw_url == '{"m": "simple", "v": "1.0", "f": "\'http://google.com\'"}'

    # Update a service with a serialized object.
    service = data_fixture.create_core_http_request_service()
    service.url = json.dumps(
        {
            "m": "simple",
            "v": "1.0",
            "f": "'http://foobar.com'",
        }
    )
    service.save()
    assert service.url == {
        "mode": "simple",
        "version": "1.0",
        "formula": "'http://foobar.com'",
    }
    raw_url = get_raw_table_value("url", service._meta.db_table, service.id)
    assert raw_url == '{"m": "simple", "v": "1.0", "f": "\'http://foobar.com\'"}'
