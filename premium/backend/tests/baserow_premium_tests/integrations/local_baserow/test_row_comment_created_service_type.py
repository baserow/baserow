from unittest.mock import Mock, patch

from django.test.utils import override_settings

import pytest

from baserow.core.services.registries import service_type_registry
from baserow_premium.integrations.local_baserow.service_types import (
    LocalBaserowRowCommentCreatedServiceType,
)
from baserow_premium.row_comments.handler import RowCommentHandler


@pytest.fixture
def commented_table(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    return user, table, rows


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_row_comment_created_notifies_listeners(premium_data_fixture, commented_table):
    user, table, rows = commented_table
    service = premium_data_fixture.create_local_baserow_row_comment_created_service(
        table=table
    )
    service_type = service_type_registry.get(
        LocalBaserowRowCommentCreatedServiceType.type
    )
    listener = Mock()
    service_type.start_listening(listener)

    try:
        message = premium_data_fixture.create_comment_message_from_plain_text(
            "Please follow this up."
        )
        comment = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)
    finally:
        service_type.stop_listening(listener)

    listener.assert_called_once()
    services, payload_callable = listener.call_args.args
    assert [s.id for s in services] == [service.id]
    payload = payload_callable(service) if callable(payload_callable) else None
    assert payload["id"] == comment.id
    assert payload["row_id"] == rows[0].id
    assert payload["table_id"] == table.id
    assert payload["user"]["id"] == user.id
    assert "Please follow this up." in str(payload["message"])


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_row_comment_created_only_notifies_matching_table(
    premium_data_fixture, commented_table
):
    user, table, rows = commented_table
    other_table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_local_baserow_row_comment_created_service(
        table=other_table
    )
    service_type = service_type_registry.get(
        LocalBaserowRowCommentCreatedServiceType.type
    )
    listener = Mock()
    service_type.start_listening(listener)

    try:
        message = premium_data_fixture.create_comment_message_from_plain_text("Hi")
        RowCommentHandler.create_comment(user, table.id, rows[0].id, message)
    finally:
        service_type.stop_listening(listener)

    listener.assert_called_once()
    services, _ = listener.call_args.args
    assert list(services) == []


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_row_comment_created_starts_automation_workflow(
    premium_data_fixture, data_fixture, commented_table
):
    from baserow.contrib.automation.workflows.constants import WorkflowState

    user, table, rows = commented_table
    workspace = table.database.workspace
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    service = premium_data_fixture.create_local_baserow_row_comment_created_service(
        table=table
    )
    data_fixture.create_automation_node(
        workflow=workflow,
        type="local_baserow_row_comment_created",
        service=service,
    )

    message = premium_data_fixture.create_comment_message_from_plain_text("Task?")
    with patch(
        "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler"
        ".async_start_workflow"
    ) as start_mock:
        RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    start_mock.assert_called_once()
