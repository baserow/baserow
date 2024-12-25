from django.core.cache import cache
from django.db import transaction

import pytest
from freezegun import freeze_time

from baserow.core.action.registries import action_type_registry
from baserow.core.auth_provider.handler import PasswordProviderHandler
from baserow.core.models import UserLogEntry
from baserow.core.user.actions import (
    CancelUserDeletionActionType,
    ChangeUserPasswordActionType,
    CreateUserActionType,
    ResetUserPasswordActionType,
    ScheduleUserDeletionActionType,
    SendResetUserPasswordActionType,
    SignInUserActionType,
    UpdateUserActionType,
)
from baserow.core.user.handler import UserHandler
from baserow.throttling_types import RateLimit
from baserow_enterprise.audit_log.models import AuditLogEntry


@pytest.mark.django_db
def test_create_user_action_type():
    user = action_type_registry.get(CreateUserActionType.type).do(
        name="Test", email="user@test.com", password="test1234", language="en"
    )
    assert user.first_name == "Test"
    assert user.email == "user@test.com"
    assert user.profile.language == "en"


@pytest.mark.django_db
def test_update_user_action_type(data_fixture):
    user = data_fixture.create_user(first_name="User")
    updated_user = action_type_registry.get(UpdateUserActionType.type).do(
        user, first_name="Test"
    )
    assert updated_user.first_name == "Test"


@pytest.mark.django_db
def test_schedule_user_deletion_action_type(data_fixture):
    user = data_fixture.create_user()
    action_type_registry.get(ScheduleUserDeletionActionType.type).do(user)
    assert user.profile.to_be_deleted is True


@pytest.mark.django_db
def test_cancel_user_deletion_action_type(data_fixture):
    user = data_fixture.create_user()
    UserHandler().schedule_user_deletion(user)
    assert user.profile.to_be_deleted is True

    action_type_registry.get(CancelUserDeletionActionType.type).do(user)
    assert user.profile.to_be_deleted is False


@pytest.mark.django_db
def test_sign_in_user_action_type(data_fixture):
    user = data_fixture.create_user()

    with freeze_time("2020-01-01 12:00:00"):
        action_type_registry.get(SignInUserActionType.type).do(user)

    assert user.last_login is not None
    assert str(user.last_login) == "2020-01-01 12:00:00+00:00"

    last_login = user.last_login

    password_auth_provider = PasswordProviderHandler.get()
    # We check the grace delay between to last_login updates
    with freeze_time("2020-01-01 12:00:30"):
        action_type_registry.get(SignInUserActionType.type).do(
            user, password_auth_provider
        )

    assert user.last_login == last_login

    with freeze_time("2020-01-01 12:01:01"):
        action_type_registry.get(SignInUserActionType.type).do(
            user, password_auth_provider
        )

    assert user.last_login > last_login


@pytest.mark.django_db(transaction=True)
def test_sign_in_user_action_type_action_log_limit(settings, data_fixture):
    settings.BASEROW_LOGIN_ACTION_LOG_LIMIT = RateLimit.from_string("2/h")
    user = data_fixture.create_user()
    cache_key = f"log_signin_action:{user.username}:PasswordAuthProviderModel"
    cache.delete(cache_key)

    # sign ins are logged
    with freeze_time("2020-01-01 12:00:10"), transaction.atomic():
        action_type_registry.get(SignInUserActionType.type).do(user)
    with freeze_time("2020-01-01 12:01:20"), transaction.atomic():
        action_type_registry.get(SignInUserActionType.type).do(user)

    # sing ins are NOT logged
    with freeze_time("2020-01-01 12:02:20"), transaction.atomic():
        action_type_registry.get(SignInUserActionType.type).do(user)

    user.refresh_from_db()
    assert str(user.last_login) == "2020-01-01 12:01:20+00:00"
    assert UserLogEntry.objects.count() == 2
    assert AuditLogEntry.objects.filter(action_type="sign_in_user").count() == 2


@pytest.mark.django_db
def test_change_user_password_action_type(data_fixture):
    user = data_fixture.create_user(password="12345678")
    user = action_type_registry.get(ChangeUserPasswordActionType.type).do(
        user, "12345678", "87654321"
    )
    assert user.check_password("87654321") is True


@pytest.mark.django_db(transaction=True)
def test_send_reset_user_password_action_type(data_fixture, mailoutbox):
    user = data_fixture.create_user(password="12345678")

    action_type_registry.get(SendResetUserPasswordActionType.type).do(
        user, "http://localhost:3000/reset-password"
    )
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_reset_user_password_action_type(data_fixture):
    user = data_fixture.create_user(password="12345678")
    signer = UserHandler().get_reset_password_signer()
    user_session = signer.dumps(user.id)
    user = action_type_registry.get(ResetUserPasswordActionType.type).do(
        user_session, "12345678"
    )
    user.check_password("12345678") is True
