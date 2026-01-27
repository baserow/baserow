import pytest
from rest_framework import serializers

from baserow.contrib.database.api.fields.serializers import (
    CollaboratorField,
    CollaboratorRequestSerializer,
)


def test_collaborator_request_serializer_with_list_of_ints():
    result = CollaboratorRequestSerializer().to_internal_value([1, 2, 3])
    assert result == [1, 2, 3]


def test_collaborator_request_serializer_with_list_of_dicts():
    result = CollaboratorRequestSerializer().to_internal_value([{"id": 1}, {"id": 2}])
    assert result == [1, 2]


def test_collaborator_request_serializer_with_ints_and_dicts():
    serializer = CollaboratorRequestSerializer()
    result = serializer.to_internal_value([1, {"id": 2}, "3"])
    assert result == [1, 2, 3]


def test_collaborator_field_int():
    assert CollaboratorField().to_internal_value(100) == 100


def test_collaborator_field_numeric_string():
    assert CollaboratorField().to_internal_value("200") == 200


def test_collaborator_field_dict_with_int_id():
    assert CollaboratorField().to_internal_value({"id": 300}) == 300


def test_collaborator_field_dict_with_string_id():
    assert CollaboratorField().to_internal_value({"id": "404"}) == 404


def test_collaborator_field_dict_without_id():
    with pytest.raises(serializers.ValidationError):
        CollaboratorField().to_internal_value({"foo": "bar"})


def test_collaborator_field_invalid_type():
    with pytest.raises(serializers.ValidationError):
        CollaboratorField().to_internal_value(["foo"])


def test_collaborator_field_non_numeric_string():
    with pytest.raises(serializers.ValidationError):
        CollaboratorField().to_internal_value("foo bar")
