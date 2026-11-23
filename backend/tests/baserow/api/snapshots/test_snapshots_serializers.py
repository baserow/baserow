import pytest

from baserow.api.snapshots.serializers import (
    UpdateApplicationMaxSnapshotsSerializer,
    UpdateWorkspaceSnapshotSettingsSerializer,
)


@pytest.mark.parametrize(
    "serializer_class, field_name, nullable",
    [
        (UpdateApplicationMaxSnapshotsSerializer, "max_snapshots", True),
        (UpdateWorkspaceSnapshotSettingsSerializer, "default_max_snapshots", False),
    ],
)
def test_snapshot_maximum_validation_contract(serializer_class, field_name, nullable):
    """Preserve required input and storage bounds when deriving fields from models."""

    for value in (0, 1, 2147483647):
        serializer = serializer_class(data={field_name: value})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {
            field_name: value,
            "delete_snapshots": False,
        }

    for value, error_code in ((-1, "min_value"), (2147483648, "max_value")):
        serializer = serializer_class(data={field_name: value})
        assert not serializer.is_valid()
        assert serializer.errors[field_name][0].code == error_code

    missing = serializer_class(data={})
    assert not missing.is_valid()
    assert missing.errors[field_name][0].code == "required"

    inherit = serializer_class(data={field_name: None, "delete_snapshots": True})
    assert inherit.is_valid() is nullable
    if nullable:
        assert inherit.validated_data == {
            field_name: None,
            "delete_snapshots": True,
        }
    else:
        assert inherit.errors[field_name][0].code == "null"
