import json
from collections.abc import Callable
from typing import Any

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.models import AgentApplication, AgentConversation
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.agent.models import (
    PublicChatAgentChannel,
    WebsiteWidgetAgentChannel,
)
from baserow_enterprise_tests.agent.test_channels_api import channels_url
from baserow_enterprise_tests.agent.test_public_chat import start, url
from baserow_premium.license.cache import invalidate_cached_instance_wide_licenses
from baserow_premium.license.models import License
from tests.baserow.contrib.agent.conftest import (  # noqa: F401
    api_user,
    configured_agent,
)


def get_script(api_client: APIClient, slug: str) -> Response:
    return api_client.get(url(slug, "widget_script"))


def script_config(response: Response) -> dict[str, Any]:
    script = response.content.decode()
    line = next(line for line in script.splitlines() if "var config = " in line)
    return json.loads(line.split("var config = ", 1)[1])


@pytest.fixture
def agent(configured_agent, api_user, enable_enterprise) -> AgentApplication:  # noqa: F811
    return configured_agent(user=api_user, name="Acme agent")


@pytest.fixture
def create_widget(agent) -> Callable[..., WebsiteWidgetAgentChannel]:
    def create(**values) -> WebsiteWidgetAgentChannel:
        return WebsiteWidgetAgentChannel.objects.create(agent=agent, **values)

    return create


@pytest.mark.django_db
def test_a_builder_adds_a_website_widget_without_a_password_or_background(
    api_client, agent
):
    created = api_client.post(
        channels_url(agent),
        {"type": "website_widget", "title": "Support", "password": "opensesame"},
    )
    changed = api_client.patch(
        channels_url(agent, created.json()["id"]),
        {"button_text": "  Ask us  ", "password": "opensesame", "background": "plain"},
    )

    widget = WebsiteWidgetAgentChannel.objects.get()
    assert created.status_code == 200
    assert changed.json() == {
        "id": widget.id,
        "type": "website_widget",
        "enabled": True,
        "slug": widget.slug,
        "title": "Support",
        "welcome_text": "",
        "accent_color": "",
        "button_text": "Ask us",
        "button_position": "bottom_right",
    }
    assert (widget.password, widget.background) == ("", "gradient")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values",
    [{"button_text": "x" * 61}, {"button_position": "top_left"}],
)
def test_an_invalid_button_is_refused(api_client, agent, values):
    response = api_client.post(
        channels_url(agent), {"type": "website_widget", **values}
    )

    assert (response.status_code, response.json()["error"]) == (
        400,
        "ERROR_REQUEST_BODY_VALIDATION",
    )


@pytest.mark.django_db
def test_a_blank_button_text_leaves_only_the_icon(api_client, agent):
    created = api_client.post(
        channels_url(agent), {"type": "website_widget", "button_text": "  "}
    )

    script = get_script(api_client, created.json()["slug"])
    assert created.json()["button_text"] == ""
    assert script_config(script)["text"] == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "accent_color,color,text_color",
    [
        ("", "#202128", "#ffffff"),
        ("#1f2937", "#1f2937", "#ffffff"),
        ("#ffcc00", "#ffcc00", "#000000"),
    ],
)
def test_the_script_carries_the_widget_settings_and_is_cached(
    api_client, create_widget, settings, accent_color, color, text_color
):
    widget = create_widget(
        accent_color=accent_color,
        button_text="Ask </script> us",
        button_position="bottom_left",
    )

    response = get_script(api_client, widget.slug)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/javascript; charset=utf-8"
    assert response["Cache-Control"] == "public, max-age=300"
    assert "</script>" not in response.content.decode()
    assert script_config(response) == {
        "id": f"baserow-agent-widget-{widget.slug}",
        "chatUrl": f"{settings.BASEROW_EMBEDDED_SHARE_URL}/public/agent-chat/"
        f"{widget.slug}?embedded=true",
        "color": color,
        "textColor": text_color,
        "position": "bottom_left",
        "text": "Ask </script> us",
        "title": "Acme agent",
    }


def public_chat_link(agent: AgentApplication, widget: WebsiteWidgetAgentChannel) -> str:
    return PublicChatAgentChannel.objects.create(agent=agent).slug


def unknown_link(agent: AgentApplication, widget: WebsiteWidgetAgentChannel) -> str:
    return "unknown"


def switched_off(agent: AgentApplication, widget: WebsiteWidgetAgentChannel) -> str:
    WebsiteWidgetAgentChannel.objects.filter(id=widget.id).update(enabled=False)
    return widget.slug


def trashed(agent: AgentApplication, widget: WebsiteWidgetAgentChannel) -> str:
    WebsiteWidgetAgentChannel.objects.filter(id=widget.id).update(trashed=True)
    return widget.slug


def unlicensed(agent: AgentApplication, widget: WebsiteWidgetAgentChannel) -> str:
    License.objects.all().delete()
    invalidate_cached_instance_wide_licenses()
    return widget.slug


@pytest.mark.django_db
@pytest.mark.parametrize(
    "unavailable", [public_chat_link, unknown_link, switched_off, trashed, unlicensed]
)
def test_only_a_usable_website_widget_serves_a_script(
    api_client, agent, create_widget, unavailable
):
    slug = unavailable(agent, create_widget())

    response = get_script(api_client, slug)

    assert (response.status_code, response.json()["error"]) == (
        404,
        "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST",
    )


@pytest.mark.django_db
def test_a_visitor_talks_to_the_agent_through_the_widget(api_client, create_widget):
    widget = create_widget(title="Support")

    info = api_client.get(url(widget.slug, "info"))
    started = start(api_client, widget)

    assert (info.json()["title"], info.json()["has_access"]) == ("Support", True)
    assert started.status_code == 200, started.json()
    assert AgentConversation.objects.get().channel_id == widget.id


@pytest.mark.django_db
def test_a_copied_website_widget_keeps_its_button_and_drops_what_the_api_would_refuse(
    data_fixture, agent, create_widget
):
    widget = create_widget(
        title="Support", button_text="Ask us", button_position="bottom_left"
    )
    application_type = AgentApplicationType()
    config = ImportExportConfig(include_permission_data=False, is_duplicate=True)
    serialized = json.loads(
        json.dumps(application_type.export_serialized(agent, config))
    )
    workspace = data_fixture.create_workspace()

    copy = application_type.import_serialized(workspace, serialized, config, {})
    serialized["channels"][0].update(button_text="x" * 61, button_position="top")
    refused = application_type.import_serialized(workspace, serialized, config, {})

    copies = [
        WebsiteWidgetAgentChannel.objects.get(agent=agent) for agent in (copy, refused)
    ]
    assert [
        (c.enabled, c.title, c.password, c.button_text, c.button_position)
        for c in copies
    ] == [
        (False, "Support", "", "Ask us", "bottom_left"),
        (False, "Support", "", "Chat with us", "bottom_right"),
    ]
    assert widget.slug not in {c.slug for c in copies}
