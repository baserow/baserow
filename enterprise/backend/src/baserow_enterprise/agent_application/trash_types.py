from typing import Any, Dict, Optional

from baserow.core.trash.registries import TrashableItemType

from .models import AgentChatChannel, AgentTool, AgentTrigger
from .operations import (
    CreateAgentToolOperationType,
    UpdateAgentChatChannelOperationType,
    UpdateAgentTriggerOperationType,
)
from .signals import (
    agent_chat_channel_created,
    agent_chat_channel_deleted,
    agent_tool_created,
    agent_tool_deleted,
    agent_trigger_created,
    agent_trigger_deleted,
)


class AgentChildTrashableItemType(TrashableItemType):
    """
    Tools, triggers and chat channels are trashed rather than deleted so that
    deleting one can be undone (and creating one redone) with the same ids.
    The agent application has no trash UI of its own; the entries only serve
    undo and are emptied with the rest of the trash.
    """

    def get_application(self, trashed_item: Any):
        raise NotImplementedError

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return self.get_application(trashed_item)

    def get_restore_operation_context(self, trash_entry, trashed_item):
        # Permissions are checked on the application, like every other agent
        # operation.
        return self.get_application(trashed_item).application_ptr

    deleted_signal = None
    created_signal = None

    def trash(self, item_to_trash: Any, requesting_user, trash_entry):
        super().trash(item_to_trash, requesting_user, trash_entry)
        self.deleted_signal.send(
            self,
            **{self.id_kwarg: item_to_trash.id},
            application=self.get_application(item_to_trash),
            user=requesting_user,
        )

    def restore(self, trashed_item: Any, trash_entry):
        trashed_item.trashed = False
        trashed_item.save(update_fields=["trashed"])
        self.created_signal.send(self, **{self.object_kwarg: trashed_item}, user=None)


class AgentToolTrashableItemType(AgentChildTrashableItemType):
    type = "agent_tool"
    model_class = AgentTool
    deleted_signal = agent_tool_deleted
    created_signal = agent_tool_created
    id_kwarg = "tool_id"
    object_kwarg = "tool"

    def get_application(self, trashed_item: AgentTool):
        return trashed_item.agent.application

    def get_name(self, trashed_item: AgentTool) -> str:
        return trashed_item.name or trashed_item.type

    def get_restore_operation_type(self) -> str:
        return CreateAgentToolOperationType.type

    def permanently_delete_item(
        self, trashed_item: AgentTool, trash_item_lookup_cache: Dict[str, Any] = None
    ):
        from .tools.handler import AgentToolHandler

        AgentToolHandler().delete_tool(trashed_item)


class AgentTriggerTrashableItemType(AgentChildTrashableItemType):
    type = "agent_trigger"
    model_class = AgentTrigger
    deleted_signal = agent_trigger_deleted
    created_signal = agent_trigger_created
    id_kwarg = "trigger_id"
    object_kwarg = "trigger"

    def get_application(self, trashed_item: AgentTrigger):
        return trashed_item.application

    def get_name(self, trashed_item: AgentTrigger) -> str:
        return trashed_item.service.specific.get_type().type

    def get_restore_operation_type(self) -> str:
        return UpdateAgentTriggerOperationType.type

    def permanently_delete_item(
        self,
        trashed_item: AgentTrigger,
        trash_item_lookup_cache: Dict[str, Any] = None,
    ):
        from .triggers.handler import AgentTriggerHandler

        AgentTriggerHandler().delete_trigger(trashed_item)


class AgentChatChannelTrashableItemType(AgentChildTrashableItemType):
    type = "agent_chat_channel"
    model_class = AgentChatChannel
    deleted_signal = agent_chat_channel_deleted
    created_signal = agent_chat_channel_created
    id_kwarg = "channel_id"
    object_kwarg = "channel"

    def get_application(self, trashed_item: AgentChatChannel):
        return trashed_item.application

    def get_name(self, trashed_item: AgentChatChannel) -> str:
        return trashed_item.name or trashed_item.type

    def get_restore_operation_type(self) -> str:
        return UpdateAgentChatChannelOperationType.type

    def permanently_delete_item(
        self,
        trashed_item: AgentChatChannel,
        trash_item_lookup_cache: Dict[str, Any] = None,
    ):
        from .channels.handler import AgentChatChannelHandler

        AgentChatChannelHandler().delete_channel(trashed_item)
