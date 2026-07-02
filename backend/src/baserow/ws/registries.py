import abc
from typing import Any, Optional

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

    def can_add(self, user: Any, web_socket_id: str, **kwargs: Any) -> bool:
        """
        Indicates whether the user can be added to the page group. Here can for
        example be checked if the user has access to a related group.

        :param user: The user requesting access.
        :param web_socket_id: The unique web socket id of the user.
        :param kwargs: The additional parameters including their provided values.
        :return: Should indicate if the user can join the page (yes=True and no=False).
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

    def get_presence_space_name(self, **kwargs) -> str | None:
        """
        Return the presence space name for this page, or None to opt out of
        presence tracking. Override to enable presence for a page type.

        :param kwargs: The additional parameters including their provided values.
        :return: A presence space name string, or None if this page type does
            not participate in presence.
        """

        return None

    def filter_focus_for_recipient(
        self,
        page_parameters: dict[str, Any],
        focus: dict[str, Any] | None,
        focus_type: "PresenceFocusType | None",
    ) -> bool:
        """
        Decide whether a recipient on this page should see the given focus
        event. Called per-recipient during focus broadcast.

        Must be overridden by every page type that enables presence (returns a
        non-None space name). Raises NotImplementedError by default to prevent
        data leaks from unimplemented filtering.

        When focus is None (clear-focus), the page type should decide whether
        to deliver the "user stopped focusing" signal.

        :param page_parameters: The recipient's page subscription parameters.
        :param focus: The focus event payload, or None for clear-focus.
        :param focus_type: The focus type instance, or None for clear-focus.
        :return: True if the recipient should see this focus event.
        """

        raise NotImplementedError(
            "Each presence-enabled page type must explicitly declare "
            "focus filtering behavior to prevent data leaks."
        )

    def broadcast(
        self,
        payload: dict[str, Any],
        ignore_web_socket_id: str | None = None,
        exclude_user_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Broadcasts a payload to everyone within the group.

        :param payload: A payload that must be broadcast to all the users in the group.
        :param ignore_web_socket_id: If provided then the payload will not be
            broadcast to that web socket id. This is often the sender.
        :param exclude_user_ids: A list of User ids which should be excluded from
            receiving the message.
        :param kwargs: The additional parameters including their provided values.
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

        prepared: list[tuple[str, dict]] = []
        for group_kw, payload in payloads_with_groups:
            prepared.append(
                (
                    self.get_group_name(**group_kw),
                    payload,
                )
            )
        broadcast_many_to_channel_group.delay(
            prepared,
            ignore_web_socket_id,
            exclude_user_ids,
        )


class PageRegistry(Registry):
    name = "ws_page"


page_registry = PageRegistry()


class InvalidFocusPayloadException(Exception):
    pass


class PresenceFocusType(abc.ABC, Instance):
    @abc.abstractmethod
    def validate(self, raw_focus: dict) -> dict:
        """
        Validate and normalize a raw focus payload from the client.

        :param raw_focus: The raw focus dict sent by the client. Always
            contains at least a ``"type"`` key matching this instance's type.
        :return: A normalized dict that must include a ``"type"`` key matching
            the registered type name. Extra keys are type-specific.
        :raises ValueError: If the payload is malformed.
        """

        ...


class PresenceFocusTypeRegistry(Registry):
    name = "presence_focus_type"

    def validate_focus(self, raw_focus: dict | None) -> tuple[dict | None, str | None]:
        """
        Validate and resolve a raw focus payload.

        Returns (validated_focus, focus_type_name) on success.
        Returns (None, None) for a clear-focus (null) payload.
        Raises InvalidFocusPayloadException if the payload is malformed
        or incompatible.
        """

        if raw_focus is None:
            return None, None

        if not isinstance(raw_focus, dict) or "type" not in raw_focus:
            raise InvalidFocusPayloadException("Missing type in focus payload")

        type_name = raw_focus["type"]
        if not isinstance(type_name, str):
            raise InvalidFocusPayloadException("Focus type must be a string")
        try:
            focus_type = self.get(type_name)
        except self.does_not_exist_exception_class:
            raise InvalidFocusPayloadException(f"Unknown focus type: {type_name}")

        try:
            return focus_type.validate(raw_focus), type_name
        except Exception as exc:
            raise InvalidFocusPayloadException(
                f"Validation failed for focus type {type_name}"
            ) from exc


presence_focus_type_registry = PresenceFocusTypeRegistry()
