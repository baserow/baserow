from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer

from baserow.config.celery import app
from baserow.ws.types import ChannelGroupMessage, PayloadMap


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
    async_to_sync(send_messages_to_channel_group)(
        channel_layer,
        ChannelGroupMessage(
            "users",
            {
                "type": "force_disconnect_users",
                "user_ids": user_ids,
                "ignore_web_socket_ids": ignore_web_socket_ids,
            },
        ),
    )


async def send_messages_to_channel_group(
    channel_layer,
    messages: ChannelGroupMessage | list[ChannelGroupMessage],
) -> None:
    """
    Sends one or more messages to their channel groups. A single
    ``ChannelGroupMessage`` is accepted as well as a list, so callers that
    only have one message don't have to wrap it themselves. When event
    recording is enabled, all recordable messages (those carrying a
    ``payload`` or ``payload_map``) are persisted in a single batch (one
    ``bulk_create`` instead of one insert per message) and their ids are
    injected into the inner payload(s) **before** the messages are sent.

    :param channel_layer: The channel layer instance to use.
    :param messages: A single ``ChannelGroupMessage`` or a list of them.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    if isinstance(messages, ChannelGroupMessage):
        messages = [messages]

    if RealtimeEventHandler.is_recording_enabled():
        recordable = [
            channel_group_message
            for channel_group_message in messages
            if channel_group_message.message.get("payload") is not None
            or channel_group_message.message.get("payload_map") is not None
        ]
        if recordable:
            event_ids = await database_sync_to_async(
                RealtimeEventHandler.record_events, thread_sensitive=False
            )(recordable)
            for channel_group_message, event_id in zip(recordable, event_ids):
                RealtimeEventHandler.add_event_id_to_payload(
                    event_id, channel_group_message.message
                )

    for channel_group_message in messages:
        await channel_layer.group_send(
            channel_group_message.channel_group_name, channel_group_message.message
        )
    if hasattr(channel_layer, "close_pools"):
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

    channel_layer = get_channel_layer()
    async_to_sync(send_messages_to_channel_group)(
        channel_layer,
        ChannelGroupMessage(
            "users",
            {
                "type": "broadcast_to_users",
                "user_ids": user_ids,
                "payload": payload,
                "ignore_web_socket_id": ignore_web_socket_id,
                "send_to_all_users": send_to_all_users,
            },
        ),
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

    channel_layer = get_channel_layer()
    async_to_sync(send_messages_to_channel_group)(
        channel_layer,
        ChannelGroupMessage(
            "users",
            {
                "type": "broadcast_to_users_individual_payloads",
                "payload_map": payload_map,
                "ignore_web_socket_id": ignore_web_socket_id,
            },
        ),
    )


@app.task(bind=True)
def broadcast_ai_provider_update(
    self, workspace_id: int | None, model_availability_updated: bool
):
    """Broadcast complete, permission-scoped AI provider state to each user."""

    from django.contrib.auth import get_user_model

    from baserow.api.ai_provider.serializers import (
        AIProviderConfigSerializer,
        WorkspaceAIProviderConfigSerializer,
    )
    from baserow.core.ai_provider.handler import AIProviderHandler
    from baserow.core.generative_ai.registries import (
        generative_ai_model_type_registry,
    )
    from baserow.core.handler import CoreHandler
    from baserow.core.models import Workspace
    from baserow.core.operations import UpdateWorkspaceOperationType

    workspaces = list(
        Workspace.objects.filter(id=workspace_id)
        if workspace_id is not None
        else Workspace.objects.all()
    )
    workspace_ids = [workspace.id for workspace in workspaces]
    if model_availability_updated:
        generative_ai_model_type_registry.prefetch_workspace_configuration(
            workspace_ids
        )

    payload_map: PayloadMap = {}

    def payload_for(user_id: int) -> dict[str, Any]:
        return payload_map.setdefault(
            str(user_id),
            {
                "type": "ai_provider_updated",
                "model_availability_updated": model_availability_updated,
            },
        )

    for workspace in workspaces:
        workspace_users = [
            workspace_user.user
            for workspace_user in workspace.workspaceuser_set.select_related("user")
        ]
        workspace_key = str(workspace.id)

        if model_availability_updated:
            enabled_models = (
                generative_ai_model_type_registry.get_enabled_models_per_type(workspace)
            )
            for user in workspace_users:
                payload_for(user.id).setdefault(
                    "generative_ai_models_enabled_by_workspace", {}
                )[workspace_key] = enabled_models

        permitted_users = CoreHandler().check_permission_for_multiple_actors(
            workspace_users,
            UpdateWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        if permitted_users:
            providers = list(
                WorkspaceAIProviderConfigSerializer(
                    AIProviderHandler.list_providers(workspace), many=True
                ).data
            )
            for user in permitted_users:
                payload_for(user.id).setdefault("ai_providers_by_workspace", {})[
                    workspace_key
                ] = providers

    if workspace_id is None:
        instance_providers = list(
            AIProviderConfigSerializer(
                AIProviderHandler.list_providers(), many=True
            ).data
        )
        staff_user_ids = (
            get_user_model()
            .objects.filter(is_active=True, is_staff=True)
            .values_list("id", flat=True)
        )
        for user_id in staff_user_ids:
            payload_for(user_id)["instance_ai_providers"] = instance_providers

    if payload_map:
        broadcast_to_users_individual_payloads(payload_map)


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

    channel_layer = get_channel_layer()
    messages = [
        ChannelGroupMessage(
            channel_group_name,
            {
                "type": "broadcast_to_group",
                "payload": payload,
                "ignore_web_socket_id": ignore_web_socket_id,
                "exclude_user_ids": exclude_user_ids,
            },
        )
        for channel_group_name, payload in payloads
    ]
    async_to_sync(send_messages_to_channel_group)(channel_layer, messages)


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

    channel_layer = get_channel_layer()
    async_to_sync(send_messages_to_channel_group)(
        channel_layer,
        ChannelGroupMessage(
            channel_group_name,
            {
                "type": "broadcast_to_group",
                "payload": payload,
                "ignore_web_socket_id": ignore_web_socket_id,
                "exclude_user_ids": exclude_user_ids,
            },
        ),
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
        }

    broadcast_to_users_individual_payloads(payload_map, ignore_web_socket_id)


@app.task(bind=True)
def cleanup_old_realtime_events(self):
    """
    Periodic task that trims ``ws_realtime_events`` by retention age. When
    recording is disabled there is nothing to trim, so the query is skipped
    entirely to keep the feature zero-impact by default.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    if not RealtimeEventHandler.is_recording_enabled():
        return

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
