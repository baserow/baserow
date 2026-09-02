from unittest.mock import patch

import pytest

from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionTypeDeactivated,
)
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    CoreSMTPEmailWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)


def test_every_type_is_registered():
    types = {t.type for t in database_workflow_action_type_registry.get_all()}

    assert types == {
        "local_baserow_create_row",
        "local_baserow_update_row",
        "local_baserow_delete_row",
        "open_url",
        "http_request",
        "smtp_email",
    }


def test_types_map_to_their_models_and_services():
    registry = database_workflow_action_type_registry

    assert (
        registry.get("local_baserow_create_row").model_class
        is LocalBaserowCreateRowWorkflowAction
    )
    assert (
        registry.get("local_baserow_create_row").service_type
        == "local_baserow_upsert_row"
    )
    assert (
        registry.get("local_baserow_update_row").model_class
        is LocalBaserowUpdateRowWorkflowAction
    )
    assert (
        registry.get("local_baserow_update_row").service_type
        == "local_baserow_upsert_row"
    )
    assert (
        registry.get("local_baserow_delete_row").model_class
        is LocalBaserowDeleteRowWorkflowAction
    )
    assert (
        registry.get("local_baserow_delete_row").service_type
        == "local_baserow_delete_row"
    )
    assert registry.get("http_request").model_class is CoreHTTPRequestWorkflowAction
    assert registry.get("http_request").service_type == "http_request"
    assert registry.get("smtp_email").model_class is CoreSMTPEmailWorkflowAction
    assert registry.get("smtp_email").service_type == "smtp_email"


@pytest.mark.django_db
def test_preparing_values_creates_the_backing_service(data_fixture):
    user = data_fixture.create_user()
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    prepared = action_type.prepare_values({}, user)

    assert prepared["service"] is not None
    assert prepared["service"].get_type().type == "local_baserow_upsert_row"


@pytest.mark.django_db
def test_preparing_values_updates_an_existing_service(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction
    )
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    action_type.prepare_values({"service": {"table_id": table.id}}, user, action)
    action.service.refresh_from_db()

    assert action.service.specific.table_id == table.id


@pytest.mark.django_db
def test_preparing_values_never_attaches_an_integration(data_fixture):
    # `integration_id` is resolved without a permission check, so an
    # integration the caller cannot reach would run every click as its user.
    user = data_fixture.create_user()
    victim = data_fixture.create_user()
    victim_integration = data_fixture.create_local_baserow_integration(
        user=victim, authorized_user=victim
    )
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction
    )
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    action_type.prepare_values(
        {"service": {"integration_id": victim_integration.id}}, user, action
    )
    action.service.refresh_from_db()

    assert action.service.integration_id is None


@pytest.mark.django_db
def test_dispatching_refuses_a_service_carrying_an_integration(data_fixture):
    # Defence in depth for the strip above.
    victim = data_fixture.create_user()
    victim_integration = data_fixture.create_local_baserow_integration(
        user=victim, authorized_user=victim
    )
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction
    )
    service = action.service.specific
    service.integration = victim_integration
    service.save()
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        # The guard runs before the context is used.
        action_type.dispatch(action, None)


@pytest.mark.django_db
def test_open_url_action_is_frontend_only_and_has_no_service(data_fixture):
    field = data_fixture.create_button_field()
    action = DatabaseWorkflowActionHandler().create_workflow_action(
        database_workflow_action_type_registry.get("open_url"),
        field=field,
        url={"formula": "'https://example.com'", "mode": "simple"},
    )

    assert action.get_type().is_frontend_only is True
    assert action.url["formula"] == "'https://example.com'"
    assert action.target == "self"
    assert not hasattr(action, "service")


