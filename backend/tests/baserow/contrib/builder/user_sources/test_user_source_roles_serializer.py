"""Test the UserSourceRolesSerializer serializer."""

import pytest

from baserow.api.user_sources.serializers import UserSourceRolesSerializer
from baserow.core.user_sources.registries import DEFAULT_USER_ROLE_PREFIX


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

    serializer = UserSourceRolesSerializer(instance=user_source)
    assert sorted(serializer.data.keys()) == ["id", "roles"]


@pytest.mark.django_db
def test_roles_is_empty_by_default(user_source):
    """Ensure the roles field returns an empty list by default."""

    serializer = UserSourceRolesSerializer(instance=user_source)
    assert serializer.data["roles"] == [f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles",
    [
        ["foo_role"],
        ["bar_role", "foo_role"],
        # Intentionally non-alphabetically sorted
        ["zoo_role", "bar_role", "foo_role"],
    ],
)
def test_roles_returns_expected_data(user_source, data_fixture, roles):
    """Ensure the roles field returns an alphabetized list of roles."""

    # Create a roles field and add some rows
    users_table = data_fixture.create_database_table(name="test_users")
    role_field = data_fixture.create_text_field(
        table=users_table, order=0, name="role", text_default=""
    )
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    model = users_table.get_model()
    for role in roles:
        model.objects.create(**{f"field_{role_field.id}": role})

    serializer = UserSourceRolesSerializer(instance=user_source)
    # We expected the roles to be alphabetized
    assert list(serializer.data["roles"]) == sorted(roles)
