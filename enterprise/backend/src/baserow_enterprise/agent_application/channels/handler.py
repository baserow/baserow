from typing import Optional

from django.db.models import QuerySet

from ..exceptions import AgentChatChannelDoesNotExist
from ..models import AgentApplication, AgentChatChannel
from .registries import agent_chat_channel_type_registry


class AgentChatChannelHandler:
    def list_channels(self, application: AgentApplication) -> QuerySet:
        return AgentChatChannel.objects.filter(application=application)

    def get_channel(self, channel_id: int) -> AgentChatChannel:
        try:
            return AgentChatChannel.objects.select_related(
                "application__workspace"
            ).get(id=channel_id)
        except AgentChatChannel.DoesNotExist:
            raise AgentChatChannelDoesNotExist(
                f"The chat channel with id {channel_id} does not exist."
            )

    def get_channel_by_uid(self, uid) -> AgentChatChannel:
        try:
            return AgentChatChannel.objects.select_related(
                "application__workspace"
            ).get(uid=uid)
        except (AgentChatChannel.DoesNotExist, ValueError):
            raise AgentChatChannelDoesNotExist(
                f"The chat channel with uid {uid} does not exist."
            )

    def create_channel(
        self,
        application: AgentApplication,
        channel_type_str: str,
        name: str = "",
        config: Optional[dict] = None,
        enabled: bool = True,
    ) -> AgentChatChannel:
        channel_type = agent_chat_channel_type_registry.get(channel_type_str)
        prepared_config = channel_type.prepare_config(config or {})

        return AgentChatChannel.objects.create(
            application=application,
            type=channel_type.type,
            name=name,
            config=prepared_config,
            enabled=enabled,
        )

    def update_channel(
        self,
        channel: AgentChatChannel,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        enabled: Optional[bool] = None,
    ) -> AgentChatChannel:
        update_fields = ["updated_on"]

        if config is not None:
            channel_type = agent_chat_channel_type_registry.get(channel.type)
            # Secrets are masked in the API, so an update without a new value
            # keeps the stored one.
            channel.config = channel_type.prepare_config(
                config, existing_config=channel.config
            )
            update_fields.append("config")

        if name is not None:
            channel.name = name
            update_fields.append("name")

        if enabled is not None:
            channel.enabled = enabled
            update_fields.append("enabled")

        channel.save(update_fields=update_fields)
        return channel

    def delete_channel(self, channel: AgentChatChannel) -> None:
        channel.delete()
