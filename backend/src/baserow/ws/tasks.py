from typing import Any, Dict, Iterable, List, Optional

from baserow.config.celery import app


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

    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

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
    payload: Dict[Any, Any],
    ignore_web_socket_id: Optional[int] = None,
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

    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    async_to_sync(send_message_to_channel_group)(
        channel_layer,
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": user_ids,
            "payload": payload,
            "ignore_web_socket_id": ignore_web_socket_id,
            "send_to_all_users": send_to_all_users,
        },
    )


@app.task(bind=True)
def broadcast_to_permitted_users(
    self,
    workspace_id: int,
    operation_type: str,
    scope_name: str,
    scope_id: int,
    payload: Dict[str, any],
    ignore_web_socket_id: Optional[int] = None,
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
    self, payload_map: Dict[str, any], ignore_web_socket_id: Optional[int] = None
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

    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    async_to_sync(send_message_to_channel_group)(
        channel_layer,
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": payload_map,
            "ignore_web_socket_id": ignore_web_socket_id,
        },
    )


@app.task(bind=True)
def broadcast_many_to_channel_group(
    self,
    payloads: list[tuple[str, dict]],
    ignore_web_socket_id: str | None = None,
    exclude_user_ids: list[int] | None = None,
):
    """
    Broadcasts a list of JSON payloads to all the users within the channel workspace
     having the provided name for each payload.

    :param payloads: A list of pairs: channel workspace and payload dictionary
        containing data that must be broadcast. Each pair can be sent to a different
        channel group.
    :param ignore_web_socket_id: The web socket id to which messages must not be
        sent. This is normally the web socket id that has originally made the change
        request.
    :param exclude_user_ids: A list of User ids which should be excluded from
        receiving messages.
    """

    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    for channel_group_name, payload in payloads:
        async_to_sync(send_message_to_channel_group)(
            channel_layer,
            channel_group_name,
            {
                "type": "broadcast_to_group",
                "payload": payload,
                "ignore_web_socket_id": ignore_web_socket_id,
                "exclude_user_ids": exclude_user_ids,
            },
        )


@app.task(bind=True)
def broadcast_to_channel_group(
    self,
    channel_group_name,
    payload,
    ignore_web_socket_id=None,
    exclude_user_ids=None,
):
    """
    Broadcasts a JSON payload all the users within the channel group having the
    provided name.

    :param channel_group_name: The name of the channel group where the payload must be
        broadcast to.
    :type workspace: str
    :param payload: A dictionary object containing the payload that must be broadcast.
    :type payload: dict
    :param ignore_web_socket_id: The web socket id to which the message must not be
        sent. This is normally the web socket id that has originally made the change
        request.
    :type ignore_web_socket_id: str
    :param exclude_user_ids: A list of User ids which should be excluded from
        receiving the message.
    :type exclude_user_ids: Optional[list]
    """

    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    async_to_sync(send_message_to_channel_group)(
        channel_layer,
        channel_group_name,
        {
            "type": "broadcast_to_group",
            "payload": payload,
            "ignore_web_socket_id": ignore_web_socket_id,
            "exclude_user_ids": exclude_user_ids,
        },
    )


@app.task(bind=True)
def broadcast_to_group(self, workspace_id, payload, ignore_web_socket_id=None):
    """
    Broadcasts a JSON payload to all users that are in provided workspace (Workspace
    model) id.

    :param workspace_id: The message will only be broadcast to the users within the
        provided workspace id.
    :type workspace_id: int
    :param payload: A dictionary object containing the payload that must be broadcast.
    :type payload: dict
    :param ignore_web_socket_id: The web socket id to which the message must not be
        sent. This is normally the web socket id that has originally made the change
        request.
    :type ignore_web_socket_id: str
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
    self, workspace_ids: Iterable[int], payload: dict, ignore_web_socket_id: str = None
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
    self, application_id: int, ignore_web_socket_id: Optional[int] = None
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
        }

    broadcast_to_users_individual_payloads(payload_map, ignore_web_socket_id)
