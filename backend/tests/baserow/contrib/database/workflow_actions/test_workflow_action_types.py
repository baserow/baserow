from types import SimpleNamespace
from unittest.mock import patch

import pytest

from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionInvalidIntegration,
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
from baserow.core.services.registries import service_type_registry


def test_every_type_is_registered():
    types = {t.type for t in database_workflow_action_type_registry.get_all()}

    assert types == {
        "local_baserow_create_row",
        "local_baserow_update_row",
        "local_baserow_delete_row",
        "open_url",
        "http_request",
        "smtp_email",
        "slack_write_message",
        "start_workflow",
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


def test_is_external_follows_the_backing_service_type():
    for action_type in database_workflow_action_type_registry.get_all():
        service_type_name = getattr(action_type, "service_type", None)
        if service_type_name is None:
            continue

        service_type = service_type_registry.get(service_type_name)
        assert action_type.is_external is service_type.is_external, action_type.type


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
def test_preparing_values_refuses_an_integration_the_type_does_not_allow(data_fixture):
    # An integration's `authorized_user` would run every click as someone
    # else, so a type has to say which integration types it accepts. A row
    # action accepts none.
    user = data_fixture.create_user()
    victim = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    victim_integration = data_fixture.create_local_baserow_integration(
        application=table.database, authorized_user=victim
    )
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction,
        field=data_fixture.create_button_field(table=table),
    )
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    with pytest.raises(WorkflowActionInvalidIntegration):
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
        # The guard reads the field the dispatch is for from the context.
        action_type.dispatch(action, SimpleNamespace(field=action.field))


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
        user,
        action_type,
        button_field,
        service={"use_instance_smtp_settings": True},
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
