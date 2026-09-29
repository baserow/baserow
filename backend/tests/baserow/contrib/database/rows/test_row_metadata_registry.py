from typing import Any, Dict, List

import msgpack
from rest_framework import serializers
from rest_framework.fields import Field

from baserow.contrib.database.rows.registries import (
    RowMetadataRegistry,
    RowMetadataType,
)


def test_nothing_registered_returns_empty_even_when_rows_provided():
    registry = RowMetadataRegistry()
    result = registry.generate_and_merge_metadata_for_rows(
        None, None, (i for i in range(3))
    )
    assert result == {}


def test_merges_together_row_metadata_by_type_and_row_id():
    registry = RowMetadataRegistry()

    class RowIdMetadata(RowMetadataType):
        type = "row_id"

        def generate_metadata_for_rows(
            self, user, table, row_ids: List[int]
        ) -> Dict[int, Any]:
            return {row_id: row_id for row_id in row_ids}

        def get_example_serializer_field(self) -> Field:
            return serializers.CharField()

    class EvenRowsMetadata(RowMetadataType):
        type = "is_even"

        def generate_metadata_for_rows(
            self, user, table, row_ids: List[int]
        ) -> Dict[int, Any]:
            return {row_id: True for row_id in row_ids if row_id % 2 == 0}

        def get_example_serializer_field(self) -> Field:
            return serializers.BooleanField()

    registry.register(EvenRowsMetadata())
    registry.register(RowIdMetadata())

    result = registry.generate_and_merge_metadata_for_rows(
        None, None, (i for i in range(3))
    )
    assert result == {
        "0": {"is_even": True, "row_id": 0},
        "1": {"row_id": 1},
        "2": {"is_even": True, "row_id": 2},
    }
    result = registry.generate_and_merge_metadata_for_row(None, None, 0)
    assert result == {"is_even": True, "row_id": 0}


def test_row_metadata_keys_are_msgpack_safe():
    registry = RowMetadataRegistry()

    class RowIdMetadata(RowMetadataType):
        type = "row_id"

        def generate_metadata_for_rows(
            self, user, table, row_ids: List[int]
        ) -> Dict[int, Any]:
            return {row_id: row_id for row_id in row_ids}

        def get_example_serializer_field(self) -> Field:
            return serializers.CharField()

    registry.register(RowIdMetadata())

    result = registry.generate_and_merge_metadata_for_rows(
        None, None, (i for i in range(3))
    )

    for key in result:
        assert isinstance(key, str), f"metadata key {key!r} must be a string"

    packed = msgpack.packb(result, use_bin_type=True)
    msgpack.unpackb(packed, strict_map_key=True, raw=False)
