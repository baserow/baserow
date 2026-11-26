import json

import pytest

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.core.handler import CoreHandler
from baserow.core.models import Template
from baserow.core.registries import ImportExportConfig
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow_enterprise.agent.models import PublicChatAgentChannel
from tests.baserow.contrib.agent.conftest import configured_agent  # noqa: F401
from tests.baserow.contrib.agent.test_agent_application import (
    duplicate,
    import_workspace_archive,
    restore_snapshot,
)

APPEARANCE = {
    "accent_color": "#ff6600",
    "background": "plain",
    "background_color": "#101010",
}


def install_template(data_fixture, user, agent, tmp_path, settings):
    slug = "agent-with-a-public-chat"
    template = Template.objects.filter(slug=slug).first()
    if template is None:
        template = data_fixture.create_template(slug=slug)
        settings.APPLICATION_TEMPLATES_DIR = str(tmp_path)
        serialized = AgentApplicationType().export_serialized(
            agent,
            ImportExportConfig(
                include_permission_data=False, is_duplicate=True, is_template=True
            ),
        )
        (tmp_path / f"{slug}.json").write_text(
            json.dumps({"export": [json.loads(json.dumps(serialized))]})
        )
    workspace = data_fixture.create_workspace(user=user)
    applications, _ = CoreHandler().install_template(user, workspace, template)
    return applications[0]


def install_user_template(data_fixture, user, agent):
    handler = UserTemplateHandler()
    revision = data_fixture.create_template(
        workspace=handler.copy_applications(user, [agent], name="Copy")
    )
    [application] = handler.install_template_content(
        user,
        data_fixture.create_workspace(user=user),
        revision,
        handler.serialize_template_content(revision),
    )
    return application


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "copy_agent,keeps_password",
    [
        ("duplicate", True),
        ("restore_snapshot", True),
        ("import_workspace_archive", False),
        ("install_template", False),
        ("install_user_template", False),
    ],
)
def test_a_copied_public_chat_is_switched_off_with_a_link_of_its_own(
    data_fixture,
    use_tmp_media_root,
    configured_agent,  # noqa: F811
    enable_enterprise,
    synced_roles,
    tmp_path,
    settings,
    copy_agent,
    keeps_password,
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, suggested_messages=["Where is my order?"])
    chat = PublicChatAgentChannel.objects.create(
        agent=agent,
        password=PublicChatAgentChannel.hash_password("secret"),
        title="Support",
        welcome_text="Ask me anything",
        **APPEARANCE,
    )
    copiers = {
        "duplicate": duplicate,
        "restore_snapshot": restore_snapshot,
        "import_workspace_archive": import_workspace_archive,
        "install_template": lambda *args: install_template(*args, tmp_path, settings),
        "install_user_template": install_user_template,
    }

    copies = [
        PublicChatAgentChannel.objects.get(
            agent=copiers[copy_agent](data_fixture, user, agent)
        )
        for _ in range(2)
    ]

    assert [
        (
            copy.enabled,
            copy.title,
            copy.welcome_text,
            copy.has_password and copy.check_password("secret"),
            {name: getattr(copy, name) for name in APPEARANCE},
            copy.agent.suggested_messages,
        )
        for copy in copies
    ] == [
        (
            False,
            "Support",
            "Ask me anything",
            keeps_password,
            APPEARANCE,
            ["Where is my order?"],
        )
    ] * 2
    assert len({chat.slug, *(copy.slug for copy in copies)}) == 3
    chat.refresh_from_db()
    assert (chat.enabled, chat.check_password("secret")) == (True, True)


@pytest.mark.django_db
def test_an_imported_public_chat_drops_the_appearance_the_api_would_refuse(
    data_fixture,
    configured_agent,  # noqa: F811
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    PublicChatAgentChannel.objects.create(agent=agent, **APPEARANCE)
    application_type = AgentApplicationType()
    config = ImportExportConfig(include_permission_data=False)
    serialized = json.loads(
        json.dumps(application_type.export_serialized(agent, config))
    )
    serialized["channels"][0].update(
        accent_color="red;x", background="image", font="georgia", show_powered_by=False
    )

    imported = application_type.import_serialized(
        data_fixture.create_workspace(user=user), serialized, config, {}
    )

    copy = PublicChatAgentChannel.objects.get(agent=imported)
    assert {name: getattr(copy, name) for name in APPEARANCE} == {
        "accent_color": "",
        "background": "gradient",
        "background_color": "#101010",
    }
