from unittest.mock import patch

import pytest
from pydantic_ai.messages import BinaryContent

from baserow.core.user_files.handler import UserFileHandler
from baserow_enterprise.agent_application.files import (
    MAX_PROMPT_FILES,
    extract_payload_files,
    load_prompt_file_parts,
)


def test_extract_payload_files_finds_nested_file_dicts():
    payload = {
        "rows": [
            {
                "id": 1,
                "Name": "Row",
                "Attachments": [
                    {"name": "abc_hash.pdf", "visible_name": "report.pdf"},
                    {"name": "def_hash.png", "visible_name": "logo.png"},
                ],
            }
        ],
        "table": {"id": 5},
    }

    found = extract_payload_files(payload)
    assert [f["name"] for f in found] == ["abc_hash.pdf", "def_hash.png"]


def test_extract_payload_files_ignores_non_file_dicts():
    payload = {"row": {"name": "not a file"}, "other": [1, "x", None]}
    assert extract_payload_files(payload) == []


def _store_file_content(user_file, content: bytes):
    from django.core.files.base import ContentFile

    from baserow.core.storage import get_default_storage

    path = UserFileHandler().user_file_path(user_file.name)
    get_default_storage().save(path, ContentFile(content))


@pytest.mark.django_db
def test_load_prompt_file_parts_inlines_text_and_wraps_binary(data_fixture, tmpdir):
    from django.test import override_settings

    with override_settings(MEDIA_ROOT=str(tmpdir)):
        text_file = data_fixture.create_user_file(
            original_name="notes.txt", mime_type="text/plain", size=11
        )
        _store_file_content(text_file, b"hello agent")

        image_file = data_fixture.create_user_file(
            original_name="logo.png", mime_type="image/png", size=4
        )
        _store_file_content(image_file, b"\x89PNG")

        parts = load_prompt_file_parts(
            [
                {"name": text_file.name, "visible_name": "notes.txt"},
                {"name": image_file.name, "visible_name": "logo.png"},
                # Unknown files are skipped silently.
                {"name": "missing_file.bin", "visible_name": "missing.bin"},
            ]
        )

    assert len(parts) == 2
    assert "hello agent" in parts[0]
    assert "notes.txt" in parts[0]
    assert isinstance(parts[1], BinaryContent)
    assert parts[1].media_type == "image/png"
    assert parts[1].data == b"\x89PNG"


@pytest.mark.django_db
def test_load_prompt_file_parts_skips_oversized_and_caps_count(data_fixture, tmpdir):
    from django.test import override_settings

    with override_settings(MEDIA_ROOT=str(tmpdir)):
        big_file = data_fixture.create_user_file(
            original_name="big.png", mime_type="image/png", size=999999999
        )

        parts = load_prompt_file_parts(
            [{"name": big_file.name, "visible_name": "big.png"}]
        )
        assert len(parts) == 1
        assert "skipped" in parts[0]

        many = []
        for i in range(MAX_PROMPT_FILES + 2):
            user_file = data_fixture.create_user_file(
                original_name=f"f{i}.txt", mime_type="text/plain", size=1
            )
            _store_file_content(user_file, b"x")
            many.append({"name": user_file.name, "visible_name": f"f{i}.txt"})

        parts = load_prompt_file_parts(many)
        # The cap plus one trailing note about the skipped remainder.
        assert len(parts) == MAX_PROMPT_FILES + 1
        assert "skipped" in parts[-1]


