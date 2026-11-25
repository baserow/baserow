from typing import Any

from rest_framework import serializers

from baserow.contrib.agent.channels.registries import AgentChannelType
from baserow.core.models import Workspace
from baserow_enterprise.agent.constants import (
    PUBLIC_CHAT_PASSWORD_MAX_LENGTH,
    PUBLIC_CHAT_PASSWORD_MIN_LENGTH,
    PUBLIC_CHAT_TITLE_MAX_LENGTH,
    PUBLIC_CHAT_WELCOME_TEXT_MAX_LENGTH,
)
from baserow_enterprise.agent.models import PublicChatAgentChannel
from baserow_enterprise.features import RBAC
from baserow_premium.license.handler import LicenseHandler


class PublicChatAgentChannelType(AgentChannelType):
    type = "public_chat"
    model_class = PublicChatAgentChannel
    allowed_fields = ["title", "welcome_text", "password"]
    serializer_field_names = ["slug", "has_password", "title", "welcome_text"]
    serializer_field_overrides = {
        "has_password": serializers.BooleanField(
            read_only=True, help_text="Whether visitors need a password."
        ),
    }
    request_serializer_field_names = ["title", "welcome_text", "password"]
    request_serializer_field_overrides = {
        "title": serializers.CharField(
            required=False,
            allow_blank=True,
            max_length=PUBLIC_CHAT_TITLE_MAX_LENGTH,
            help_text="The title visitors see; blank shows the agent's name.",
        ),
        "welcome_text": serializers.CharField(
            required=False,
            allow_blank=True,
            max_length=PUBLIC_CHAT_WELCOME_TEXT_MAX_LENGTH,
            help_text="The text visitors see before they write.",
        ),
        "password": serializers.CharField(
            required=False,
            allow_blank=True,
            write_only=True,
            trim_whitespace=False,
            min_length=PUBLIC_CHAT_PASSWORD_MIN_LENGTH,
            max_length=PUBLIC_CHAT_PASSWORD_MAX_LENGTH,
            help_text="The password visitors type; an empty string removes it.",
        ),
    }

    def is_deactivated(self, workspace: Workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(RBAC, workspace)

    def prepare_values(self, values: dict[str, Any]) -> dict[str, Any]:
        if "password" not in values:
            return values
        return {
            **values,
            "password": PublicChatAgentChannel.hash_password(values["password"]),
        }

    def get_name(self, channel: PublicChatAgentChannel) -> str:
        return channel.title or "Public chat"
