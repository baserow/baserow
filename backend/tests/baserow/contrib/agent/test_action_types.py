from unittest.mock import patch

from django.core.mail.backends.locmem import EmailBackend
from django.test.utils import override_settings

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
    arguments = {"recipient": "alice@example.com", "subject": "Hello", "body": "Report"}
    preview = adapter.get_preview(action, adapter.prepare(action, arguments), arguments)
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


@override_settings(
    CELERY_EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    EMAIL_HOST="localhost",
    INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS=True,
)
def test_the_starter_only_selects_an_instance_server_that_delivers():
    service = SMTPEmailAgentActionType().get_defaults()["service"]

    assert service["use_instance_smtp_settings"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula",
    ["minus('abc', 1)", "(" * 1000 + "'a'" + ")" * 1000],
    ids=["refused argument", "nested too deeply"],
)
def test_a_stored_formula_that_cannot_be_checked_only_marks_its_field(
    configured_email, formula
):
    action = configured_email
    action.service.body = BaserowFormulaObject.create(formula, mode="advanced")

    errors = SMTPEmailAgentActionType().get_configuration_errors(action)

    assert errors == {"body": "invalid"}


@pytest.mark.django_db
def test_a_preview_shows_all_of_a_large_request_that_is_delivered(
    configured_email, mailoutbox
):
    action = configured_email
    body = "message " * 10000
    adapter = SMTPEmailAgentActionType()
    arguments = {"to_email": "alice@example.com", "subject": "Hello", "body": body}
    resolved_values = adapter.prepare(action, arguments)
    preview = adapter.get_preview(action, resolved_values, arguments)
    assert "truncated" not in preview
    assert preview["values"]["body"] == body
    with patch(
        "baserow.contrib.integrations.core.service_types.get_connection",
        return_value=EmailBackend(),
    ):
        adapter.dispatch(action, resolved_values)
    assert mailoutbox[0].body == body
