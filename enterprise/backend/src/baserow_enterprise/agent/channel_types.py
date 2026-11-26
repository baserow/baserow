from typing import Any

from rest_framework import serializers

from baserow.contrib.agent.channels.registries import AgentChannelType
from baserow.contrib.agent.models import AgentApplication
from baserow.core.models import Workspace
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.agent.constants import (
    PUBLIC_CHAT_PASSWORD_MAX_LENGTH,
    PUBLIC_CHAT_PASSWORD_MIN_LENGTH,
    PUBLIC_CHAT_TITLE_MAX_LENGTH,
    PUBLIC_CHAT_WELCOME_TEXT_MAX_LENGTH,
)
from baserow_enterprise.agent.models import PublicChatAgentChannel
from baserow_enterprise.features import RBAC
from baserow_premium.license.handler import LicenseHandler

PASSWORD_HASH_LENGTH = PublicChatAgentChannel._meta.get_field("password").max_length


def imported_text(value: object, max_length: int) -> str:
    """
    :param value: A text from an imported file, which may be anything.
    :param max_length: The longest text the field stores.
    :return: The text cut to fit, or an empty string when it isn't one.
    """

    return value[:max_length] if isinstance(value, str) else ""


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

    def export_serialized(
        self,
        channel: PublicChatAgentChannel,
        import_export_config: ImportExportConfig,
    ) -> dict[str, Any]:
        serialized = super().export_serialized(channel, import_export_config)
        serialized.update(title=channel.title, welcome_text=channel.welcome_text)
        if self._keeps_password(import_export_config):
            serialized["password"] = channel.password
        return serialized

    def import_serialized(
        self,
        agent: AgentApplication,
        serialized: dict[str, Any],
        import_export_config: ImportExportConfig,
        **values: Any,
    ) -> PublicChatAgentChannel:
        keeps_password = self._keeps_password(import_export_config)
        return super().import_serialized(
            agent,
            serialized,
            import_export_config,
            title=imported_text(serialized.get("title"), PUBLIC_CHAT_TITLE_MAX_LENGTH),
            welcome_text=imported_text(
                serialized.get("welcome_text"), PUBLIC_CHAT_WELCOME_TEXT_MAX_LENGTH
            ),
            password=imported_text(serialized.get("password"), PASSWORD_HASH_LENGTH)
            if keeps_password
            else "",
        )

    def _keeps_password(self, import_export_config: ImportExportConfig) -> bool:
        """
        Only a copy on this instance keeps the hash: an exported file would carry
        it to anyone who gets the file, where it can be guessed offline.

        :param import_export_config: How the agent is exported or imported.
        :return: Whether the copy keeps the password.
        """

        return (
            import_export_config.is_duplicate
            and not import_export_config.is_template
            and not import_export_config.exclude_sensitive_data
        )
