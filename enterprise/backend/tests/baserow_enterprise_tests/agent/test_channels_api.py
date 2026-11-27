from collections.abc import Callable, Iterator
from typing import Any

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from baserow.contrib.agent.models import AgentApplication
from baserow.core.action.signals import action_done
from baserow_enterprise.agent.models import PublicChatAgentChannel
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_premium.license.cache import invalidate_cached_instance_wide_licenses
from baserow_premium.license.models import License
from tests.baserow.contrib.agent.conftest import (  # noqa: F401
    api_user,
    configured_agent,
)


def channels_url(agent: AgentApplication, channel_id: int | None = None) -> str:
    if channel_id is None:
        return reverse("api:agent:channels:list", kwargs={"agent_id": agent.id})
    return reverse(
        "api:agent:channels:item",
        kwargs={"agent_id": agent.id, "channel_id": channel_id},
    )


def visitor_info(api_client: APIClient, slug: str) -> Response:
    return api_client.get(
        reverse("api:enterprise:agent_public_chat:info", kwargs={"slug": slug})
    )


@pytest.fixture
def agent(configured_agent, api_user, enable_enterprise) -> AgentApplication:  # noqa: F811
    return configured_agent(user=api_user)


@pytest.fixture
def create_chat(api_client, agent) -> Callable[..., dict[str, Any]]:
    def create(**values) -> dict[str, Any]:
        response = api_client.post(
            channels_url(agent), {"type": "public_chat", **values}
        )
        assert response.status_code == 200, response.json()
        return response.json()

    return create


@pytest.fixture
def actions() -> Iterator[list[tuple[str, dict]]]:
    done = []

    def record(sender, action_params, **kwargs) -> None:
        done.append((sender.type, action_params))

    action_done.connect(record, weak=False)
    yield done
    action_done.disconnect(record)


@pytest.mark.django_db
def test_a_builder_creates_lists_changes_and_deletes_a_public_chat(
    api_client, agent, create_chat
):
    created = create_chat(title="Support", password="opensesame")
    chat = PublicChatAgentChannel.objects.get()
    expected = {
        "id": chat.id,
        "type": "public_chat",
        "enabled": True,
        "slug": chat.slug,
        "has_password": True,
        "title": "Support",
        "welcome_text": "",
        "accent_color": "",
        "background": "gradient",
        "background_color": "",
    }

    assert created == expected
    assert api_client.get(channels_url(agent)).json() == [expected]
    changed = api_client.patch(
        channels_url(agent, chat.id), {"enabled": False, "welcome_text": "Hi"}
    )
    assert changed.json() == {**expected, "enabled": False, "welcome_text": "Hi"}
    assert chat.check_password("opensesame")
    assert api_client.delete(channels_url(agent, chat.id)).status_code == 204
    assert api_client.get(channels_url(agent)).json() == []


@pytest.mark.django_db
def test_a_builder_changes_the_appearance(api_client, agent, create_chat):
    appearance = {
        "accent_color": "#FF6600",
        "background": "plain",
        "background_color": "#F0F0F0",
    }

    changed = api_client.patch(
        channels_url(agent, create_chat()["id"]), appearance, format="json"
    ).json()

    assert {name: changed[name] for name in appearance} == {
        **appearance,
        "accent_color": "#ff6600",
        "background_color": "#f0f0f0",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values",
    [
        {"accent_color": "red"},
        {"background_color": "#12345"},
        {"background": "video"},
    ],
)
def test_an_invalid_appearance_is_refused(api_client, agent, create_chat, values):
    response = api_client.patch(
        channels_url(agent, create_chat()["id"]), values, format="json"
    )

    assert (response.status_code, response.json()["error"]) == (
        400,
        "ERROR_REQUEST_BODY_VALIDATION",
    )


@pytest.mark.django_db
def test_an_empty_password_removes_it_and_a_short_one_is_refused(
    api_client, agent, create_chat
):
    url = channels_url(agent, create_chat(password="opensesame")["id"])

    short = api_client.patch(url, {"password": "1234567"})
    removed = api_client.patch(url, {"password": ""})

    assert (short.status_code, short.json()["error"]) == (
        400,
        "ERROR_REQUEST_BODY_VALIDATION",
    )
    assert removed.json()["has_password"] is False
    assert PublicChatAgentChannel.objects.get().password == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "password,near_miss", [("  open sesame  ", "open sesame"), (" " * 8, " " * 9)]
)
def test_a_password_is_taken_exactly_as_typed(
    api_client, agent, create_chat, password, near_miss
):
    chat = create_chat()

    changed = api_client.patch(channels_url(agent, chat["id"]), {"password": password})

    auth_url = reverse(
        "api:enterprise:agent_public_chat:auth", kwargs={"slug": chat["slug"]}
    )
    assert changed.json()["has_password"] is True
    for typed, status_code in ((password, 200), (near_miss, 401)):
        response = api_client.post(auth_url, {"password": typed}, format="json")
        assert response.status_code == status_code


