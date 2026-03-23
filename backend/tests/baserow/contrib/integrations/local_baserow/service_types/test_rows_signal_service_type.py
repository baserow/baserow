import pytest

from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedServiceType,
)


@pytest.mark.parametrize(
    "path,id_mapping,expected",
    [
        # When path has fewer than 2 elements, return as is
        ([], {}, []),
        (["0"], {}, ["0"]),
        # When field_dbname doesn't start with "field_", return path as is
        (["0", "id"], {}, ["0", "id"]),
        (["0", "foo"], {}, ["0", "foo"]),
        # {rowIndex}.{fieldName} and field not in mapping
        (["0", "field_1"], {}, ["0", "field_1"]),
        # {rowIndex}.{fieldName} and field in mapping
        (["0", "field_1"], {"database_fields": {1: 2}}, ["0", "field_2"]),
        # {rowIndex}.{fieldName}.{fieldValueIndex}.{value} and field not in mapping
        (["0", "field_1", "0", "value"], {}, ["0", "field_1", "0", "value"]),
        # {rowIndex}.{fieldName}.{fieldValueIndex}.{value} and field in mapping
        (
            ["0", "field_1", "0", "value"],
            {"database_fields": {1: 2}},
            ["0", "field_2", "0", "value"],
        ),
    ],
)
def test_local_baserow_rows_signal_service_type_import_path(path, id_mapping, expected):
    assert (
        LocalBaserowRowsCreatedServiceType().import_path(path, id_mapping) == expected
    )
