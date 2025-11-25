import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connections, transaction
from django.test import override_settings

import pytest
import responses
from freezegun import freeze_time
from itsdangerous.exc import BadSignature, SignatureExpired
from responses.matchers import json_params_matcher

from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.models import Database, Table
from baserow.core.exceptions import (
    BaseURLHostnameNotAllowed,
    WorkspaceInvitationDoesNotExist,
    WorkspaceInvitationEmailMismatch,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import BlacklistedToken, UserLogEntry, Workspace, WorkspaceUser
from baserow.core.registries import plugin_registry
from baserow.core.user.exceptions import (
    DisabledSignupError,
    EmailAlreadyVerified,
    InvalidPassword,
    InvalidVerificationToken,
    PasswordDoesNotMatchValidation,
    RefreshTokenAlreadyBlacklisted,
    ResetPasswordDisabledError,
    UserAlreadyExist,
    UserIsLastAdmin,
    UserNotFound,
)
from baserow.core.user.handler import UserHandler

User = get_user_model()
invalid_passwords = [
    "",
    "a",
    "ab",
    "ask",
    "oiue",
    "dsj43",
    "984kds",
    "dsfkjh4",
    (
        "Bgvmt95en6HGJZ9Xz0F8xysQ6eYgo2Y54YzRPxxv10b5n16F4rZ6YH4ulonocwiFK6970KiAxoYhU"
        "LYA3JFDPIQGj5gMZZl25M46sO810Zd3nyBg699a2TDMJdHG7hAAi0YeDnuHuabyBawnb4962OQ1OO"
        "f1MxzFyNWG7NR2X6MZQL5G1V61x56lQTXbvK1AG1IPM87bQ3YAtIBtGT2vK3Wd83q3he5ezMtUfzK"
        "2ibj0WWhf86DyQB4EHRUJjYcBiI78iEJv5hcu33X2I345YosO66cTBWK45SqJEDudrCOq"
    ),
]


@pytest.mark.django_db
def test_get_user(data_fixture):
    user_1 = data_fixture.create_user(email="user1@localhost")

    handler = UserHandler()

    with pytest.raises(ValueError):
        handler.get_active_user()

    with pytest.raises(UserNotFound):
        handler.get_active_user(user_id=-1)

    with pytest.raises(UserNotFound):
        handler.get_active_user(email="user3@localhost")

    assert handler.get_active_user(user_id=user_1.id).id == user_1.id
    assert handler.get_active_user(email=user_1.email).id == user_1.id


@pytest.mark.django_db
def test_create_user(data_fixture):
    plugin_mock = MagicMock()
    with patch.dict(plugin_registry.registry, {"mock": plugin_mock}):
        user_handler = UserHandler()
        valid_password = "thisIsAValidPassword"

        data_fixture.update_settings(allow_new_signups=False)
        with pytest.raises(DisabledSignupError):
            user_handler.create_user("Test1", "test@test.nl", valid_password)
        assert User.objects.all().count() == 0
        data_fixture.update_settings(allow_new_signups=True)

        user = user_handler.create_user("Test1", "test@test.nl", valid_password)
        assert user.pk
        assert user.first_name == "Test1"
        assert user.email == "test@test.nl"
        assert user.username == "test@test.nl"
        assert user.profile.language == "en"
        assert user.profile.completed_onboarding is False

        assert Workspace.objects.all().count() == 0

        plugin_mock.user_created.assert_called_with(user, None, None, None)

        with pytest.raises(UserAlreadyExist):
            user_handler.create_user("Test1", "test@test.nl", valid_password)


@pytest.mark.django_db
def test_update_user(data_fixture):
    user_handler = UserHandler()
    user = data_fixture.create_user(first_name="Initial", language="fr")

    user_handler.update_user(user, first_name="Updated")

    user.refresh_from_db()
    user.profile.refresh_from_db()
    assert user.first_name == "Updated"
    assert user.profile.language == "fr"

    user_handler.update_user(user, language="en")

    user.refresh_from_db()
    user.profile.refresh_from_db()
    assert user.first_name == "Updated"
    assert user.profile.language == "en"


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_password", invalid_passwords)
def test_create_user_invalid_password(data_fixture, invalid_password):
    user_handler = UserHandler()

    with pytest.raises(PasswordDoesNotMatchValidation):
        user_handler.create_user("Test1", "test@test.nl", invalid_password)


@pytest.mark.django_db
def test_first_ever_created_user_is_staff(data_fixture):
    user_handler = UserHandler()
    valid_password = "thisIsAValidPassword"

    data_fixture.update_settings(allow_new_signups=True)

    first_user = user_handler.create_user(
        "First Ever User", "test@test.nl", valid_password
    )
    assert first_user.first_name == "First Ever User"
    assert first_user.is_staff

    second_user = user_handler.create_user(
        "Second User", "test2@test.nl", valid_password
    )
    assert second_user.first_name == "Second User"
    assert not second_user.is_staff


@pytest.mark.django_db
def test_create_user_with_invitation(data_fixture):
    plugin_mock = MagicMock()
    with patch.dict(plugin_registry.registry, {"mock": plugin_mock}):
        valid_password = "thisIsAValidPassword"

        user_handler = UserHandler()
        core_handler = CoreHandler()

        invitation = data_fixture.create_workspace_invitation(email="test0@test.nl")
        signer = core_handler.get_workspace_invitation_signer()

        with pytest.raises(BadSignature):
            user_handler.create_user(
                "Test1",
                "test0@test.nl",
                valid_password,
                workspace_invitation_token="INVALID",
            )

        with pytest.raises(WorkspaceInvitationDoesNotExist):
            user_handler.create_user(
                "Test1",
                "test0@test.nl",
                valid_password,
                workspace_invitation_token=signer.dumps(99999),
            )

        with pytest.raises(WorkspaceInvitationEmailMismatch):
            user_handler.create_user(
                "Test1",
                "test1@test.nl",
                valid_password,
                workspace_invitation_token=signer.dumps(invitation.id),
            )

        data_fixture.update_settings(
            allow_new_signups=False, allow_signups_via_workspace_invitations=False
        )
        with pytest.raises(DisabledSignupError):
            user_handler.create_user(
                "Test1",
                "test0@test.nl",
                valid_password,
                workspace_invitation_token=signer.dumps(invitation.id),
            )

        data_fixture.update_settings(
            allow_new_signups=False, allow_signups_via_workspace_invitations=True
        )
        user = user_handler.create_user(
            "Test1",
            "test0@test.nl",
            valid_password,
            workspace_invitation_token=signer.dumps(invitation.id),
        )

        assert user.profile.completed_onboarding is True

        assert Workspace.objects.all().count() == 1
        assert Workspace.objects.all().first().id == invitation.workspace_id
        assert WorkspaceUser.objects.all().count() == 2

        plugin_mock.user_created.assert_called_once()
        args = plugin_mock.user_created.call_args
        assert args[0][0] == user
        assert args[0][1].id == invitation.workspace_id
        assert args[0][2].email == invitation.email
        assert args[0][2].workspace_id == invitation.workspace_id

        # We do not expect any initial data to have been created.
        assert Database.objects.all().count() == 0
        assert Table.objects.all().count() == 0


@pytest.mark.django_db
def test_create_user_with_template(data_fixture):
    old_templates = settings.APPLICATION_TEMPLATES_DIR
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )
    template = data_fixture.create_template(slug="example-template")
    user_handler = UserHandler()
    valid_password = "thisIsAValidPassword"
    user = user_handler.create_user(
        "Test1", "test0@test.nl", valid_password, template=template
    )

    assert user.profile.completed_onboarding is True
    assert Workspace.objects.all().count() == 2
    workspace = Workspace.objects.filter(users__in=[user.id]).first()
    assert workspace.users.filter(id=user.id).count() == 1
    assert workspace.name == "Test1's workspace"

    assert WorkspaceUser.objects.all().count() == 1
    # We expect the example template to be installed
    assert Database.objects.all().count() == 1
    assert Database.objects.all().first().name == "Event marketing"
    assert Table.objects.all().count() == 2

    settings.APPLICATION_TEMPLATES_DIR = old_templates


