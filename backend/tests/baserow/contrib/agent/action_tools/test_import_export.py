from copy import deepcopy

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.models import AgentToolApproval
from baserow.contrib.integrations.core.models import SMTPIntegration
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig

INTERNAL = ImportExportConfig(
    include_permission_data=False, is_duplicate=True, exclude_sensitive_data=False
)


@pytest.fixture
def action_with_connection(data_fixture):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    integration = data_fixture.create_smtp_integration(
        application=agent, username="sender", password="mail-secret"
    )
    action = data_fixture.create_agent_action(
        agent=agent,
        name="welcome_email",
        ask_first=True,
        description="Send the welcome template to a new customer.",
    )
    service = action.service.specific
    service.integration = integration
    service.use_instance_smtp_settings = False
    service.from_email = BaserowFormulaObject.create("'sender@example.com'")
    service.save()
    return user, agent, action


@pytest.mark.django_db
def test_internal_duplicate_remaps_integration_and_preserves_action_inputs(
    data_fixture, action_with_connection
):
    user, agent, action = action_with_connection
    conversation = data_fixture.create_agent_conversation(agent=agent, user=user)
    data_fixture.create_agent_tool_approval(
        conversation=conversation, tool_name=action.name
    )
    copied = CoreHandler().duplicate_application(user, agent).specific
    [clone] = AgentActionHandler().list_actions(copied)
    assert clone.id != action.id and clone.service_id != action.service_id
    assert clone.inputs == action.inputs
    assert (clone.name, clone.description, clone.enabled, clone.ask_first) == (
        action.name,
        action.description,
        True,
        True,
    )
    assert clone.service.specific.subject == action.service.specific.subject
    assert clone.service.integration_id != action.service.integration_id
    integration = clone.service.integration.specific
    assert integration.application_id == copied.id
    assert integration.host == "smtp.example.com"
    assert integration.password == "mail-secret"
    assert not AgentToolApproval.objects.filter(
        reply__conversation__agent=copied
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "config",
    [
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=True),
        ImportExportConfig(
            include_permission_data=False,
            is_duplicate=True,
            is_template=True,
            exclude_sensitive_data=True,
        ),
    ],
)
def test_external_copy_disabled_and_redacted_without_reseeding(
    action_with_connection, config
):
    _, agent, action = action_with_connection
    app_type = AgentApplicationType()
    serialized = app_type.export_serialized(agent, config)
    exported_action = serialized["actions"][0]
    assert exported_action["service"]["subject"] is None
    assert exported_action["service"]["to_emails"] is None
    assert serialized["integrations"][0]["password"] is None
    id_mapping = {}
    copied = app_type.import_serialized(
        agent.workspace, deepcopy(serialized), config, id_mapping
    )
    [clone] = AgentActionHandler().list_actions(copied)
    assert clone.enabled is False and clone.ask_first is True
    assert clone.inputs == action.inputs
    assert clone.service.specific.subject["formula"] == ""
    assert clone.service.specific.to_emails["formula"] == ""
    assert clone.service.integration.specific.password in (None, "")
    assert id_mapping["agent_actions"][action.id] == clone.id


@pytest.mark.django_db
@pytest.mark.parametrize("mapping", ["absent", "foreign", "missing"])
def test_import_never_reuses_an_unmapped_or_foreign_integration(
    data_fixture, action_with_connection, mapping
):
    _, agent, action = action_with_connection
    target = data_fixture.create_agent_application(workspace=agent.workspace)
    serialized = deepcopy(AgentActionHandler().export_actions(agent, INTERNAL))
    integration_id = action.service.integration_id
    mapped = (
        {}
        if mapping == "absent"
        else {integration_id: integration_id if mapping == "foreign" else 99999999}
    )
    [clone] = AgentActionHandler().import_actions(
        target, serialized, {"integrations": mapped}, INTERNAL
    )
    assert clone.service.integration_id is None
    assert (
        AgentActionHandler().get_configuration_errors(clone)["integration_id"]
        == "required"
    )


@pytest.mark.django_db
def test_import_rejects_malformed_inputs_and_resolves_reserved_names(
    data_fixture, action_with_connection
):
    _, agent, action = action_with_connection
    target = data_fixture.create_agent_application(workspace=agent.workspace)
    serialized = deepcopy(AgentActionHandler().export_actions(agent, INTERNAL))
    serialized[0]["inputs"][0]["type"] = "unsupported"
    with pytest.raises(ValidationError):
        AgentActionHandler().import_actions(
            target, serialized, {"integrations": {}}, INTERNAL
        )
    serialized[0]["inputs"] = action.inputs
    serialized[0]["name"] = "web_search"
    [clone] = AgentActionHandler().import_actions(
        target, serialized, {"integrations": {}}, INTERNAL
    )
    assert clone.name == "web_search_2"


@pytest.mark.django_db
def test_agent_supports_smtp_integrations_only(data_fixture):
    from baserow.core.integrations.handler import IntegrationHandler
    from baserow.core.integrations.registries import integration_type_registry

    agent = data_fixture.create_agent_application()
    supported = AgentApplicationType().supports_integration_type
    assert supported(integration_type_registry.get("smtp"))
    assert not supported(integration_type_registry.get("local_baserow"))
    source = data_fixture.create_smtp_integration()
    config = ImportExportConfig(
        include_permission_data=False, exclude_sensitive_data=False
    )
    exported = IntegrationHandler().export_integration(source, config)
    imported = IntegrationHandler().import_integration(
        agent, exported, {}, import_export_config=config
    )
    assert SMTPIntegration.objects.filter(id=imported.id, application=agent).exists()
