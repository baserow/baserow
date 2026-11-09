from unittest.mock import patch

from django.db import DEFAULT_DB_ALIAS
from django.shortcuts import reverse
from django.test import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
)

from baserow.api.settings.registries import SettingsDataRegistry, SettingsDataType
from baserow.core.actions import UpdateAdminSettingsActionType
from baserow.core.handler import CoreHandler
from baserow.core.models import Settings, Template
from baserow.core.user_templates.handler import UserTemplateHandler
from tests.baserow.contrib.database.utils import get_deadlock_error
from tests.baserow.core.user_templates.utils import create_template, recorded_actions


@pytest.mark.django_db
def test_get_settings(api_client):
    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "instance_id" not in response_json
    assert response_json["allow_new_signups"] is True

    settings = Settings.objects.first()
    settings.allow_new_signups = False
    settings.save()

    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "instance_id" not in response_json
    assert response_json["allow_new_signups"] is False
    assert response_json["email_verification"] == "no_verification"

    # None is not returned as a value for email_verification
    settings.email_verification = None
    settings.save()
    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["email_verification"] == "no_verification"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "domain,secret,receiver_url,expected",
    [
        ("inbound.example.com", "s", "http://email-receiver:8880", True),
        ("", "s", "http://email-receiver:8880", False),
        ("inbound.example.com", "", "http://email-receiver:8880", False),
        ("inbound.example.com", "s", "", False),
    ],
)
def test_get_settings_reports_whether_inbound_email_is_enabled(
    api_client, domain, secret, receiver_url, expected
):
    # The frontend hides the email trigger unless this is true; it mirrors the
    # backend's own gate, so an instance with the domain and secret but no
    # receiver URL (and therefore no message sweep) does not offer the trigger.
    with override_settings(
        INBOUND_EMAIL_DOMAIN=domain,
        INBOUND_EMAIL_WEBHOOK_SECRET=secret,
        INBOUND_EMAIL_RECEIVER_URL=receiver_url,
    ):
        response = api_client.get(reverse("api:settings:get"))

    assert response.status_code == HTTP_200_OK
    assert response.json()["inbound_email_enabled"] is expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "backend,expected",
    [
        ("django.core.mail.backends.smtp.EmailBackend", True),
        ("django.core.mail.backends.console.EmailBackend", False),
        ("", False),
    ],
)
def test_get_settings_reports_whether_email_delivery_is_enabled(
    api_client, backend, expected
):
    with override_settings(CELERY_EMAIL_BACKEND=backend):
        response = api_client.get(reverse("api:settings:get"))

    assert response.status_code == HTTP_200_OK
    assert response.json()["email_delivery_enabled"] is expected


