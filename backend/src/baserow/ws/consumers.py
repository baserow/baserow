from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from baserow.ws.registries import PageType, page_registry

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


@dataclass
class PageContext:
    """
    The context about a page and a user when the user
    intends to be subscribed or unsubscribed from
    getting changes relevant to the page.
    """

    web_socket_id: str
    user: Optional["AbstractUser"]
    resolved_page_type: PageType
    page_scope: "PageScope"


@dataclass
class PageScope:
    """
    Represents one page that a user can be subscribed to.
    Different page parameters can be used to represent
    subscriptions to the same page types with different
    values (e.g. being subscribed to a table page with
    table_id=1 or table_id=2)
    """

    page_type: str
    page_parameters: dict[str, any]


class SubscribedPages:
    """
    Holds information about all pages a user is subscribed to.
    """

    def __init__(self):
        self.pages: list[PageScope] = []

    def add(self, page_scope: PageScope):
        """
        Adds a page to the list of subscribed pages.

        :param page_scope: Page to add.
        """

        if page_scope not in self.pages:
            self.pages.append(page_scope)

    def remove(self, page_scope: PageScope):
        """
        Removes a page from the list of subscribed pages.

        :param page_scope: Page to remove.
        """

        try:
            self.pages.remove(page_scope)
        except ValueError:
            pass

    def is_page_in_permission_group(
        self, page_scope: PageScope, group_name_to_check: str
    ) -> bool:
        """
        Checks whether an instance of PageScope belongs to the provided
        permission group.

        :param page_scope: The page to check.
        :param group_name_to_check: The permission group name that will be
            compared to permission group name of the page.
        :return: True if the page has the same permission group name.
        """

        try:
            page_type = page_registry.get(page_scope.page_type)
        except page_registry.does_not_exist_exception_class:
            return False

        page_perm_group_name = page_type.get_permission_channel_group_name(
            **page_scope.page_parameters
        )
        if page_perm_group_name == group_name_to_check:
            return True
        return False

    def has_pages_with_permission_group(self, group_name_to_check: str) -> bool:
        """
        Utility method that determines whether the list of subscribed
        pages contains any page with the provided permission group.

        This is useful to know for consumers using this class to determine
        if by unsubscribing to a page they should unsubscribe from a
        permission group as well or there are still pages that need the
        same permission group.

        :param group_name_to_check: The permission group name that will be
            compared to permission group names of the subscribed pages.
        :return: True if the list of subscribed pages contains any page matching
            the provided permission group name.
        """

        return any(
            self.is_page_in_permission_group(page, group_name_to_check)
            for page in self.pages
        )

    def copy(self):
        new = SubscribedPages()
        new.pages = self.pages.copy()
        return new

    def __len__(self):
        return len(self.pages)

    def __iter__(self):
        return iter(self.pages)


class CoreConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

        user = self.scope["user"]
        web_socket_id = self.scope["web_socket_id"]

        await self.send_json(
            {
                "type": "authentication",
                "success": user is not None,
                "web_socket_id": web_socket_id,
            }
        )

        if not user:
            await self.close()
            return

        self.scope["pages"] = SubscribedPages()
        await self.channel_layer.group_add("users", self.channel_name)

    async def disconnect(self, message):
        await self._remove_all_page_scopes(send_confirmation=False)
        await self.channel_layer.group_discard("users", self.channel_name)

    async def receive_json(self, content, **parameters):
        """
        Processes incoming messages.
        """

        if "page" in content:
            await self._add_page_scope(content)
        if "remove_page" in content:
            await self._remove_page_scope(content)

    async def _get_page_context(
        self, content: dict, page_name_attr: str
    ) -> Optional[PageContext]:
        """
        Helper method that will construct a PageContext object for adding
        or removing page scopes from the consumer.

        :param content: Dictionary representing the JSON that the client sent.
        :param page_name_attr: Identifies the name of the parameter in the
            content dictionary that refers to the page type.
        """

        user = self.scope["user"]
        web_socket_id = self.scope["web_socket_id"]

        if not user:
            return None

        try:
            page_type = page_registry.get(content[page_name_attr])
        except page_registry.does_not_exist_exception_class:
            return None

        parameters = {
            parameter: content.get(parameter) for parameter in page_type.parameters
        }

        return PageContext(
            page_scope=PageScope(
                page_type=content[page_name_attr],
                page_parameters=parameters,
            ),
            resolved_page_type=page_type,
            user=user,
            web_socket_id=web_socket_id,
        )

    async def _add_page_scope(self, content: dict):
        """
        Subscribes the connection to a page abstraction. Based on the provided page
        type we can figure out to which page the connection wants to subscribe to. This
        is for example used when the users visits a page that they might want to
        receive real time updates for.

        :param content: The provided payload by the user. This should contain the page
            type and additional parameters.
        """

        context = await self._get_page_context(content, "page")

        if not context:
            return

        user, web_socket_id, page_type, parameters = attrgetter(
            "user", "web_socket_id", "resolved_page_type", "page_scope.page_parameters"
        )(context)

        can_add = await database_sync_to_async(page_type.can_add)(
            user, web_socket_id, **parameters
        )

        if not can_add:
            return

        group_name = page_type.get_group_name(**parameters)
        await self.channel_layer.group_add(group_name, self.channel_name)

        permission_group_name = page_type.get_permission_channel_group_name(
            **parameters
        )
        if permission_group_name:
            await self.channel_layer.group_add(permission_group_name, self.channel_name)

        page_scope = PageScope(page_type=page_type.type, page_parameters=parameters)
        self.scope["pages"].add(page_scope)

        await self.send_json(
            {"type": "page_add", "page": page_type.type, "parameters": parameters}
        )

    async def _remove_page_scope(self, content: dict, send_confirmation=True):
        """
        Unsubscribes the connection from a page. Based on the provided page
        type and its params we can figure out to which page the connection wants
        to unsubscribe from.

        :param content: The provided payload by the user. This should contain the page
            type and additional parameters.
        :param send_confirmation: If True, the client will receive a confirmation
            message about unsubscribing.
        """

        context = await self._get_page_context(content, "remove_page")

        if not context:
            return

        user, page_type, parameters = attrgetter(
            "user", "resolved_page_type", "page_scope.page_parameters"
        )(context)

        group_name = page_type.get_group_name(**parameters)
        await self.channel_layer.group_discard(group_name, self.channel_name)

        page_scope = PageScope(page_type=page_type.type, page_parameters=parameters)

        self.scope["pages"].remove(page_scope)

        permission_group_name = page_type.get_permission_channel_group_name(
            **parameters
        )
        if permission_group_name and not self.scope[
            "pages"
        ].has_pages_with_permission_group(permission_group_name):
            await self.channel_layer.group_discard(
                permission_group_name, self.channel_name
            )

        if send_confirmation:
            await self.send_json(
                {
                    "type": "page_discard",
                    "page": page_type.type,
                    "parameters": parameters,
                }
            )

    async def _remove_all_page_scopes(self, send_confirmation=True):
        """
        Unsubscribes the connection from all currently subscribed pages.
        """

        if self.scope.get("pages"):
            for page_scope in self.scope["pages"].copy():
                content = {
                    "user": self.scope["user"],
                    "web_socket_id": self.scope["web_socket_id"],
                    "remove_page": page_scope.page_type,
                    **page_scope.page_parameters,
                }
                await self._remove_page_scope(
                    content, send_confirmation=send_confirmation
                )

    async def _remove_page_scopes_associated_with_perm_group(
        self, permission_group_name: str
    ):
        """
        Unsubscribes the connection from all currently subscribed pages associated
        with the provided permission channel group.

        :param permission_group_name: The name of the permission channel group.
        """

        if self.scope.get("pages"):
            for page_scope in self.scope["pages"].copy():
                if self.scope["pages"].is_page_in_permission_group(
                    page_scope, permission_group_name
                ):
                    content = {
                        "user": self.scope["user"],
                        "web_socket_id": self.scope["web_socket_id"],
                        "remove_page": page_scope.page_type,
                        **page_scope.page_parameters,
                    }
                    await self._remove_page_scope(content, send_confirmation=True)

    # Event handlers

    async def force_disconnect_users(self, event):
        """
        Closes the connection with this user if their user id is in the provided
        list.

        :param event: The event containing the payload: the user ids that must
            be disconnected and optionally the web socket ids to ignore from
            disconnection.
        """

        disconnect_user_ids = event["user_ids"]
        ignore_web_socket_ids = event["ignore_web_socket_ids"] or []

        user_id = self.scope["user"].id
        web_socket_id = self.scope["web_socket_id"]

        if (
            user_id in disconnect_user_ids
            and web_socket_id not in ignore_web_socket_ids
        ):
            await self.send_json({"type": "force_disconnect"})
            return await self.close()

    async def broadcast_to_users(self, event):
        """
        Broadcasts a message to all the users that are in the provided user_ids list.
        Optionally the ignore_web_socket_id is ignored because that is often the
        sender. Also, if `send_to_all_users` is set to True then all users will be sent
        the payload regardless of `user_ids`, but `ignore_web_socket_id` will still
        be respected.

        :param event: The event containing the payload, user ids and the web socket
            id that must be ignored.
        :type event: dict
        """

        web_socket_id = self.scope["web_socket_id"]
        payload = event["payload"]
        user_ids = event["user_ids"]
        ignore_web_socket_id = event["ignore_web_socket_id"]
        send_to_all_users = event["send_to_all_users"]

        shouldnt_ignore = (
            not ignore_web_socket_id or ignore_web_socket_id != web_socket_id
        )
        if shouldnt_ignore and (self.scope["user"].id in user_ids or send_to_all_users):
            await self.send_json(payload)

    async def broadcast_to_users_individual_payloads(self, event):
        """
        Accepts a payload mapping and sends the payload as JSON if the user_id of the
        consumer is part of the mapping provided

        :param event: The event containing the payload mapping
        """

        web_socket_id = self.scope["web_socket_id"]

        payload_map = event["payload_map"]
        ignore_web_socket_id = event["ignore_web_socket_id"]

        user_id = str(self.scope["user"].id)

        shouldnt_ignore = (
            not ignore_web_socket_id or ignore_web_socket_id != web_socket_id
        )

        if shouldnt_ignore and user_id in payload_map:
            await self.send_json(payload_map[user_id])

    async def broadcast_to_group(self, event):
        """
        Broadcasts a message to all the users that are in the provided group name.

        :param event: The event containing the payload, group name and the web socket
            id that must be ignored.
        :type event: dict
        """

        web_socket_id = self.scope["web_socket_id"]
        payload = event["payload"]
        ignore_web_socket_id = event["ignore_web_socket_id"]
        exclude_user_ids = set(event.get("exclude_user_ids", None) or [])
        user_id = self.scope["user"].id

        if user_id in exclude_user_ids:
            return

        if not ignore_web_socket_id or ignore_web_socket_id != web_socket_id:
            await self.send_json(payload)

    async def users_removed_from_permission_group(self, event):
        """
        Event handler that reacts to a situation when one or many users were
        revoked access to resources associated with a permission channel group.

        When that happens the consumer has to check whether it is the consumer of
        the involved user and if so, remove itself from all pages associated with
        the permission channel group.
        """

        user_ids_to_remove = event["user_ids_to_remove"]
        user_id = self.scope["user"].id

        if user_id in user_ids_to_remove:
            await self._remove_page_scopes_associated_with_perm_group(
                event["permission_group_name"]
            )
