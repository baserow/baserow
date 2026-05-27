from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from baserow.config.celery import app
from baserow.ws.types import PayloadMap


@app.task(bind=True)
def force_disconnect_users(
    self, user_ids: List[int], ignore_web_socket_ids: Optional[List[str]] = None
):
    """
    This task can be executed if the users matching the provided ids must be
    disconnected.

    :param user_ids: The ids of the users that must be disconnected.
    :param ignore_web_socket_ids: An optional list of web socket id which will
        not be sent the payload if provided.
    """

    channel_layer = get_channel_layer()
    async_to_sync(send_message_to_channel_group)(
        channel_layer,
        "users",
        {
            "type": "force_disconnect_users",
            "user_ids": user_ids,
            "ignore_web_socket_ids": ignore_web_socket_ids,
        },
    )


async def send_message_to_channel_group(
    channel_layer, channel_group_name: str, message: dict
):
    """
    Sends a message to a channel group.

    All channel_layer.*send* methods must have close_pools called after due to a
    bug in channels 4.0.0 as recommended on
    https://github.com/django/channels_redis/issues/332

    :param channel_layer: The channel layer instance to use.
    :param channel_group_name: The channel group name identifying the channel group
        that should receive the message.
    :param messsage: JSON to send.
    """

    await channel_layer.group_send(channel_group_name, message)
    if hasattr(channel_layer, "close_pools"):
        # The inmemory channel layer in tests does not have this function.
        await channel_layer.close_pools()


@app.task(bind=True)
def broadcast_to_users(
    self,
    user_ids: List[int],
    payload: Dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
    send_to_all_users: bool = False,
):
    """
    Broadcasts a JSON payload the provided users.

    :param user_ids: A list containing the user ids that will be sent the payload.
    :param payload: A dictionary object containing the payload that will be
        broadcast.
    :param ignore_web_socket_id: An optional web socket id which will not be sent the
        payload if provided. This is normally the web socket id that has originally
        made the change request.
    :param send_to_all_users: If set to True all users will be sent the payload and
        the user_ids parameter will be ignored. ignore_web_socket_id however will still
        be respected.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    channel_layer = get_channel_layer()
    full_message = {
        "type": "broadcast_to_users",
        "user_ids": user_ids,
        "payload": payload,
        "ignore_web_socket_id": ignore_web_socket_id,
        "send_to_all_users": send_to_all_users,
    }
    if RealtimeEventHandler.is_recording_enabled():
        event_id = RealtimeEventHandler.record_events([("users", full_message)])[0]
        payload["realtime_update_id"] = event_id
    async_to_sync(send_message_to_channel_group)(
        channel_layer,
        "users",
        full_message,
    )


@app.task(bind=True)
def broadcast_to_permitted_users(
    self,
    workspace_id: int,
    operation_type: str,
    scope_name: str,
    scope_id: int,
    payload: Dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
):
    """
    This task will broadcast a websocket message to all the users that are permitted
    to perform the operation provided.

    :param self:
    :param workspace_id: The workspace the users are in
    :param operation_type: The operation that should be checked for
    :param scope_name: The name of the scope that the operation is executed on
    :param scope_id: The id of the scope instance
    :param payload: The message being sent
    :param ignore_web_socket_id: An optional web socket id which will not be sent the
        payload if provided. This is normally the web socket id that has originally
        made the change request.
    :return:
    """

    from baserow.core.handler import CoreHandler
    from baserow.core.mixins import TrashableModelMixin
    from baserow.core.models import Workspace, WorkspaceUser
    from baserow.core.registries import object_scope_type_registry

    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        return  # trashed in the meantime

    users_in_workspace = [
        workspace_user.user
        for workspace_user in WorkspaceUser.objects.filter(
            workspace=workspace
        ).select_related("user")
    ]

    scope_type = object_scope_type_registry.get(scope_name)
    scope_model_class = scope_type.model_class

    objects = (
        scope_model_class.objects_and_trash
        if issubclass(scope_model_class, TrashableModelMixin)
        else scope_model_class.objects
    )

    try:
        scope = objects.get(id=scope_id)
    except scope_model_class.DoesNotExist:
        return  # trashed or deleted in the meantime

    user_ids = [
        u.id
        for u in CoreHandler().check_permission_for_multiple_actors(
            users_in_workspace,
            operation_type,
            workspace,
            context=scope,
        )
    ]

    broadcast_to_users(user_ids, payload, ignore_web_socket_id=ignore_web_socket_id)


@app.task(bind=True)
def broadcast_to_users_individual_payloads(
    self, payload_map: PayloadMap, ignore_web_socket_id: Optional[str] = None
):
    """
    This task will broadcast different payloads to different users by just using one
    message.

    :param payload_map: A mapping from user_id to the payload that should be sent to
        the user. The id has to be stringified to not violate redis channel policy
    :param ignore_web_socket_id: An optional web socket id which will not be sent the
        payload if provided. This is normally the web socket id that has originally
        made the change request.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    channel_layer = get_channel_layer()
    full_message = {
        "type": "broadcast_to_users_individual_payloads",
        "payload_map": payload_map,
        "ignore_web_socket_id": ignore_web_socket_id,
    }
    if RealtimeEventHandler.is_recording_enabled():
        event_id = RealtimeEventHandler.record_events([("users", full_message)])[0]
        for inner_payload in payload_map.values():
            if isinstance(inner_payload, dict):
                inner_payload["realtime_update_id"] = event_id
    async_to_sync(send_message_to_channel_group)(
        channel_layer,
        "users",
        full_message,
    )