@pytest.mark.django_db
def test_inbound_email_enabled_cannot_be_updated(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"inbound_email_enabled": True, "allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["allow_new_signups"] is False
    assert response.json()["inbound_email_enabled"] is False


@pytest.mark.django_db
def test_realtime_recovery_only_pins_authenticated_settings_reads(
    api_client, data_fixture
):
    _user, token = data_fixture.create_user_and_token()
    recovery_header = {"HTTP_X_BASEROW_REALTIME_RECOVERY": "true"}

    with patch(
        "baserow.api.mixins.set_db_alias",
        return_value=DEFAULT_DB_ALIAS,
    ) as mock_set_db_alias:
        response = api_client.get(
            reverse("api:settings:get"),
            HTTP_AUTHORIZATION=f"JWT {token}",
            **recovery_header,
        )
        assert response.status_code == HTTP_200_OK
        mock_set_db_alias.assert_called_with(DEFAULT_DB_ALIAS)

        mock_set_db_alias.reset_mock()
        response = api_client.get(reverse("api:settings:get"), **recovery_header)
        assert response.status_code == HTTP_200_OK
        mock_set_db_alias.assert_not_called()


@pytest.mark.django_db
def test_require_first_admin_user_is_false_after_admin_creation(
    api_client, data_fixture
):
    data_fixture.create_password_provider()
    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_admin_signup_page"] is True

    # create the admin user
    response = api_client.post(
        reverse("api:user:index"),
        {
            "name": "admin",
            "email": "admin@baserow.io",
            "password": "admin1234",
            "language": "en",
            "authenticate": True,
        },
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    token = response_json["access_token"]

    response = api_client.get(
        reverse("api:settings:get"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["show_admin_signup_page"] is False


@pytest.mark.django_db
def test_get_instance_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    user_2, token_2 = data_fixture.create_user_and_token()

    response = api_client.get(reverse("api:settings:instance_id"))
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.get(
        reverse("api:settings:instance_id"),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert CoreHandler().get_settings().allow_new_signups is True

    response = api_client.get(
        reverse("api:settings:instance_id"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["instance_id"]) > 32

    settings = Settings.objects.first()
    settings.allow_new_signups = False
    settings.save()

    response = api_client.get(
        reverse("api:settings:instance_id"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["instance_id"] == settings.instance_id


@pytest.mark.django_db
def test_update_settings(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    user_2, token_2 = data_fixture.create_user_and_token()

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert CoreHandler().get_settings().allow_new_signups is True

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["allow_new_signups"][0]["code"] == "invalid"

    response = api_client.patch(
        reverse("api:settings:update"),
        {"instance_id": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert CoreHandler().get_settings().instance_id != "test"

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["allow_new_signups"] is False
    assert "instance_id" not in response_json
    assert CoreHandler().get_settings().allow_new_signups is False

    response = api_client.patch(
        reverse("api:settings:update"),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["allow_new_signups"] is False
    assert "instance_id" not in response_json
    assert CoreHandler().get_settings().allow_new_signups is False


@pytest.mark.django_db
def test_update_co_branding_logo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )

    response = api_client.patch(
        reverse("api:settings:update"),
        {"co_branding_logo": {"name": file1.name}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["co_branding_logo"]["name"] == file1.name

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["co_branding_logo"]["name"] == file1.name


@pytest.mark.django_db
def test_update_show_baserow_help_request(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"show_baserow_help_request": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_baserow_help_request"] is False

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_baserow_help_request"] is False


@pytest.mark.django_db
def test_register_settings_data_type(api_client, data_fixture):
    registry = SettingsDataRegistry()

    class TmpSettingsDataType(SettingsDataType):
        type = "test_tmp"

        def get_settings_data(self, request) -> dict:
            return "hello"

    registry.register(TmpSettingsDataType())

    with patch("baserow.api.settings.views.settings_data_registry", new=registry):
        response = api_client.get(reverse("api:settings:get"))
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert len(response_json.keys()) > 1
        assert response_json["test_tmp"] == "hello"


@pytest.mark.parametrize("value", [None, "invalid"])
@pytest.mark.django_db
def test_update_email_verification_settings_invalid(api_client, data_fixture, value):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"email_verification": value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["email_verification"][0]["code"] == "invalid_choice"


@pytest.mark.django_db
def test_update_email_verification_settings(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"email_verification": "recommended"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert CoreHandler().get_settings().email_verification == "recommended"


@pytest.mark.django_db
def test_partial_update_does_not_overwrite_email_verification(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"email_verification": "recommended"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert CoreHandler().get_settings().email_verification == "recommended"

    response = api_client.patch(
        reverse("api:settings:update"),
        {"track_workspace_usage": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json["track_workspace_usage"] is True

    settings = CoreHandler().get_settings()
    assert settings.email_verification == "recommended"
    assert response_json["email_verification"] == "recommended"


@pytest.mark.django_db
def test_allow_reporting_abuse_setting(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    user_2, token_2 = data_fixture.create_user_and_token()

    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    assert response.json()["allow_reporting_abuse"] is True

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_reporting_abuse": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert CoreHandler().get_settings().allow_reporting_abuse is True

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_reporting_abuse": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["allow_reporting_abuse"] is False
    assert CoreHandler().get_settings().allow_reporting_abuse is False


@pytest.mark.django_db
@pytest.mark.parametrize("flag", [True, False])
def test_user_templates_require_approval_setting(
    api_client, data_fixture, settings, flag
):
    if not flag:
        settings.FEATURE_FLAGS = []
    token = data_fixture.create_user_and_token(is_staff=True)[1]
    response = api_client.get(reverse("api:settings:get"))
    assert response.json()["user_templates_require_approval"] is True

    with recorded_actions() as actions:
        response = api_client.patch(
            reverse("api:settings:update"),
            {"user_templates_require_approval": False, "allow_new_signups": True},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    if flag:
        assert response.status_code == HTTP_200_OK
        assert actions == [
            (
                "admin_update_settings",
                {"settings": {"user_templates_require_approval": False}},
            )
        ]
        assert UpdateAdminSettingsActionType.get_long_description(actions[0][1]) == (
            "Settings updated: User templates require approval: off"
        )
    else:
        assert response.status_code == HTTP_403_FORBIDDEN
        assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert CoreHandler().get_settings().user_templates_require_approval is not flag


@pytest.mark.django_db
def test_update_settings_without_a_change_records_no_action(api_client, data_fixture):
    token = data_fixture.create_user_and_token(is_staff=True)[1]

    with recorded_actions() as actions:
        response = api_client.patch(
            reverse("api:settings:update"),
            {"allow_new_signups": True},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    assert actions == []


@pytest.mark.django_db
@pytest.mark.parametrize("deadlocks,status", [(1, HTTP_200_OK), (2, HTTP_409_CONFLICT)])
def test_switching_approval_off_is_retried_after_a_deadlock(
    api_client, data_fixture, deadlocks, status
):
    token = data_fixture.create_user_and_token(is_staff=True)[1]
    template = create_template(data_fixture, None, "in_review")
    approve = UserTemplateHandler.approve_pending_revisions
    attempts = []

    def deadlock(handler, admin):
        attempts.append(admin)
        if len(attempts) <= deadlocks:
            raise get_deadlock_error()
        return approve(handler, admin)

    with patch.object(UserTemplateHandler, "approve_pending_revisions", deadlock):
        response = api_client.patch(
            reverse("api:settings:update"),
            {"user_templates_require_approval": False},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == status
    switched_off = status == HTTP_200_OK
    if not switched_off:
        assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"
    assert CoreHandler().get_settings().user_templates_require_approval is not (
        switched_off
    )
    listed = Template.objects.get(id=template.id).public_revision_id is not None
    assert listed is switched_off
