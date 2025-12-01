from decimal import Decimal
from unittest.mock import patch

import pytest

from baserow.core.app_auth_providers.exceptions import IncompatibleUserSourceType
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.exceptions import PermissionException
from baserow.core.user_sources.exceptions import (
    UserSourceDoesNotExist,
    UserSourceNotInSameApplication,
)
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.core.user_sources.service import UserSourceService


def pytest_generate_tests(metafunc):
    if "user_source_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "user_source_type",
            [pytest.param(e, id=e.type) for e in user_source_type_registry.get_all()],
        )


@pytest.mark.django_db
@patch("baserow.core.user_sources.service.user_source_created")
def test_create_user_source(user_source_created_mock, data_fixture, user_source_type):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application, order="1.0000"
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application, order="2.0000"
    )

    service = UserSourceService()
    user_source = service.create_user_source(
        user, user_source_type, application=application
    )

    last_user_source = UserSource.objects.last()

    # Check it's the last user_source
    assert last_user_source.id == user_source.id

    user_source_created_mock.send.assert_called_once_with(
        service, user_source=user_source, user=user, before_id=None
    )


@pytest.mark.django_db
def test_create_user_source_w_auth_source(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    user_source_type = list(user_source_type_registry.get_all())[0]
    app_auth_provider_type = list(app_auth_provider_type_registry.get_all())[0]

    user_source2 = UserSourceService().create_user_source(
        user,
        user_source_type,
        application=application,
        auth_providers=[{"type": app_auth_provider_type.type}],
    )

    assert AppAuthProvider.objects.count() == 1


@pytest.mark.django_db
def test_create_user_source_w_incompatible_auth_source(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    user_source_type = list(user_source_type_registry.get_all())[0]
    app_auth_provider_type = list(app_auth_provider_type_registry.get_all())[0]

    original_compatible = app_auth_provider_type.compatible_user_source_types
    app_auth_provider_type.compatible_user_source_types = []

    with pytest.raises(IncompatibleUserSourceType):
        UserSourceService().create_user_source(
            user,
            user_source_type,
            application=application,
            auth_providers=[{"type": app_auth_provider_type.type}],
        )

    app_auth_provider_type.compatible_user_source_types = original_compatible


@pytest.mark.django_db
def test_create_user_source_before(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application, order="1.0000"
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application, order="2.0000"
    )

    user_source_type = list(user_source_type_registry.get_all())[0]

    user_source2 = UserSourceService().create_user_source(
        user,
        user_source_type,
        application=application,
        before=user_source3,
    )

    user_sources = UserSource.objects.all()
    assert user_sources[0].id == user_source1.id
    assert user_sources[1].id == user_source2.id
    assert user_sources[2].id == user_source3.id


@pytest.mark.django_db
def test_get_unique_orders_before_user_source_triggering_full_application_order_reset(
    data_fixture,
):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source_1 = data_fixture.create_user_source_with_first_type(
        application=application, order="1.00000000000000000000"
    )
    user_source_2 = data_fixture.create_user_source_with_first_type(
        application=application, order="1.00000000000000001000"
    )
    user_source_3 = data_fixture.create_user_source_with_first_type(
        application=application, order="2.99999999999999999999"
    )
    user_source_4 = data_fixture.create_user_source_with_first_type(
        application=application, order="2.99999999999999999998"
    )

    user_source_type = user_source_type_registry.get("local_baserow")

    user_source_created = UserSourceService().create_user_source(
        user,
        user_source_type,
        application=application,
        before=user_source_3,
    )

    user_source_1.refresh_from_db()
    user_source_2.refresh_from_db()
    user_source_3.refresh_from_db()
    user_source_4.refresh_from_db()

    assert user_source_1.order == Decimal("1.00000000000000000000")
    assert user_source_2.order == Decimal("2.00000000000000000000")
    assert user_source_4.order == Decimal("3.00000000000000000000")
    assert user_source_3.order == Decimal("4.00000000000000000000")
    assert user_source_created.order == Decimal("3.50000000000000000000")


@pytest.mark.django_db
@patch("baserow.core.user_sources.service.user_source_orders_recalculated")
def test_recalculate_full_order(user_source_orders_recalculated_mock, data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    data_fixture.create_user_source_with_first_type(
        application=application, order="1.9000"
    )
    data_fixture.create_user_source_with_first_type(
        application=application, order="3.4000"
    )

    service = UserSourceService()
    service.recalculate_full_orders(user, application)

    user_source_orders_recalculated_mock.send.assert_called_once_with(
        service, application=application
    )


@pytest.mark.django_db
def test_create_user_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    user_source_type = user_source_type_registry.get("local_baserow")

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        UserSourceService().create_user_source(
            user, user_source_type, application=application
        )


@pytest.mark.django_db
def test_get_user_source(data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    assert (
        UserSourceService().get_user_source(user, user_source.id).id == user_source.id
    )


@pytest.mark.django_db
def test_get_user_source_does_not_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(UserSourceDoesNotExist):
        assert UserSourceService().get_user_source(user, 0)


@pytest.mark.django_db
def test_get_user_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        UserSourceService().get_user_source(user, user_source.id)


@pytest.mark.django_db
def test_get_user_sources(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    assert [p.id for p in UserSourceService().get_user_sources(user, application)] == [
        user_source1.id,
        user_source2.id,
        user_source3.id,
    ]

    def exclude_user_source_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=user_source1.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_user_source_1

        assert [
            p.id for p in UserSourceService().get_user_sources(user, application)
        ] == [
            user_source2.id,
            user_source3.id,
        ]


@pytest.mark.django_db
@patch("baserow.core.user_sources.service.user_source_deleted")
def test_delete_user_source(user_source_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    service = UserSourceService()
    service.delete_user_source(user, user_source)

    user_source_deleted_mock.send.assert_called_once_with(
        service,
        user_source_id=user_source.id,
        application=user_source.application,
        user=user,
    )


@pytest.mark.django_db(transaction=True)
def test_delete_user_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        UserSourceService().delete_user_source(user, user_source)


@pytest.mark.django_db
@patch("baserow.core.user_sources.service.user_source_updated")
def test_update_user_source(user_source_updated_mock, data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    service = UserSourceService()
    user_source_updated = service.update_user_source(
        user, user_source, value="newValue"
    )

    user_source_updated_mock.send.assert_called_once_with(
        service, user_source=user_source_updated, user=user
    )


@pytest.mark.django_db(transaction=True)
def test_update_user_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        UserSourceService().update_user_source(user, user_source, value="newValue")


@pytest.mark.django_db
@patch("baserow.core.user_sources.service.user_source_moved")
def test_move_user_source(user_source_moved_mock, data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    service = UserSourceService()
    user_source_moved = service.move_user_source(
        user, user_source3, before=user_source2
    )

    user_source_moved_mock.send.assert_called_once_with(
        service, user_source=user_source_moved, before=user_source2, user=user
    )


@pytest.mark.django_db
def test_move_user_source_not_same_application(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    application2 = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application2
    )

    with pytest.raises(UserSourceNotInSameApplication):
        UserSourceService().move_user_source(user, user_source3, before=user_source2)


@pytest.mark.django_db
def test_move_user_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        UserSourceService().move_user_source(user, user_source3, before=user_source2)


@pytest.mark.django_db
@patch("baserow.core.user_sources.service.user_source_orders_recalculated")
def test_move_user_source_trigger_order_recalculated(
    user_source_orders_recalculated_mock, data_fixture
):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application, order="2.99999999999999999998"
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application, order="2.99999999999999999999"
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application, order="3.0000"
    )

    service = UserSourceService()
    service.move_user_source(user, user_source3, before=user_source2)

    user_source_orders_recalculated_mock.send.assert_called_once_with(
        service, application=application
    )