@pytest.mark.django_db
def test_create_user_with_template_different_language(data_fixture):
    old_templates = settings.APPLICATION_TEMPLATES_DIR
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )
    template = data_fixture.create_template(slug="example-template")
    user_handler = UserHandler()
    valid_password = "thisIsAValidPassword"
    user = user_handler.create_user(
        "Test1", "test0@test.nl", valid_password, template=template, language="fr"
    )

    assert Workspace.objects.all().count() == 2
    workspace = Workspace.objects.filter(users__in=[user.id]).first()
    assert workspace.users.filter(id=user.id).count() == 1
    assert workspace.name == "Projet de « Test1 »"

    settings.APPLICATION_TEMPLATES_DIR = old_templates


@pytest.mark.django_db(transaction=True)
def test_send_reset_password_email(data_fixture, mailoutbox):
    user = data_fixture.create_user(email="test@localhost")
    handler = UserHandler()

    with pytest.raises(BaseURLHostnameNotAllowed):
        handler.send_reset_password_email(user, "http://test.nl/reset-password")

    signer = handler.get_reset_password_signer()
    handler.send_reset_password_email(user, "http://localhost:3000/reset-password")

    assert len(mailoutbox) == 1
    email = mailoutbox[0]

    assert email.subject == "Reset password - Baserow"
    assert email.from_email == "no-reply@localhost"
    assert "test@localhost" in email.to

    html_body = email.alternatives[0][0]
    search_url = "http://localhost:3000/reset-password/"
    start_url_index = html_body.index(search_url)

    assert start_url_index != -1

    end_url_index = html_body.index('"', start_url_index)
    token = html_body[start_url_index + len(search_url) : end_url_index]

    user_id = signer.loads(token)
    assert user_id == user.id


