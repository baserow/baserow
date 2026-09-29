from unittest.mock import patch

import pytest

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionInvalidIntegration,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.exceptions import PermissionException

SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"


def _instance_can_send(settings):
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = SMTP_BACKEND
    settings.EMAIL_HOST = "smtp.example.com"


def _instance_turned_off(settings):
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = False
    settings.CELERY_EMAIL_BACKEND = SMTP_BACKEND


def _button(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    return data_fixture.create_button_field(table=table)


def _email_type():
    return database_workflow_action_type_registry.get("smtp_email")


def _create(user, button_field, **service):
    return DatabaseWorkflowActionService().create_workflow_action(
        user,
        _email_type(),
        button_field,
        service={"to_emails": "'to@example.com'", **service},
    )


def test_the_email_action_accepts_smtp_integrations():
    assert _email_type().allowed_integration_types == ["smtp"]


@pytest.mark.django_db
def test_the_email_action_is_offered_where_the_instance_cannot_send(
    data_fixture, settings
):
    _instance_turned_off(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)

    assert _email_type().is_deactivated(button_field.table.database.workspace) is False


@pytest.mark.django_db
def test_an_email_action_attaches_an_smtp_integration_of_its_own_database(
    data_fixture, settings
):
    _instance_turned_off(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    smtp = data_fixture.create_smtp_integration(
        application=button_field.table.database, user=user
    )

    action = _create(
        user,
        button_field,
        integration_id=smtp.id,
        from_email="'from@example.com'",
    )

    service = action.service.specific
    assert service.integration_id == smtp.id
    assert service.use_instance_smtp_settings is False


@pytest.mark.django_db
def test_an_email_action_refuses_an_smtp_integration_of_another_database(
    data_fixture, settings
):
    _instance_turned_off(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    other = data_fixture.create_database_application(
        workspace=button_field.table.database.workspace
    )
    smtp = data_fixture.create_smtp_integration(application=other, user=user)

    with pytest.raises(WorkflowActionInvalidIntegration):
        _create(user, button_field, integration_id=smtp.id)


@pytest.mark.django_db
def test_an_email_action_refuses_a_slack_bot(data_fixture, settings):
    _instance_turned_off(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = data_fixture.create_slack_bot_integration(
        application=button_field.table.database, user=user
    )

    with pytest.raises(WorkflowActionInvalidIntegration):
        _create(user, button_field, integration_id=bot.id)


@pytest.mark.django_db
def test_an_email_action_refuses_an_smtp_integration_the_user_cannot_read(
    data_fixture, settings
):
    _instance_turned_off(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    smtp = data_fixture.create_smtp_integration(
        application=button_field.table.database, user=user
    )
    refused = PermissionException("cannot read")

    # Asked of the type directly: through the service, its own permission
    # check would be the one refused.
    with patch(
        "baserow.contrib.database.workflow_actions.workflow_action_types"
        ".CoreHandler.check_permissions",
        side_effect=refused,
    ):
        with pytest.raises(PermissionException) as raised:
            _email_type().prepare_values(
                {"service": {"integration_id": smtp.id}, "field": button_field},
                user,
                None,
            )

    assert raised.value is refused


@pytest.mark.django_db
def test_choosing_the_instance_drops_the_integration(data_fixture, settings):
    _instance_can_send(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    smtp = data_fixture.create_smtp_integration(
        application=button_field.table.database, user=user
    )
    action = _create(
        user,
        button_field,
        use_instance_smtp_settings=False,
        integration_id=smtp.id,
        from_email="'from@example.com'",
    )

    action = (
        DatabaseWorkflowActionService()
        .update_workflow_action(
            user, action, service={"use_instance_smtp_settings": True}
        )
        .workflow_action
    )

    service = action.service.specific
    assert service.use_instance_smtp_settings is True
    assert service.integration_id is None


@pytest.mark.django_db
def test_an_edit_while_the_instance_is_off_keeps_the_instance_choice(
    data_fixture, settings
):
    """
    The service type drops the instance while it cannot send. An edit that
    does not touch the choice must not leave the action with neither the
    instance nor an integration once sending is back.
    """

    _instance_can_send(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    action = _create(user, button_field, use_instance_smtp_settings=True)

    _instance_turned_off(settings)
    action = (
        DatabaseWorkflowActionService()
        .update_workflow_action(user, action, service={"subject": "'Again'"})
        .workflow_action
    )

    service = action.service.specific
    assert service.subject["formula"] == "'Again'"
    assert service.use_instance_smtp_settings is True
    assert service.integration_id is None


@pytest.mark.django_db
def test_a_click_sends_through_the_integration(data_fixture, settings):
    _instance_turned_off(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    smtp = data_fixture.create_smtp_integration(
        application=button_field.table.database,
        user=user,
        host="mail.example.org",
        port=2525,
        username="mailer",
        password="secret",  # nosec B106
    )
    _create(
        user,
        button_field,
        integration_id=smtp.id,
        from_email="'from@example.com'",
        subject="'Hi'",
        body="'Body'",
    )
    row = button_field.table.get_model().objects.create()

    with (
        patch(
            "baserow.contrib.integrations.core.service_types.get_connection"
        ) as get_connection,
        patch(
            "baserow.contrib.integrations.core.service_types.EmailMultiAlternatives"
        ) as message,
    ):
        message.return_value.send.return_value = 1
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    kwargs = get_connection.call_args.kwargs
    assert kwargs["host"] == "mail.example.org"
    assert kwargs["port"] == 2525
    assert kwargs["username"] == "mailer"
    assert kwargs["password"] == "secret"  # nosec B105
    message.return_value.send.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "backend,allowed,words",
    [
        (SMTP_BACKEND, False, "turned off"),
        (CONSOLE_BACKEND, True, "no SMTP server"),
    ],
)
def test_a_click_on_an_instance_action_the_instance_cannot_send_is_refused(
    data_fixture, settings, backend, allowed, words
):
    """
    Refused before anything runs. A console backend would otherwise report the
    message as sent.
    """

    _instance_can_send(settings)
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    _create(user, button_field, use_instance_smtp_settings=True)
    row = button_field.table.get_model().objects.create()

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = allowed
    settings.CELERY_EMAIL_BACKEND = backend
    with patch(
        "baserow.contrib.integrations.core.service_types.EmailMultiAlternatives"
    ) as message:
        with pytest.raises(WorkflowActionDispatchError) as raised:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert words in str(raised.value)
    assert "SMTP integration" in str(raised.value)
    message.assert_not_called()


@pytest.mark.django_db
def test_a_backend_whose_path_merely_contains_a_local_one_still_sends(
    data_fixture, settings
):
    _instance_can_send(settings)
    settings.CELERY_EMAIL_BACKEND = "myapp.console_relay.EmailBackend"
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    action = _create(user, button_field, use_instance_smtp_settings=True)

    _email_type().raise_if_misconfigured(action)
