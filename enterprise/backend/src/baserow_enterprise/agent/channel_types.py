from typing import Any

from django.core.validators import RegexValidator

from rest_framework import serializers

from baserow.contrib.agent.channels.registries import AgentChannelType
from baserow.contrib.agent.models import AgentApplication
from baserow.core.models import Workspace
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.agent.constants import (
    PUBLIC_CHAT_COLOR_PATTERN,
    PUBLIC_CHAT_PASSWORD_MAX_LENGTH,
    PUBLIC_CHAT_PASSWORD_MIN_LENGTH,
    PUBLIC_CHAT_TITLE_MAX_LENGTH,
    PUBLIC_CHAT_WELCOME_TEXT_MAX_LENGTH,
    PublicChatBackground,
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


APPEARANCE_FIELDS = [
    "accent_color",
    "background",
    "background_color",
]
COLOR_FIELDS = ["accent_color", "background_color"]


def color_field(help_text: str) -> serializers.CharField:
    """
    :param help_text: What the colour is for.
    :return: A field taking a `#rrggbb` colour, or blank for the default.
    """

    return serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=7,
        validators=[RegexValidator(PUBLIC_CHAT_COLOR_PATTERN)],
        help_text=f"{help_text} As `#rrggbb`; blank for the default.",
    )


APPEARANCE_FIELD_OVERRIDES = {
    "accent_color": color_field(
        "The colour of the buttons and the visitor's messages."
    ),
    "background": serializers.ChoiceField(
        required=False,
        choices=PublicChatBackground.choices,
        help_text="How the page background is drawn.",
    ),
    "background_color": color_field("The solid background colour or gradient tint."),
}


def imported_appearance(serialized: dict[str, Any]) -> dict[str, Any]:
    """
    :param serialized: A public chat from an imported file, which may hold anything.
    :return: The appearance values the API would accept; any other is left to the
        model's default.
    """

    appearance = {}
    for name, field in APPEARANCE_FIELD_OVERRIDES.items():
        try:
            appearance[name] = field.run_validation(serialized.get(name))
        except serializers.ValidationError:
            continue
    return appearance


class PublicChatAgentChannelType(AgentChannelType):
    type = "public_chat"
    model_class = PublicChatAgentChannel
    allowed_fields = ["title", "welcome_text", "password", *APPEARANCE_FIELDS]
    serializer_field_names = [
        "slug",
        "has_password",
        "title",
        "welcome_text",
        *APPEARANCE_FIELDS,
    ]
    serializer_field_overrides = {
        "has_password": serializers.BooleanField(
            read_only=True, help_text="Whether visitors need a password."
        ),
        **APPEARANCE_FIELD_OVERRIDES,
    }
    request_serializer_field_names = [
        "title",
        "welcome_text",
        "password",
        *APPEARANCE_FIELDS,
    ]
    request_serializer_field_overrides = {
        **APPEARANCE_FIELD_OVERRIDES,
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
        prepared = {
            **values,
            **{name: values[name].lower() for name in COLOR_FIELDS if name in values},
        }
        if "password" in values:
            prepared["password"] = PublicChatAgentChannel.hash_password(
                values["password"]
            )
        return prepared

    def get_name(self, channel: PublicChatAgentChannel) -> str:
        return channel.title or "Public chat"

    def export_serialized(
        self,
        channel: PublicChatAgentChannel,
        import_export_config: ImportExportConfig,
    ) -> dict[str, Any]:
        serialized = super().export_serialized(channel, import_export_config)
        serialized.update(
            title=channel.title,
            welcome_text=channel.welcome_text,
            **{name: getattr(channel, name) for name in APPEARANCE_FIELDS},
        )
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
            **imported_appearance(serialized),
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
