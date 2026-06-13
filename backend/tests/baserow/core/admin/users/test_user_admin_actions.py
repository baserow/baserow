import pytest

from baserow.core.action.signals import action_done
from baserow.core.admin.users.actions import AdminDisableTwoFactorAuthActionType
from baserow.core.two_factor_auth.exceptions import TwoFactorAuthNotConfigured
from baserow.core.two_factor_auth.handler import TwoFactorAuthHandler


@pytest.mark.django_db
def test_admin_disable_two_factor_auth_action_disables_and_registers(data_fixture):
    staff_user = data_fixture.create_user(is_staff=True)
    user = data_fixture.create_user()
    data_fixture.configure_totp(user)

    received = []

    def receiver(sender, user, action_type, action_params, **kwargs):
        received.append((user, action_type, action_params))

    action_done.connect(receiver)
    try:
        AdminDisableTwoFactorAuthActionType.do(staff_user, user.id)
    finally:
        action_done.disconnect(receiver)

    assert TwoFactorAuthHandler().get_provider(user) is None
    assert len(received) == 1
    acting_user, action_type, params = received[0]
    assert acting_user.id == staff_user.id
    assert action_type.type == "admin_disable_two_factor_auth"
    assert params["user_id"] == staff_user.id
    assert params["user_email"] == staff_user.email
    assert params["disabled_user_id"] == user.id
    assert params["disabled_user_email"] == user.email


@pytest.mark.django_db
def test_admin_disable_two_factor_auth_action_not_registered_on_failure(data_fixture):
    staff_user = data_fixture.create_user(is_staff=True)
    user = data_fixture.create_user()

    received = []

    def receiver(sender, **kwargs):
        received.append(kwargs)

    action_done.connect(receiver)
    try:
        with pytest.raises(TwoFactorAuthNotConfigured):
            AdminDisableTwoFactorAuthActionType.do(staff_user, user.id)
    finally:
        action_done.disconnect(receiver)

    assert len(received) == 0