@app.task(bind=True)
def broadcast_many_to_channel_group(
    self,
    payloads: list[tuple[str, Dict[str, Any]]],
    ignore_web_socket_id: str | None = None,
    exclude_user_ids: list[int] | None = None,
):
    """
    Broadcasts a list of JSON payloads to all the users within the channel group
    having the provided name for each payload.

    :param payloads: A list of ``(channel_group_name, payload)`` tuples.
    :param ignore_web_socket_id: The web socket id to which messages must not be
        sent. This is normally the web socket id that has originally made the change
        request.
    :param exclude_user_ids: A list of User ids which should be excluded from
        receiving messages.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    full_messages = []
    for channel_group_name, payload in payloads:
        full_messages.append(
            (
                channel_group_name,
                payload,
                {
                    "type": "broadcast_to_group",
                    "payload": payload,
                    "ignore_web_socket_id": ignore_web_socket_id,
                    "exclude_user_ids": exclude_user_ids,
                },
            )
        )

    if RealtimeEventHandler.is_recording_enabled():
        event_ids = RealtimeEventHandler.record_events(
            [
                (channel_group_name, full_message)
                for channel_group_name, _, full_message in full_messages
            ]
        )
        for event_id, (_, payload, _) in zip(event_ids, full_messages):
            payload["realtime_update_id"] = event_id

    channel_layer = get_channel_layer()
    for channel_group_name, payload, full_message in full_messages:
        async_to_sync(send_message_to_channel_group)(
            channel_layer,
            channel_group_name,
            full_message,
        )


@app.task(bind=True)
def broadcast_to_channel_group(
    self,
    channel_group_name: str,
    payload: Dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
    exclude_user_ids: Optional[List[int]] = None,
):
    """
    Broadcasts a JSON payload to all users within the channel group having the
    provided name.

    :param channel_group_name: The name of the channel group where the payload must be
        broadcast to.
    :param payload: A dictionary object containing the payload that must be broadcast.
    :param ignore_web_socket_id: The web socket id to which the message must not be
        sent. This is normally the web socket id that has originally made the change
        request.
    :param exclude_user_ids: A list of User ids which should be excluded from
        receiving the message.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    channel_layer = get_channel_layer()
    full_message = {
        "type": "broadcast_to_group",
        "payload": payload,
        "ignore_web_socket_id": ignore_web_socket_id,
        "exclude_user_ids": exclude_user_ids,
    }
    if RealtimeEventHandler.is_recording_enabled():
        event_id = RealtimeEventHandler.record_events(
            [(channel_group_name, full_message)]
        )[0]
        payload["realtime_update_id"] = event_id
    async_to_sync(send_message_to_channel_group)(
        channel_layer,
        channel_group_name,
        full_message,
    )


