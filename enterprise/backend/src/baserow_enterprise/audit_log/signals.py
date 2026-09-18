from datetime import datetime
from typing import Any, Dict, Optional, Type

from django.dispatch import receiver

from baserow.core.action.registries import ActionType
from baserow.core.action.signals import ActionCommandType, action_done
from baserow.core.models import Workspace
from baserow.core.types import Actor

from .handler import AuditLogHandler


@receiver(action_done)
def log_action(
    sender,
    user: Actor,
    action_type: Type[ActionType],
    action_params: Dict[str, Any],
    action_timestamp: datetime,
    action_command_type: ActionCommandType,
    action_uuid: str,
    workspace: Optional[Workspace] = None,
    **kwargs,
):
    AuditLogHandler.log_action(
        user,
        action_type,
        action_params,
        action_timestamp,
        action_command_type,
        action_uuid=action_uuid,
        workspace=workspace,
        **kwargs,
    )