@pytest.mark.django_db
def test_email_is_refused_when_the_instance_cannot_send(data_fixture, settings):
    """
    A database action carries no integration, so without an instance SMTP
    server the email action would fail on every click. It is refused when it is
    configured instead, with a reason the editor can show.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = False
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("smtp_email")
    workspace = table.database.workspace

    assert action_type.is_deactivated(workspace) is True
    assert "SMTP" in action_type.get_deactivated_reason(workspace)

    with pytest.raises(WorkflowActionTypeDeactivated):
        DatabaseWorkflowActionService().create_workflow_action(
            user, action_type, button_field
        )


@pytest.mark.django_db
def test_email_is_refused_when_the_instance_only_prints_what_it_is_given(
    data_fixture, settings
):
    """
    Without SMTP configured, Baserow keeps a backend that writes the message
    locally and reports success. `EMAIL_HOST` is no help here: Django defaults
    it to "localhost" whether or not anything is listening.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    settings.EMAIL_HOST = "localhost"
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("smtp_email")

    assert action_type.is_deactivated(table.database.workspace) is True

    with pytest.raises(WorkflowActionTypeDeactivated):
        DatabaseWorkflowActionService().create_workflow_action(
            user, action_type, button_field
        )


@pytest.mark.django_db
def test_each_way_of_being_unable_to_send_says_which_one_it_is(data_fixture, settings):
    """
    An administrator who turned instance sending off reads that, rather than
    being told this installation has no mail server at all.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    workspace = table.database.workspace
    action_type = database_workflow_action_type_registry.get("smtp_email")

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = False
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    assert "turned off" in action_type.get_deactivated_reason(workspace)

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    assert "no SMTP server" in action_type.get_deactivated_reason(workspace)


@pytest.mark.django_db
def test_a_backend_whose_path_merely_contains_a_local_one_still_sends(
    data_fixture, settings
):
    """
    The names are matched as whole path segments. A custom backend living in a
    module such as `myapp.console_relay` sends for real, and reading its path
    as a substring would turn the email action off for that installation.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "myapp.console_relay.EmailBackend"
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    action_type = database_workflow_action_type_registry.get("smtp_email")

    assert action_type.is_deactivated(table.database.workspace) is False


@pytest.mark.django_db
def test_email_is_offered_when_the_instance_can_send(data_fixture, settings):
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "smtp.example.com"
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("smtp_email")

    assert action_type.is_deactivated(table.database.workspace) is False

    action = DatabaseWorkflowActionService().create_workflow_action(
        user, action_type, button_field
    )

    assert action.service.specific.use_instance_smtp_settings is True
    # ADR 006 section 5: a button's actions never run as an integration's user.
    assert action.service.integration_id is None


@pytest.mark.django_db
def test_an_api_client_cannot_store_an_action_that_can_never_send(
    data_fixture, settings
):
    """
    The form does not offer the choice, but the endpoint takes whatever it is
    given, and a service that sends through nothing fails on every click.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("smtp_email")

    action = DatabaseWorkflowActionService().create_workflow_action(
        user, action_type, button_field, service={"use_instance_smtp_settings": False}
    )

    assert action.service.specific.use_instance_smtp_settings is True


@pytest.mark.django_db
def test_a_deactivated_type_cannot_be_swapped_to_either(data_fixture, settings):
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = False
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    with pytest.raises(WorkflowActionTypeDeactivated):
        DatabaseWorkflowActionService().update_workflow_action(
            user, action, type="smtp_email"
        )


@pytest.mark.django_db
def test_a_click_that_may_not_dispatch_is_told_nothing_about_the_instance(
    data_fixture, settings
):
    """
    The reason names how this installation is configured, so it is for whoever
    may configure the button, not for anyone who can reach the endpoint.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    row = table.get_model().objects.create()
    action_type = database_workflow_action_type_registry.get("smtp_email")
    DatabaseWorkflowActionService().create_workflow_action(
        user, action_type, button_field
    )

    # The instance stops being able to send after the action was configured.
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

    refused = Exception("not allowed to dispatch")
    with patch(
        "baserow.core.handler.CoreHandler.check_multiple_permissions",
        side_effect=refused,
    ):
        with pytest.raises(Exception) as raised:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert raised.value is refused