@pytest.mark.django_db(transaction=True)
def test_send_reset_password_email_in_different_language(data_fixture, mailoutbox):
    user = data_fixture.create_user(email="test@localhost", language="fr")
    handler = UserHandler()

    handler.send_reset_password_email(user, "http://localhost:3000/reset-password")

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Réinitialiser le mot de passe - Baserow"


@pytest.mark.django_db(transaction=True)
def test_send_reset_password_email_reset_password_disabled(data_fixture):
    user = data_fixture.create_user(email="test@localhost", is_staff=True)

    CoreHandler().update_settings(user, allow_reset_password=False)

    with pytest.raises(ResetPasswordDisabledError):
        UserHandler().send_reset_password_email(
            user, "http://localhost:3000/reset-password"
        )


@pytest.mark.django_db
def test_reset_password(data_fixture):
    user = data_fixture.create_user(email="test@localhost")
    handler = UserHandler()
    valid_password = "thisIsAValidPassword"

    signer = handler.get_reset_password_signer()

    with pytest.raises(BadSignature):
        handler.reset_password("test", valid_password)
        assert not user.check_password(valid_password)

    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps(9999)

    with freeze_time("2020-01-02 12:00"):
        with pytest.raises(UserNotFound):
            handler.reset_password(token, valid_password)
            assert not user.check_password(valid_password)

    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps(user.id)

    with freeze_time("2020-01-04 12:00"):
        with pytest.raises(SignatureExpired):
            handler.reset_password(token, valid_password)
            assert not user.check_password(valid_password)

    with freeze_time("2020-01-02 12:00"):
        user = handler.reset_password(token, valid_password)
        assert user.check_password(valid_password)
        assert user.profile.last_password_change == datetime(
            2020, 1, 2, 12, 00, tzinfo=timezone.utc
        )


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_password", invalid_passwords)
def test_reset_password_invalid_new_password(data_fixture, invalid_password):
    user = data_fixture.create_user(email="test@localhost")
    handler = UserHandler()

    signer = handler.get_reset_password_signer()
    token = signer.dumps(user.id)

    with pytest.raises(PasswordDoesNotMatchValidation):
        handler.reset_password(token, invalid_password)


