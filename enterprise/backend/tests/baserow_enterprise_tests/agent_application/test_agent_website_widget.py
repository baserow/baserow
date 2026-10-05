import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.channels.website import (
    WebsiteWidgetAgentChatChannelType,
)
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import AgentChatChannel

from .test_agent_runner import register_runner_test_model_type


@pytest.fixture
def widget_channel(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Docs")
        .specific
    )
    application.active = True
    application.save(update_fields=["active"])
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent, ai_generative_ai_type="agent_runner_test", ai_generative_ai_model="m"
    )
    channel_type = WebsiteWidgetAgentChatChannelType()
    channel = AgentChatChannel.objects.create(
        application=application,
        type=channel_type.type,
        name="Site",
        config=channel_type.prepare_config(
            {
                "title": "Ask us",
                "button_color": "#FF8800",
                "button_position": "bottom-left",
                "button_text": "  Need help?  ",
            }
        ),
    )
    return user, application, agent, channel


@pytest.mark.django_db
def test_widget_config_defaults_validation_and_no_password(widget_channel):
    user, application, agent, channel = widget_channel
    channel_type = WebsiteWidgetAgentChatChannelType()

    assert channel.config["slug"]
    assert channel.config["password"] == ""
    assert channel.config["button_color"] == "#ff8800"
    assert channel.config["button_position"] == "bottom-left"
    assert channel.config["button_text"] == "Need help?"

    defaults = channel_type.prepare_config({})
    assert defaults["button_color"] == "#5190ef"
    assert defaults["button_position"] == "bottom-right"
    assert defaults["button_text"] == "Chat with us"

    # A password never sticks: a widget can't ask for one.
    updated = channel_type.prepare_config(
        {"password": "secret", "button_text": "Hi"}, existing_config=channel.config
    )
    assert updated["password"] == ""
    assert updated["slug"] == channel.config["slug"]
    assert updated["button_color"] == "#ff8800"
    assert not channel_type.has_password(channel)

    with pytest.raises(DRFValidationError):
        channel_type.prepare_config({"button_color": "red"})
    with pytest.raises(DRFValidationError):
        channel_type.prepare_config({"button_position": "middle"})

    public = channel_type.get_public_config(channel)
    assert public["button_text"] == "Need help?"
    assert public["embed_script_url"].endswith(
        f"/api/agent_application/public/widget/{channel.config['slug']}.js"
    )
    assert "password" not in public


@pytest.mark.django_db
def test_widget_channel_is_reachable_through_the_public_chat(
    api_client, widget_channel
):
    user, application, agent, channel = widget_channel

    assert AgentChatHandler().get_public_web_channel(channel.config["slug"]) == (
        channel
    )
    response = api_client.get(
        f"/api/agent_application/public/chat/{channel.config['slug']}/"
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Ask us"
    assert response.json()["has_password"] is False


@pytest.mark.django_db
def test_widget_script_bakes_in_the_settings(api_client, widget_channel):
    user, application, agent, channel = widget_channel
    slug = channel.config["slug"]

    response = api_client.get(f"/api/agent_application/public/widget/{slug}.js")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert response["Cache-Control"] == "no-cache"
    script = response.content.decode()
    assert "__WIDGET_CONFIG__" not in script
    assert f'"chat_url": "http://localhost:3000/agent-chat/{slug}"' in script
    assert '"color": "#ff8800"' in script
    assert '"position": "bottom-left"' in script
    assert '"text": "Need help?"' in script
    assert '"title": "Ask us"' in script

    # A disabled channel serves nothing, like the public page.
    channel.enabled = False
    channel.save(update_fields=["enabled"])
    response = api_client.get(f"/api/agent_application/public/widget/{slug}.js")
    assert response.status_code == 404


@pytest.mark.django_db
def test_plain_web_channel_serves_no_widget_script(api_client, data_fixture):
    from baserow_enterprise.agent_application.channels.web import (
        WebAgentChatChannelType,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Docs")
        .specific
    )
    application.active = True
    application.save(update_fields=["active"])
    channel_type = WebAgentChatChannelType()
    channel = AgentChatChannel.objects.create(
        application=application,
        type=channel_type.type,
        config=channel_type.prepare_config({}),
    )

    response = api_client.get(
        f"/api/agent_application/public/widget/{channel.config['slug']}.js"
    )
    assert response.status_code == 404