@app.task(bind=True)
def broadcast_to_group(
    self,
    workspace_id: int,
    payload: Dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
):
    """
    Broadcasts a JSON payload to all users that are in provided workspace (Workspace
    model) id.

    :param workspace_id: The message will only be broadcast to the users within the
        provided workspace id.
    :param payload: A dictionary object containing the payload that must be broadcast.
    :param ignore_web_socket_id: The web socket id to which the message must not be
        sent. This is normally the web socket id that has originally made the change
        request.
    """

    from baserow.core.models import WorkspaceUser

    user_ids = [
        user["user_id"]
        for user in WorkspaceUser.objects.filter(workspace_id=workspace_id).values(
            "user_id"
        )
    ]
    if len(user_ids) == 0:
        return

    broadcast_to_users(user_ids, payload, ignore_web_socket_id)


@app.task(bind=True)
def broadcast_to_groups(
    self,
    workspace_ids: Iterable[int],
    payload: Dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
):
    """
    Broadcasts a JSON payload to all users that are in the provided workspaces.

    :param workspace_ids: Ids of workspaces to broadcast to.
    :param payload: A dictionary object containing the payload that must be broadcast.
    :param ignore_web_socket_id: The web socket id to which the message must not be
        sent. This is normally the web socket id that has originally made the change
        request.
    """

    from baserow.core.models import WorkspaceUser

    user_ids = list(
        WorkspaceUser.objects.filter(workspace_id__in=workspace_ids)
        .distinct("user_id")
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )

    if len(user_ids) == 0:
        return

    broadcast_to_users(user_ids, payload, ignore_web_socket_id)


@app.task(bind=True)
def broadcast_application_created(
    self, application_id: int, ignore_web_socket_id: Optional[str] = None
):
    """
    This task is called when an application is created. We made this a task instead of
    running the code in the signal because calculating the individual payloads can take
    a lot of computational power and should therefore not run on a gunicorn worker.

    :param application_id: The id of the application that was created
    :param ignore_web_socket_id: If provided, the web_socket_id to ignore
    """

    from baserow.api.applications.serializers import (
        PolymorphicApplicationResponseSerializer,
    )
    from baserow.core.handler import CoreHandler
    from baserow.core.models import Application, WorkspaceUser
    from baserow.core.operations import ReadApplicationOperationType

    try:
        application = Application.objects.get(id=application_id).specific
    except Application.DoesNotExist:
        return  # trashed in the meantime

    workspace = application.workspace
    users_in_workspace = [
        workspace_user.user
        for workspace_user in WorkspaceUser.objects.filter(
            workspace=workspace
        ).select_related("user")
    ]

    user_ids = [
        u.id
        for u in CoreHandler().check_permission_for_multiple_actors(
            users_in_workspace,
            ReadApplicationOperationType.type,
            workspace,
            context=application,
        )
    ]

    users_in_workspace_id_map = {user.id: user for user in users_in_workspace}

    payload_map = {}
    for user_id in user_ids:
        user = users_in_workspace_id_map[user_id]
        application_serialized = PolymorphicApplicationResponseSerializer(
            application, context={"user": user}
        ).data

        payload_map[str(user_id)] = {
            "type": "application_created",
            "application": application_serialized,
            "workspace_id": workspace.id,
        }

    broadcast_to_users_individual_payloads(payload_map, ignore_web_socket_id)


@app.task(bind=True)
def cleanup_old_realtime_events(self):
    """
    Periodic task that trims ``ws_realtime_events`` by retention age.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    RealtimeEventHandler.cleanup_old_realtime_events(
        settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    )


@app.on_after_finalize.connect
def setup_periodic_ws_realtime_events_cleanup(sender, **kwargs):
    from baserow.ws.realtime_events import (
        REALTIME_EVENTS_CLEANUP_INTERVAL_MINUTES,
    )

    sender.add_periodic_task(
        timedelta(minutes=REALTIME_EVENTS_CLEANUP_INTERVAL_MINUTES),
        cleanup_old_realtime_events.s(),
    )