@pytest.mark.django_db
def test_a_locked_type_is_refused_but_its_chat_switches_off_and_deletes(
    api_client, agent, create_chat
):
    url = channels_url(agent, create_chat()["id"])
    unknown = api_client.post(channels_url(agent), {"type": "carrier_pigeon"})
    License.objects.all().delete()
    invalidate_cached_instance_wide_licenses()

    refused = [
        unknown,
        api_client.post(channels_url(agent), {"type": "public_chat"}),
        api_client.patch(url, {"title": "New"}),
    ]
    switched_off = api_client.patch(url, {"enabled": False})
    deleted = api_client.delete(url)

    assert [(r.status_code, r.json()["error"]) for r in refused] == [
        (400, "ERROR_AGENT_CHANNEL_TYPE_NOT_AVAILABLE")
    ] * 3
    assert (switched_off.json()["enabled"], deleted.status_code) == (False, 204)


@pytest.mark.django_db
def test_a_restored_chat_answers_visitors_again_with_the_same_link(
    api_client, agent, create_chat
):
    chat = create_chat()

    api_client.delete(channels_url(agent, chat["id"]))
    trashed = visitor_info(api_client, chat["slug"])
    restored = api_client.patch(
        reverse("api:trash:restore"),
        {"trash_item_type": "agent_channel", "trash_item_id": chat["id"]},
    )

    assert (trashed.status_code, restored.status_code) == (404, 204)
    assert visitor_info(api_client, chat["slug"]).status_code == 200
    assert api_client.get(channels_url(agent)).json() == [chat]


@pytest.mark.django_db
def test_each_write_registers_its_action_without_the_password(
    api_client, agent, create_chat, actions
):
    channel_id = create_chat(title="Support", password="opensesame")["id"]
    url = channels_url(agent, channel_id)

    api_client.patch(url, {"title": "Support", "password": "anothersecret"})
    api_client.patch(url, {"title": "Support", "enabled": True})
    api_client.delete(url)

    params = {
        "agent_id": agent.id,
        "channel_id": channel_id,
        "channel_type": "public_chat",
    }
    assert actions == [
        ("create_agent_channel", params),
        ("update_agent_channel", {**params, "changed_fields": ["password"]}),
        ("delete_agent_channel", params),
    ]


@pytest.mark.django_db
def test_a_channel_of_another_agent_is_not_found(
    api_client,
    agent,
    configured_agent,  # noqa: F811
):
    other = PublicChatAgentChannel.objects.create(
        agent=configured_agent(workspace=agent.workspace)
    )

    responses = [
        api_client.patch(channels_url(agent, other.id), {"enabled": False}),
        api_client.delete(channels_url(agent, other.id)),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [
        (404, "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST")
    ] * 2


@pytest.mark.django_db
def test_an_outsider_cannot_tell_an_existing_channel_from_a_missing_one(
    api_client, data_fixture, agent, create_chat
):
    url = channels_url(agent, create_chat()["id"])
    _, token = data_fixture.create_user_and_token()
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")

    responses = [
        api_client.patch(url, {"password": "x"}),
        api_client.patch(channels_url(agent, 0), {"enabled": False}),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [
        (401, "PERMISSION_DENIED")
    ] * 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,allowed",
    [
        (None, False),
        ("NO_ACCESS", False),
        ("VIEWER", False),
        ("EDITOR", False),
        ("BUILDER", True),
        ("ADMIN", True),
    ],
    ids=["non-member", "no-access", "viewer", "editor", "builder", "admin"],
)
def test_only_builders_list_add_change_and_delete_channels(
    api_client,
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    role_uid,
    allowed,
):
    admin = enterprise_data_fixture.create_user()
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[user] if role_uid else []
    )
    if role_uid:
        RoleAssignmentHandler().assign_role(
            user, workspace, Role.objects.get(uid=role_uid)
        )
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    chat = PublicChatAgentChannel.objects.create(agent=agent)
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")
    api_client.default_format = "json"

    statuses = [
        api_client.get(channels_url(agent)).status_code,
        api_client.post(channels_url(agent), {"type": "public_chat"}).status_code,
        api_client.patch(channels_url(agent, chat.id), {"enabled": False}).status_code,
        api_client.delete(channels_url(agent, chat.id)).status_code,
    ]

    assert statuses == ([200, 200, 200, 204] if allowed else [401] * 4)
    assert PublicChatAgentChannel.objects_and_trash.count() == (2 if allowed else 1)


@pytest.mark.django_db
def test_listing_five_channels_costs_as_many_queries_as_one(
    api_client, agent, create_chat
):
    create_chat()
    api_client.get(channels_url(agent))
    with CaptureQueriesContext(connection) as one:
        api_client.get(channels_url(agent))
    for _ in range(4):
        create_chat()
    with CaptureQueriesContext(connection) as five:
        response = api_client.get(channels_url(agent))

    assert (len(response.json()), len(five.captured_queries)) == (
        5,
        len(one.captured_queries),
    )
