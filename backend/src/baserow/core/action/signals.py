from enum import Enum

from django.dispatch import Signal, receiver

from loguru import logger


class ActionCommandType(Enum):
    DO = "DO"
    UNDO = "UNDO"
    REDO = "REDO"


action_done = Signal()


@receiver(action_done)
def log_action_receiver(
    sender,
    user,
    action_type,
    action_params,
    action_timestamp,
    action_command_type,
    workspace,
    **kwargs,
):
    logger.info(
        "{action_command_type}: workspace={workspace_id} action_type={action_type} user={user_id}",
        action_command_type=action_command_type.name.lower(),
        workspace_id=workspace.id if workspace else "",
        action_type=action_type.type,
        user_id=getattr(user, "id", None),
    )
