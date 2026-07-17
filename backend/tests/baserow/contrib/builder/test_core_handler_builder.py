import pytest

from baserow.contrib.builder.models import Builder
from baserow.core.handler import CoreHandler


@pytest.mark.django_db
def test_can_duplicate_builder_application(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    assert builder.mobile_breakpoint == 640
    assert builder.tablet_breakpoint == 1024

    builder_clone = CoreHandler().duplicate_application(user, builder)

    assert builder.id != builder_clone.id
    assert builder.name in builder_clone.name
    assert builder_clone.mobile_breakpoint == 640
    assert builder_clone.tablet_breakpoint == 1024

    assert Builder.objects.count() == 2


@pytest.mark.django_db
def test_can_duplicate_legacy_builder_application(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder.mobile_breakpoint = None
    builder.tablet_breakpoint = None
    builder.save()

    builder_clone = CoreHandler().duplicate_application(user, builder)

    assert builder_clone.mobile_breakpoint is None
    assert builder_clone.tablet_breakpoint is None


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
