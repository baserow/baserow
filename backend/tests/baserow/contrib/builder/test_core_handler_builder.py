import pytest

from baserow.contrib.builder.models import Builder
from baserow.core.handler import CoreHandler


@pytest.mark.django_db
def test_can_duplicate_builder_application(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    builder_clone = CoreHandler().duplicate_application(user, builder)

    assert builder.id != builder_clone.id
    assert builder.name in builder_clone.name

    assert Builder.objects.count() == 2


@pytest.mark.django_db
def test_duplicated_application_imports_integration(data_fixture):
    """
    Ensure that when duplicating an application, the integration is also
    imported correctly.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user)
    data_fixture.create_local_baserow_integration(user=user, application=builder)

    new_builder = CoreHandler().duplicate_application(user, builder)

    assert new_builder.integrations.all()[0].specific.authorized_user == user
