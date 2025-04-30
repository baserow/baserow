from unittest.mock import patch

import pytest

from baserow.contrib.builder.domains.domain_types import CustomDomainType
from baserow.contrib.builder.domains.exceptions import DomainNotInBuilder
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.domains.service import DomainService
from baserow.core.exceptions import PermissionException, UserNotInWorkspace
from baserow.core.utils import Progress


@patch("baserow.contrib.builder.domains.service.domain_created")
@pytest.mark.django_db
def test_domain_created_signal_sent(domain_created_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    service = DomainService()
    domain = service.create_domain(
        user, CustomDomainType(), builder, domain_name="test"
    )

    domain_created_mock.send.assert_called_once_with(service, domain=domain, user=user)


@pytest.mark.django_db
def test_create_domain_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()

    with pytest.raises(UserNotInWorkspace):
        DomainService().create_domain(
            user, CustomDomainType, builder, domain_name="test"
        )


@patch("baserow.contrib.builder.domains.service.domain_deleted")
@pytest.mark.django_db
def test_domain_deleted_signal_sent(domain_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    service = DomainService()
    service.delete_domain(user, domain)

    domain_deleted_mock.send.assert_called_once_with(
        service, builder=builder, domain_id=domain.id, user=user
    )


@pytest.mark.django_db(transaction=True)
def test_delete_domain_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    user_unrelated = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    domain = DomainService().create_domain(
        user, CustomDomainType(), builder, domain_name="test"
    )

    with pytest.raises(UserNotInWorkspace):
        DomainService().delete_domain(user_unrelated, domain)

    assert Domain.objects.count() == 1


@pytest.mark.django_db
def test_get_domain_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    with pytest.raises(UserNotInWorkspace):
        DomainService().get_domain(user, domain.id)


@pytest.mark.django_db
def test_get_domains_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    with pytest.raises(UserNotInWorkspace):
        DomainService().get_domains(user, builder)


@pytest.mark.django_db
def test_get_domains_partial_permissions(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    domain_with_access = data_fixture.create_builder_custom_domain(builder=builder)
    domain_without_access = data_fixture.create_builder_custom_domain(builder=builder)

    def exclude_domain_without_access(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=domain_without_access.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_domain_without_access

        assert [p.id for p in DomainService().get_domains(user, builder)] == [
            domain_with_access.id,
        ]


@patch("baserow.contrib.builder.domains.service.domain_updated")
@pytest.mark.django_db
def test_domain_updated_signal_sent(domain_updated_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    service = DomainService()
    service.update_domain(user, domain, domain_name="new.com")

    domain_updated_mock.send.assert_called_once_with(service, domain=domain, user=user)


@pytest.mark.django_db
def test_update_domain_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    with pytest.raises(UserNotInWorkspace):
        DomainService().update_domain(user, domain, domain_name="test.com")


@pytest.mark.django_db
def test_update_domain_invalid_values(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    domain_updated = DomainService().update_domain(user, domain, nonsense="hello")

    assert hasattr(domain_updated, "nonsense") is False


@patch("baserow.contrib.builder.domains.service.domains_reordered")
@pytest.mark.django_db
def test_domains_reordered_signal_sent(domains_reordered_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder, order=2)

    service = DomainService()
    full_order = service.order_domains(user, builder, [domain_two.id, domain_one.id])

    domains_reordered_mock.send.assert_called_once_with(
        service, builder=builder, order=full_order, user=user
    )


@pytest.mark.django_db
def test_order_domains_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder, order=2)

    with pytest.raises(UserNotInWorkspace):
        DomainService().order_domains(user, builder, [domain_two.id, domain_one.id])


@pytest.mark.django_db
def test_order_domains_domain_not_in_builder(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(order=2)

    with pytest.raises(DomainNotInBuilder):
        DomainService().order_domains(user, builder, [domain_two.id, domain_one.id])


@pytest.mark.django_db
def test_get_published_builder_by_domain_name(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to
    )

    result = DomainService().get_public_builder_by_domain_name(
        user, domain1.domain_name
    )

    assert builder_to == result


@pytest.mark.django_db
def test_get_published_builder_by_domain_name_unauthorized(
    data_fixture, stub_check_permissions
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to
    )

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DomainService().get_public_builder_by_domain_name(user, domain1.domain_name)


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.handler.run_async_job")
def test_async_publish_domain(mock_run_async_job, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    domain1 = data_fixture.create_builder_custom_domain(builder=builder)

    job = DomainService().async_publish(user, domain1)

    mock_run_async_job.delay.assert_called_once()
    args = mock_run_async_job.delay.call_args
    assert args[0][0] == job.id


@pytest.mark.django_db(transaction=True)
def test_async_publish_domain_no_permission(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    domain1 = data_fixture.create_builder_custom_domain()

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DomainService().async_publish(user, domain1)


@pytest.mark.django_db()
@patch("baserow.contrib.builder.domains.service.domain_updated")
def test_publish_domain(domain_updated_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    domain1 = data_fixture.create_builder_custom_domain(builder=builder)

    progress = Progress(100)
    service = DomainService()
    domain = service.publish(user, domain1, progress)

    domain_updated_mock.send.assert_called_once_with(service, domain=domain, user=user)


@pytest.mark.django_db()
def test_publish_domain_unauthorized(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    domain1 = data_fixture.create_builder_custom_domain(builder=builder)

    progress = Progress(100)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DomainService().publish(user, domain1, progress)