@pytest.mark.django_db
def test_reset_password_reset_password_disabled(data_fixture):
    user = data_fixture.create_user(email="test@localhost", is_staff=True)
    handler = UserHandler()

    signer = handler.get_reset_password_signer()
    token = signer.dumps(user.id)

    CoreHandler().update_settings(user, allow_reset_password=False)

    with pytest.raises(ResetPasswordDisabledError):
        handler.reset_password(token, "new_password")


@pytest.mark.django_db
def test_change_password(data_fixture):
    valid_password = "aValidPassword"
    valid_new_password = "aValidNewPassword"
    user = data_fixture.create_user(email="test@localhost", password=valid_password)
    handler = UserHandler()

    with pytest.raises(InvalidPassword):
        handler.change_password(user, "INCORRECT", valid_new_password)

    user.refresh_from_db()
    assert user.check_password(valid_password)

    with freeze_time("2020-01-01 12:00"):
        user = handler.change_password(user, valid_password, valid_new_password)
        assert user.check_password(valid_new_password)
        assert user.profile.last_password_change == datetime(
            2020, 1, 1, 12, 00, tzinfo=timezone.utc
        )


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_password", invalid_passwords)
def test_change_password_invalid_new_password(data_fixture, invalid_password):
    validOldPW = "thisPasswordIsValid"
    user = data_fixture.create_user(email="test@localhost", password=validOldPW)
    handler = UserHandler()

    with pytest.raises(PasswordDoesNotMatchValidation):
        handler.change_password(user, validOldPW, invalid_password)

    user.refresh_from_db()
    assert user.check_password(validOldPW)


@pytest.mark.django_db(transaction=True)
def test_schedule_user_deletion(data_fixture, mailoutbox):
    valid_password = "aValidPassword"
    user = data_fixture.create_user(
        email="test@localhost", password=valid_password, is_staff=True
    )
    handler = UserHandler()

    with pytest.raises(UserIsLastAdmin):
        handler.schedule_user_deletion(user)

    data_fixture.create_user(email="test_admin@localhost", is_staff=True)

    assert len(mailoutbox) == 0

    handler.schedule_user_deletion(user)

    user.refresh_from_db()
    assert user.profile.to_be_deleted is True

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Account deletion scheduled - Baserow"


@pytest.mark.django_db(transaction=True)
def test_cancel_user_deletion(data_fixture, mailoutbox):
    user = data_fixture.create_user(email="test@localhost", to_be_deleted=True)
    handler = UserHandler()

    handler.cancel_user_deletion(user)

    user.refresh_from_db()
    assert user.profile.to_be_deleted is False

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Account deletion cancelled - Baserow"


