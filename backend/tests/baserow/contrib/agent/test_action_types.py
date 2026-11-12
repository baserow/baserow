from unittest.mock import patch

from django.core.mail.backends.locmem import EmailBackend

import pytest

from baserow.contrib.agent.action_tools.action_types import SMTPEmailAgentActionType
from baserow.core.formula.types import BaserowFormulaObject


@pytest.fixture
def configured_email(data_fixture):
    action = data_fixture.create_agent_action()
    service = action.service.specific
    service.integration = data_fixture.create_smtp_integration(application=action.agent)
    service.use_instance_smtp_settings = False
    service.from_email = BaserowFormulaObject.create("sender@example.com", mode="raw")
    service.save()
    action.service = service
    return action


@pytest.mark.django_db
def test_renamed_input_keeps_binding_and_deleted_input_marks_action_unconfigured(
    configured_email,
):
    action = configured_email
    adapter = SMTPEmailAgentActionType()
    assert adapter.get_configuration_errors(action) == {}
    action.inputs[0]["name"] = "recipient"
    preview = adapter.get_preview(
        action,
        {"recipient": "alice@example.com", "subject": "Hello", "body": "Report"},
    )
    assert preview["values"]["to_emails"] == ["alice@example.com"]
    action.inputs.pop(0)
    assert adapter.get_configuration_errors(action) == {"to_emails": "invalid"}


@pytest.mark.django_db
def test_readiness_does_not_resolve_formulas_or_contact_smtp(configured_email):
    with patch.object(
        SMTPEmailAgentActionType().service_type, "resolve_service_formulas"
    ) as resolve:
        assert (
            SMTPEmailAgentActionType().get_configuration_errors(configured_email) == {}
        )
    resolve.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "argument", [" '{path}'", "'{path}' ", "('{path}')", '"{path}"']
)
def test_input_reference_validation_accepts_decorated_literals(
    configured_email, argument
):
    action = configured_email
    path = f"tool_input.{action.inputs[0]['id']}"
    action.service.to_emails = BaserowFormulaObject.create(
        f"get({argument.format(path=path)})", mode="advanced"
    )
    adapter = SMTPEmailAgentActionType()
    assert adapter.get_configuration_errors(action) == {}
    action.inputs.pop(0)
    assert adapter.get_configuration_errors(action) == {"to_emails": "invalid"}


@pytest.mark.django_db
def test_preview_is_bounded_but_delivery_retains_full_payload(
    configured_email, mailoutbox
):
    action = configured_email
    body = "message " * 1000
    adapter = SMTPEmailAgentActionType()
    arguments = {"to_email": "alice@example.com", "subject": "Hello", "body": body}
    preview = adapter.get_preview(action, arguments)
    assert preview["truncated"] is True
    assert len(preview["values"]["body"]) == 1000
    with patch(
        "baserow.contrib.integrations.core.service_types.get_connection",
        return_value=EmailBackend(),
    ):
        adapter.dispatch(action, arguments)
    assert mailoutbox[0].body == body