@pytest.mark.django_db
def test_runner_injects_attachments_and_trigger_payload_files(data_fixture, tmpdir):
    from django.test import override_settings

    from baserow.core.handler import CoreHandler
    from baserow_enterprise.agent_application.handler import AgentApplicationHandler
    from baserow_enterprise.agent_application.models import AgentChat, AgentChatMessage
    from baserow_enterprise.agent_application.runner import AgentRunner

    from .test_agent_runner import register_runner_test_model_type

    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )

    with override_settings(MEDIA_ROOT=str(tmpdir)):
        user_file = data_fixture.create_user_file(
            original_name="notes.txt", mime_type="text/plain", size=5
        )
        _store_file_content(user_file, b"hello")

        # A manual message with an attachment becomes a multi-part prompt.
        chat = AgentChat.objects.create(agent=agent, user=user)
        message = AgentChatMessage.objects.create(
            chat=chat,
            role=AgentChatMessage.Role.HUMAN,
            content="Look at this.",
            attachments=[{"name": user_file.name, "visible_name": "notes.txt"}],
        )
        prompt = AgentRunner(chat)._build_user_prompt(message)
        assert prompt[0] == "Look at this."
        assert "hello" in prompt[1]

        # Files in a trigger's event payload (file field values) are injected
        # into the opening prompt of the triggered run.
        triggered_chat = AgentChat.objects.create(
            agent=agent,
            source=AgentChat.Source.TRIGGER,
            trigger_type="rows_created",
            event_payload={
                "rows": [
                    {
                        "id": 1,
                        "File": [{"name": user_file.name, "visible_name": "notes.txt"}],
                    }
                ]
            },
        )
        system_message = AgentChatMessage.objects.create(
            chat=triggered_chat,
            role=AgentChatMessage.Role.SYSTEM,
            content="A row was created.",
        )
        prompt = AgentRunner(triggered_chat)._build_user_prompt(system_message)
        assert prompt[0] == "A row was created."
        assert "hello" in prompt[1]

        # Without files the prompt stays a plain string.
        plain = AgentChatMessage.objects.create(
            chat=chat, role=AgentChatMessage.Role.HUMAN, content="Just text."
        )
        assert AgentRunner(chat)._build_user_prompt(plain) == "Just text."


@pytest.mark.django_db
def test_send_message_with_user_files_persists_attachments(
    api_client, data_fixture, tmpdir
):
    import uuid as uuid_module

    from django.test import override_settings

    from rest_framework.status import HTTP_202_ACCEPTED

    from baserow.core.handler import CoreHandler
    from baserow_enterprise.agent_application.handler import AgentApplicationHandler
    from baserow_enterprise.agent_application.models import AgentChatMessage

    from .test_agent_approvals import _register_test_types

    _register_test_types()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_approval_test",
        ai_generative_ai_model="test-model",
    )

    with override_settings(MEDIA_ROOT=str(tmpdir)):
        user_file = data_fixture.create_user_file(
            original_name="notes.txt", mime_type="text/plain", size=1
        )

        with patch(
            "baserow_enterprise.agent_application.handler.AgentChatHandler"
            ".start_chat_run"
        ):
            response = api_client.post(
                f"/api/agent_application/{application.id}/chats/"
                f"{uuid_module.uuid4()}/messages/",
                {
                    "content": "Look at this file.",
                    "user_files": [{"name": user_file.name}],
                },
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )

    assert response.status_code == HTTP_202_ACCEPTED, response.json()
    message = AgentChatMessage.objects.get(role=AgentChatMessage.Role.HUMAN)
    assert message.attachments[0]["name"] == user_file.name
    assert message.attachments[0]["visible_name"] == "notes.txt"
    assert message.attachments[0]["mime_type"] == "text/plain"


@pytest.mark.django_db
def test_send_message_with_unknown_user_file_fails(api_client, data_fixture):
    import uuid as uuid_module

    from rest_framework.status import HTTP_400_BAD_REQUEST

    from baserow.core.handler import CoreHandler
    from baserow_enterprise.agent_application.handler import AgentApplicationHandler

    from .test_agent_approvals import _register_test_types

    _register_test_types()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_approval_test",
        ai_generative_ai_model="test-model",
    )

    response = api_client.post(
        f"/api/agent_application/{application.id}/chats/"
        f"{uuid_module.uuid4()}/messages/",
        {"content": "Hi.", "user_files": [{"name": "does_not_exist.txt"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