@pytest.mark.django_db(transaction=False)
def test_delete_expired_users_and_related_workspaces_if_last_admin(
    data_fixture, mailoutbox, django_capture_on_commit_callbacks
):
    user1 = data_fixture.create_user(email="test1@localhost", to_be_deleted=True)
    user2 = data_fixture.create_user(email="test2@localhost", to_be_deleted=True)
    user3 = data_fixture.create_user(email="test3@localhost")
    user4 = data_fixture.create_user(email="test4@localhost")
    user5 = data_fixture.create_user(email="test5@localhost", to_be_deleted=True)
    user6 = data_fixture.create_user(email="test6@localhost", is_active=False)

    connection = connections["default"]
    initial_table_names = sorted(connection.introspection.table_names())

    database = data_fixture.create_database_application(user=user1)
    # The link field and the many to many table should be deleted at the end
    table, table2, link_field = data_fixture.create_two_linked_tables(
        user=user1, database=database
    )

    model_a = table.get_model()
    row_a_1 = model_a.objects.create()
    row_a_2 = model_a.objects.create()

    model_b = table2.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    getattr(row_a_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_a_2, f"field_{link_field.id}").set([row_b_2.id])

    # Create a multiple select field with option (creates an extra table that should
    # be deleted at the end)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )

    # Only one deleted admin
    workspaceuser1 = data_fixture.create_user_workspace(user=user1)

    # With two admins that are going to be deleted and one user
    workspaceuser1_2 = data_fixture.create_user_workspace(user=user1)
    workspaceuser5_2 = data_fixture.create_user_workspace(
        user=user5, workspace=workspaceuser1_2.workspace
    )
    workspaceuser3 = data_fixture.create_user_workspace(
        user=user3, permissions="MEMBER", workspace=workspaceuser1_2.workspace
    )

    # With two admins but one non active and we delete the other
    workspaceuser1_3 = data_fixture.create_user_workspace(user=user1)
    workspaceuser6 = data_fixture.create_user_workspace(
        user=user6, workspace=workspaceuser1_3.workspace
    )

    # Only one non deleted admin
    workspaceuser2 = data_fixture.create_user_workspace(user=user2)

    # Only one admin non deleted and with a deleted user
    workspaceuser4 = data_fixture.create_user_workspace(user=user4)
    workspaceuser5 = data_fixture.create_user_workspace(
        user=user5, permissions="MEMBER", workspace=workspaceuser4.workspace
    )

    # One deleted admin with normal user
    workspaceuser4_2 = data_fixture.create_user_workspace(
        user=user4, permissions="MEMBER"
    )
    workspaceuser5_3 = data_fixture.create_user_workspace(
        user=user5, workspace=workspaceuser4_2.workspace
    )

    handler = UserHandler()

    # Last login before max expiration date (should be deleted)
    with freeze_time("2020-01-01 12:00"):
        handler.update_last_login(user1)
        handler.update_last_login(user3)
        handler.update_last_login(user5)

    # Last login after max expiration date (shouldn't be deleted)
    with freeze_time("2020-01-05 12:00"):
        handler.update_last_login(user2)
        handler.update_last_login(user4)

    with freeze_time("2020-01-07 12:00"):
        with django_capture_on_commit_callbacks(execute=True):
            handler.delete_expired_users_and_related_workspaces_if_last_admin(
                grace_delay=timedelta(days=3)
            )

    user_ids = User.objects.values_list("pk", flat=True)
    assert len(user_ids) == 4
    assert user1.id not in user_ids
    assert user5.id not in user_ids
    assert user2.id in user_ids
    assert user3.id in user_ids
    assert user4.id in user_ids
    assert user6.id in user_ids

    workspace_ids = Workspace.objects.values_list("pk", flat=True)
    assert len(workspace_ids) == 3
    assert workspaceuser1.workspace.id not in workspace_ids
    assert workspaceuser1_2.workspace.id not in workspace_ids
    assert workspaceuser1_3.workspace.id in workspace_ids
    assert workspaceuser2.workspace.id in workspace_ids
    assert workspaceuser4.workspace.id in workspace_ids
    assert workspaceuser4_2.workspace.id not in workspace_ids

    end_table_names = sorted(connection.introspection.table_names())

    # Check that everything has really been deleted
    assert Database.objects.count() == 0
    assert Table.objects.count() == 0
    assert SelectOption.objects.count() == 0
    assert initial_table_names == end_table_names

    # Check mail sent
    assert len(mailoutbox) == 2
    assert mailoutbox[0].subject == "Account permanently deleted - Baserow"


@pytest.mark.django_db
def test_active_users_qs_excludes_deactivated_users(data_fixture):
    deactivated_user = data_fixture.create_user(
        email="test1@localhost", is_active=False
    )
    active_user = data_fixture.create_user(email="test2@localhost", is_active=True)
    assert set(
        UserHandler().get_all_active_users_qs().values_list("id", flat=True)
    ) == {active_user.id}


@pytest.mark.django_db
def test_active_users_qs_excludes_pending_deletion_users(data_fixture):
    user_pending_deletion = data_fixture.create_user(
        email="test1@localhost", to_be_deleted=True
    )
    active_user = data_fixture.create_user(
        email="test2@localhost", is_active=True, to_be_deleted=False
    )
    assert set(
        UserHandler().get_all_active_users_qs().values_list("id", flat=True)
    ) == {active_user.id}


