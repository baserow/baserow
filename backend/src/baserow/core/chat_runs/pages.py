from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.ws.registries import PageType

from .push import chat_group_name
from .registries import chat_run_type_registry


class ChatRunsPageType(PageType):
    """
    Discover run identity/status in tabs with a conversation open. Output is
    delivered through HTTP, never through this group. The run type checks access.
    """

    type = "chat_runs"
    parameters = ["run_type", "chat_id"]

    def can_add(
        self,
        user: AbstractUser,
        web_socket_id: str,
        run_type: str,
        chat_id: Any,
        **kwargs: Any,
    ) -> bool:
        """
        :param user: The user of the tab.
        :param web_socket_id: The id of the tab's websocket.
        :param run_type: The run type of the chat's runs.
        :param chat_id: The id of the chat, as the tab sent it.
        :return: Whether the run type lets the user follow the chat.
        """

        try:
            chat_run_type = chat_run_type_registry.get(run_type)
            return chat_run_type.can_follow_chat(user, int(chat_id))
        except (
            chat_run_type_registry.does_not_exist_exception_class,
            TypeError,
            ValueError,
        ):
            return False

    def get_group_name(self, run_type: str, chat_id: Any, **kwargs: Any) -> str:
        """
        :param run_type: The run type of the chat's runs.
        :param chat_id: The id of the chat, as the tab sent it.
        :return: The group the chat's runs push to.
        """

        return chat_group_name(run_type, int(chat_id))
