from typing import Optional

from baserow.core.registry import Instance, Registry
from baserow.ws.tasks import broadcast_many_to_channel_group, broadcast_to_channel_group


class PageType(Instance):
    """
    The page registry holds the pages where the users can subscribe/add himself to.
    When added they will receive real time updates related to that page.

    A user can subscribe by sending a message to the server containing the type as
    page name and the additional parameters. Example:

    {
        'page': 'database',
        'table_id': 1
    }
    """

    parameters = []
    """
    A list of parameter name strings which are required when calling all methods. If
    for example the parameter `test` is included, then you can expect that parameter
    to be passed in the can_add and get_group_name functions. This way you can create
    dynamic groups.
    """

    def can_add(self, user, web_socket_id, **kwargs):
        """
        Indicates whether the user can be added to the page group. Here can for
        example be checked if the user has access to a related group.

        :param user: The user requesting access.
        :type user: User
        :param web_socket_id: The unique web socket id of the user.
        :type web_socket_id: str
        :param kwargs: The additional parameters including their provided values.
        :type kwargs: dict
        :return: Should indicate if the user can join the page (yes=True and no=False).
        :rtype: bool
        """

        raise NotImplementedError(
            "Each web socket page must have his own can_add method."
        )

    def get_group_name(self, **kwargs):
        """
        The generated name will be used by used by the core consumer to add the user
        to the correct group of the channel_layer. But only if the user is allowed to
        be added to the group. That is first determined by the can_add method.

        :param kwargs: The additional parameters including their provided values.
        :type kwargs: dict
        :return: The unique name of the group. This will be used as parameter to the
            channel_layer.group_add.
        :rtype: str
        """

        raise NotImplementedError(
            "Each web socket page must have his own get_group_name method."
        )

    def get_permission_channel_group_name(self, **kwargs) -> Optional[str]:
        """
        The generated name will be used by the core consumer to add the connected
        client to a permission channel group so that the consumer can then listen
        to permission changes and unsubscribe itself from channel groups where
        permissions have been revoked.

        The permission channel group is optional and so None can be returned which
        will not add the consumer subscribing to the page to any permission groups.

        :param kwargs: The additional parameters including their provided values.
        :return: The permission group name relevant to the page.
        """

        return None

    def broadcast(
        self, payload, ignore_web_socket_id=None, exclude_user_ids=None, **kwargs
    ):
        """
        Broadcasts a payload to everyone within the group.

        :param payload: A payload that must be broad casted to all the users in the
            group.
        :type payload:  dict
        :param ignore_web_socket_id: If provided then the payload will not be broad
            casted to that web socket id. This is often the sender.
        :type ignore_web_socket_id: Optional[str]
        :param exclude_user_ids: A list of User ids which should be excluded from
            receiving the message.
        :type exclude_user_ids: Optional[list]
        :param kwargs: The additional parameters including their provided values.
        :type kwargs: dict
        """

        broadcast_to_channel_group.delay(
            self.get_group_name(**kwargs),
            payload,
            ignore_web_socket_id,
            exclude_user_ids,
        )

    def broadcast_many(
        self,
        payloads_with_groups: list[tuple[dict, dict]],
        ignore_web_socket_id: str | None = None,
        exclude_user_ids: list[int] | None = None,
        **kwargs,
    ):
        """
        Broadcasts a list of payloads to everyone within a group for each payload.

        :param payloads_with_groups: a list of pairs: group keyword args and payload
            itself
        :param ignore_web_socket_id: If provided then payloads will not be broad
            casted to that web socket id. This is often the sender.
        :type ignore_web_socket_id: Optional[str]
        :param exclude_user_ids: A list of User ids which should be excluded from
            receiving messages.
        :type exclude_user_ids: Optional[list]
        :param kwargs: dict
        :return:
        """

        broadcast_many_to_channel_group.delay(
            [
                (
                    self.get_group_name(**group_kw),
                    payload,
                )
                for group_kw, payload in payloads_with_groups
            ],
            ignore_web_socket_id,
            exclude_user_ids,
        )


class PageRegistry(Registry):
    name = "ws_page"


page_registry = PageRegistry()