@pytest.mark.django_db
def test_blacklist_refresh_token(data_fixture):
    user = data_fixture.create_user()

    UserHandler().blacklist_refresh_token("test", datetime(2021, 1, 1, 12, 00))

    tokens = BlacklistedToken.objects.all()
    assert len(tokens) == 1
    assert (
        tokens[0].hashed_token
        == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    )


@pytest.mark.django_db
def test_duplicate_blacklist_refresh_token(data_fixture):
    UserHandler().blacklist_refresh_token("test", datetime(2021, 1, 1, 12, 00))

    with pytest.raises(RefreshTokenAlreadyBlacklisted):
        UserHandler().blacklist_refresh_token("test", datetime(2021, 1, 1, 12, 00))


@pytest.mark.django_db
def test_refresh_token_is_blacklisted(data_fixture):
    assert UserHandler().refresh_token_is_blacklisted("test") is False
    UserHandler().blacklist_refresh_token("test", datetime(2021, 1, 1, 12, 00))
    assert UserHandler().refresh_token_is_blacklisted("test") is True


@pytest.mark.django_db
def test_user_handler_delete_user_log_entries_older_than(data_fixture):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    action = "SIGNED_IN"
    before_retention_period = datetime(2021, 1, 3, 23, 59, tzinfo=timezone.utc)
    after_retention_period = datetime(2021, 1, 4, 0, 1, tzinfo=timezone.utc)
    cutoff = datetime(2021, 1, 4, 0, 0, tzinfo=timezone.utc)

    entries = [
        UserLogEntry(actor=user, action=action),
        UserLogEntry(actor=user2, action=action),
        UserLogEntry(actor=user, action=action),
        UserLogEntry(actor=user2, action=action),
        UserLogEntry(actor=user, action=action),
    ]

    UserLogEntry.objects.bulk_create(entries)
    assert UserLogEntry.objects.count() == 5

    entries[0].timestamp = before_retention_period
    entries[1].timestamp = before_retention_period
    entries[2].timestamp = before_retention_period
    entries[3].timestamp = after_retention_period
    entries[4].timestamp = after_retention_period
    UserLogEntry.objects.bulk_update(entries, ["timestamp"])

    UserHandler().delete_user_log_entries_older_than(cutoff)

    assert UserLogEntry.objects.count() == 2


@pytest.mark.django_db
def test_create_email_verification_token(data_fixture):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    user2.email = user.email

    with freeze_time("2023-05-05"):
        signer = UserHandler()._get_email_verification_signer()
        token = UserHandler().create_email_verification_token(user)
        token_data = signer.loads(token)
        assert token_data["user_id"] == user.id
        assert token_data["email"] == user.email
        assert token_data["expires_at"] == "2023-05-06T00:00:00+00:00"

        token2 = UserHandler().create_email_verification_token(user2)
        token_data2 = signer.loads(token2)
        assert token_data2["user_id"] == user2.id
        assert token_data2["email"] == user2.email
        assert token_data2["expires_at"] == "2023-05-06T00:00:00+00:00"

        assert token != token2


@pytest.mark.django_db
def test_verify_email_address(data_fixture):
    user = data_fixture.create_user()
    token = UserHandler().create_email_verification_token(user)
    assert user.profile.email_verified is False

    UserHandler().verify_email_address(token)

    user.refresh_from_db()
    assert user.profile.email_verified is True


@pytest.mark.django_db
def test_verify_email_address_expired(data_fixture):
    user = data_fixture.create_user()

    with freeze_time("2023-05-05"):
        token = UserHandler().create_email_verification_token(user)

    with freeze_time("2023-05-07"), pytest.raises(InvalidVerificationToken):
        UserHandler().verify_email_address(token)


@pytest.mark.django_db
def test_verify_email_address_user_doesnt_exist(data_fixture):
    user = data_fixture.create_user()
    token = UserHandler().create_email_verification_token(user)
    user.delete()

    with pytest.raises(InvalidVerificationToken):
        UserHandler().verify_email_address(token)


