"""Test the UserSourceSerializer serializer."""

import pytest
from pytest_unordered import unordered

from baserow.api.user_sources.serializers import UserSourceSerializer


@pytest.fixture(autouse=True)
def user_source(data_fixture):
    """A fixture to help test UserSourceSerializer."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)

    return data_fixture.create_user_source_with_first_type(
        application=application,
    )


@pytest.mark.django_db
def test_serializer_has_expected_fields(user_source):
    """Ensure the serializer returns the expected fields."""

    expected_fields = [
        "user_count",
        "user_count_updated_at",
        "application_id",
        "auth_providers",
        "id",
        "integration_id",
        "name",
        "order",
        "type",
        "uid",
    ]

    serializer = UserSourceSerializer(instance=user_source)
    assert list(serializer.data.keys()) == unordered(expected_fields)