@pytest.mark.django_db
def test_verify_email_address_user_different_email(data_fixture):
    user = data_fixture.create_user()
    token = UserHandler().create_email_verification_token(user)
    user.email = "newemail@example.com"
    user.save()

    with pytest.raises(InvalidVerificationToken):
        UserHandler().verify_email_address(token)


@pytest.mark.django_db
def test_verify_email_address_already_verified(data_fixture):
    user = data_fixture.create_user()
    token = UserHandler().create_email_verification_token(user)
    profile = user.profile
    profile.email_verified = True
    profile.save()

    with pytest.raises(EmailAlreadyVerified):
        UserHandler().verify_email_address(token)


@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_EMBEDDED_SHARE_HOSTNAME="http://test/")
def test_send_email_pending_verification(data_fixture, mailoutbox):
    user = data_fixture.create_user()

    with transaction.atomic():
        UserHandler().send_email_pending_verification(user)

    assert len(mailoutbox) == 1
    email = mailoutbox[0]

    assert email.subject == "Please confirm email"
    assert user.email in email.to

    html_body = email.alternatives[0][0]
    f"http://test/auth/verify-email/" in html_body


@pytest.mark.django_db
def test_send_email_pending_verification_already_verified(data_fixture):
    user = data_fixture.create_user()
    profile = user.profile
    profile.email_verified = True
    profile.save()

    with pytest.raises(EmailAlreadyVerified):
        UserHandler().send_email_pending_verification(user)


@pytest.mark.django_db
@patch("baserow.core.user.handler.share_onboarding_details_with_baserow")
def test_start_share_onboarding_details_with_baserow(mock_task, data_fixture):
    user = data_fixture.create_user()

    UserHandler().start_share_onboarding_details_with_baserow(
        user, "Marketing", "CEO", "11 - 50", "The Netherlands"
    )

    mock_task.delay.assert_called_with(
        email=user.email,
        team="Marketing",
        role="CEO",
        size="11 - 50",
        country="The Netherlands",
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_share_onboarding_details_with_baserow_valid_response(data_fixture):
    data_fixture.update_settings(instance_id="1")

    response1 = responses.add(
        responses.POST,
        "http://baserow-saas-backend:8000/api/saas/onboarding/additional-details/",
        status=204,
        match=[
            json_params_matcher(
                {
                    "email": "test@test.nl",
                    "team": "Marketing",
                    "role": "CEO",
                    "size": "11 - 50",
                    "country": "The Netherlands",
                    "instance_id": "1",
                }
            )
        ],
    )

    UserHandler().share_onboarding_details_with_baserow(
        email="test@test.nl",
        team="Marketing",
        role="CEO",
        size="11 - 50",
        country="The Netherlands",
    )

    assert response1.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_send_change_email_confirmation(data_fixture, mailoutbox):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user = data_fixture.create_user(email="test@localhost", password=valid_password)
    handler = UserHandler()

    # Test with invalid hostname
    with pytest.raises(BaseURLHostnameNotAllowed):
        handler.send_change_email_confirmation(
            user, "newemail@localhost", valid_password, "http://test.nl/change-email"
        )

    # Test with incorrect password
    with pytest.raises(InvalidPassword):
        handler.send_change_email_confirmation(
            user,
            "newemail@localhost",
            "wrongpassword",
            "http://localhost:3000/change-email",
        )

    # Test with existing email
    data_fixture.create_user(email="existing@localhost")
    with pytest.raises(UserAlreadyExist):
        handler.send_change_email_confirmation(
            user,
            "existing@localhost",
            valid_password,
            "http://localhost:3000/change-email",
        )

    # Test successful email change confirmation
    signer = handler.get_change_email_signer()
    handler.send_change_email_confirmation(
        user, "newemail@localhost", valid_password, "http://localhost:3000/change-email"
    )

    assert len(mailoutbox) == 1
    email = mailoutbox[0]

    assert email.subject == "Confirm email address change - Baserow"
    assert email.from_email == "no-reply@localhost"
    assert "newemail@localhost" in email.to

    html_body = email.alternatives[0][0]
    search_url = "http://localhost:3000/change-email/"
    start_url_index = html_body.index(search_url)

    assert start_url_index != -1

    end_url_index = html_body.index('"', start_url_index)
    token = html_body[start_url_index + len(search_url) : end_url_index]

    payload = signer.loads(token)
    assert payload["user_id"] == user.id
    assert payload["new_email"] == "newemail@localhost"


@pytest.mark.django_db(transaction=True)
def test_send_change_email_confirmation_in_different_language(data_fixture, mailoutbox):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user = data_fixture.create_user(
        email="test@localhost", password=valid_password, language="fr"
    )
    handler = UserHandler()

    handler.send_change_email_confirmation(
        user, "newemail@localhost", valid_password, "http://localhost:3000/change-email"
    )

    assert len(mailoutbox) == 1
    # The French translation for "Confirm email address change - Baserow"
    assert (
        "Confirmer le changement" in mailoutbox[0].subject
        or "Baserow" in mailoutbox[0].subject
    )


@pytest.mark.django_db(transaction=True)
def test_send_change_email_confirmation_auth_provider_disabled(data_fixture):
    from baserow.core.auth_provider.exceptions import AuthProviderDisabled

    data_fixture.create_password_provider(enabled=False)
    valid_password = "thisIsAValidPassword"
    user = data_fixture.create_user(email="test@localhost", password=valid_password)

    with pytest.raises(AuthProviderDisabled):
        UserHandler().send_change_email_confirmation(
            user,
            "newemail@localhost",
            valid_password,
            "http://localhost:3000/change-email",
        )


@pytest.mark.django_db(transaction=True)
def test_send_change_email_confirmation_without_password(data_fixture):
    from baserow.core.user.exceptions import ChangeEmailNotAllowed

    data_fixture.create_password_provider()
    # Create user without password (simulating SSO account)
    user = data_fixture.create_user(email="test@localhost")
    user.password = ""
    user.save()

    with pytest.raises(ChangeEmailNotAllowed):
        UserHandler().send_change_email_confirmation(
            user,
            "newemail@localhost",
            "dummy_password",  # Provided but user has no password
            "http://localhost:3000/change-email",
        )


@pytest.mark.django_db
def test_change_email(data_fixture):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user = data_fixture.create_user(email="test@localhost", password=valid_password)
    handler = UserHandler()

    # Test with invalid token
    with pytest.raises(BadSignature):
        handler.change_email("invalid_token")

    # Test with non-existent user
    signer = handler.get_change_email_signer()
    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps({"user_id": 9999, "new_email": "newemail@localhost"})

    with freeze_time("2020-01-01 18:00"):  # Within 12 hours
        with pytest.raises(UserNotFound):
            handler.change_email(token)

    # Test with expired token
    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps({"user_id": user.id, "new_email": "newemail@localhost"})

    with freeze_time("2020-01-02 01:01"):  # More than 12 hours later (13 hours 1 min)
        with pytest.raises(SignatureExpired):
            handler.change_email(token)

    # Test successful email change
    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps({"user_id": user.id, "new_email": "newemail@localhost"})

    with freeze_time("2020-01-01 18:00"):  # Within 12 hours
        changed_user, old_email = handler.change_email(token)

    assert changed_user.email == "newemail@localhost"
    assert changed_user.username == "newemail@localhost"
    assert old_email == "test@localhost"

    # Verify the user was updated in the database
    user.refresh_from_db()
    assert user.email == "newemail@localhost"
    assert user.username == "newemail@localhost"


@pytest.mark.django_db
def test_change_email_already_exists(data_fixture):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user = data_fixture.create_user(email="test@localhost", password=valid_password)
    data_fixture.create_user(email="existing@localhost")
    handler = UserHandler()

    signer = handler.get_change_email_signer()
    token = signer.dumps({"user_id": user.id, "new_email": "existing@localhost"})

    with pytest.raises(UserAlreadyExist):
        handler.change_email(token)

    # Verify the user's email was not changed
    user.refresh_from_db()
    assert user.email == "test@localhost"
