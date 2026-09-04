from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer

from baserow.config.celery import app
from baserow.ws.types import ChannelGroupMessage, PayloadMap

# Instance-level provider changes can affect every workspace. Keep both the amount of
# state resolved by one worker and the number of recipients in one channel-layer
# message bounded. These are deliberately constants rather than deployment settings:
# they are safety limits, not product behaviour.
AI_PROVIDER_UPDATE_WORKSPACE_BATCH_SIZE = 25
AI_PROVIDER_UPDATE_RECIPIENT_BATCH_SIZE = 250
AI_PROVIDER_UPDATE_RENDER_LOCK_KEY = "ai_provider_update_renderer"
AI_PROVIDER_UPDATE_RENDER_LOCK_TIMEOUT = 300
# ASGI channel layers only guarantee messages up to 1 MB when JSON encoded. Leave
# headroom for the recorded event id and serializer framing.
AI_PROVIDER_UPDATE_MAX_ENVELOPE_BYTES = 900 * 1024


def _ai_provider_refresh_marker(
    workspace_id: int | None,
    model_availability_updated: bool,
    *,
    refresh_workspace_availability: bool,
    refresh_provider_settings: bool,
) -> dict[str, Any]:
    return {
        "type": "ai_provider_updated",
        "model_availability_updated": model_availability_updated,
        "requires_refresh": True,
        "workspace_id": workspace_id,
        "refresh_workspace_availability": refresh_workspace_availability,
        "refresh_provider_settings": refresh_provider_settings,
    }


def _bounded_ai_provider_payload(
    user_ids: list[int], payload: dict[str, Any], refresh_marker: dict[str, Any]
) -> dict[str, Any]:
    """Replace an oversized global-users envelope with a compact recovery marker."""

    import json

    from django.core.serializers.json import DjangoJSONEncoder

    envelope = {
        "type": "broadcast_to_users",
        "user_ids": user_ids,
        "payload": payload,
        "ignore_web_socket_id": None,
        "send_to_all_users": False,
    }
    size = len(
        json.dumps(
            envelope,
            cls=DjangoJSONEncoder,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return payload if size <= AI_PROVIDER_UPDATE_MAX_ENVELOPE_BYTES else refresh_marker


def _ai_provider_renderer_lock():
    """Return a renewable cross-worker lock for provider snapshot rendering."""

    from django.core.cache import cache

    return cache.lock(
        AI_PROVIDER_UPDATE_RENDER_LOCK_KEY,
        timeout=AI_PROVIDER_UPDATE_RENDER_LOCK_TIMEOUT,
    )


def _renew_ai_provider_renderer_lock(lock) -> None:
    """Keep ownership while rendering, recording, and sending a snapshot."""

    lock.reacquire()


def _ai_provider_snapshot_transaction():
    """Return a primary-backed repeatable-read transaction when one can be opened."""

    from contextlib import nullcontext

    from django.db import DEFAULT_DB_ALIAS, transaction

    from baserow.config.db_routers import set_db_alias
    from baserow.core.db import IsolationLevel, transaction_atomic

    set_db_alias(DEFAULT_DB_ALIAS)
    if transaction.get_connection(DEFAULT_DB_ALIAS).in_atomic_block:
        # Direct callers can already own a transaction (notably TestCase). A Celery
        # task starts in autocommit and always takes the repeatable-read branch below.
        return nullcontext()
    return transaction_atomic(
        using=DEFAULT_DB_ALIAS,
        isolation_level=IsolationLevel.REPEATABLE_READ,
    )


def _run_ai_provider_renderer(renderer, sender, *args) -> None:
    """Serialize one coherent provider snapshot and retain ordering through send."""

    from redis.exceptions import LockNotOwnedError

    from baserow.cachalot_patch import cachalot_disabled

    lock = _ai_provider_renderer_lock()
    lock.acquire()
    try:
        with cachalot_disabled():
            with _ai_provider_snapshot_transaction():
                rendered = renderer(*args, lock)
        sender(rendered, lock)
    finally:
        try:
            lock.release()
        except LockNotOwnedError:
            # If a renderer exceeded the guarded timeout, it must not release a lock
            # subsequently acquired by another worker.
            pass


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
    """
    Schedule or send permission-scoped AI provider state updates.

    A workspace-scoped change is handled in this task, as before. An instance-scoped
    change is fanned out into bounded workspace batches and a separate instance-admin
    update. This prevents one Celery worker from loading every workspace/member and
    constructing one unbounded ``payload_map``.
    """

    from django.db import DEFAULT_DB_ALIAS

    from baserow.config.db_routers import set_db_alias
    from baserow.core.models import Workspace
    from baserow.core.utils import grouper

    # This task is queued after commit. A replica can still lag behind that commit and
    # must never be used to decide which workspaces receive its authoritative update.
    set_db_alias(DEFAULT_DB_ALIAS)

    if workspace_id is not None:
        _broadcast_ai_provider_workspace_updates(
            [workspace_id], model_availability_updated
        )
        return

    # Instance administrators don't need to wait for every workspace id to be read and
    # queued. Their payload is independent and is recipient-batched by its own task.
    broadcast_ai_provider_instance_update.delay(model_availability_updated)

    workspace_ids = (
        Workspace.objects.order_by("id")
        .values_list("id", flat=True)
        .iterator(chunk_size=AI_PROVIDER_UPDATE_WORKSPACE_BATCH_SIZE)
    )
    for workspace_id_batch in grouper(
        AI_PROVIDER_UPDATE_WORKSPACE_BATCH_SIZE, workspace_ids
    ):
        broadcast_ai_provider_workspace_update_batch.delay(
            list(workspace_id_batch), model_availability_updated
        )


@app.task(bind=True)
def broadcast_ai_provider_workspace_update_batch(
    self, workspace_ids: list[int], model_availability_updated: bool
):
    """Broadcast provider updates for one bounded batch of workspaces."""

    if not workspace_ids:
        return

    _broadcast_ai_provider_workspace_updates(workspace_ids, model_availability_updated)


def _broadcast_ai_provider_workspace_updates(
    workspace_ids: list[int], model_availability_updated: bool
) -> None:
    """Render and send one bounded workspace batch without unbounded user lists."""

    _run_ai_provider_renderer(
        _render_ai_provider_workspace_updates,
        _send_ai_provider_workspace_updates,
        workspace_ids,
        model_availability_updated,
    )


def _render_ai_provider_workspace_updates(
    workspace_ids: list[int], model_availability_updated: bool, renderer_lock
) -> list[tuple[Any, dict[str, Any], dict[str, Any]]]:
    """Render coherent public and privileged payloads for a workspace batch."""

    from baserow.api.ai_provider.serializers import (
        AIProviderFeatureSettingSerializer,
        WorkspaceAIProviderConfigSerializer,
    )
    from baserow.core.ai_provider.handler import AIProviderHandler
    from baserow.core.ai_provider.registries import (
        ai_provider_model_feature_type_registry,
    )
    from baserow.core.ai_provider.resolution import load_ai_provider_state
    from baserow.core.generative_ai.registries import (
        generative_ai_model_type_registry,
    )
    from baserow.core.models import Workspace

    workspaces = list(Workspace.objects.filter(id__in=workspace_ids).order_by("id"))
    if not workspaces:
        return []

    states = load_ai_provider_state(workspaces)
    rendered = []

    for workspace in workspaces:
        _renew_ai_provider_renderer_lock(renderer_lock)
        workspace_key = str(workspace.id)
        state = states[workspace.id]

        base_payload: dict[str, Any] = {
            "type": "ai_provider_updated",
            "model_availability_updated": model_availability_updated,
        }
        if model_availability_updated:
            enabled_models = (
                generative_ai_model_type_registry.get_enabled_models_per_type(
                    workspace, state=state
                )
            )
            ai_features = (
                ai_provider_model_feature_type_registry.get_workspace_availability(
                    workspace, state=state
                )
            )
            base_payload["generative_ai_models_enabled_by_workspace"] = {
                workspace_key: enabled_models
            }
            base_payload["ai_features_by_workspace"] = {workspace_key: ai_features}

        providers = list(
            WorkspaceAIProviderConfigSerializer(
                AIProviderHandler.list_providers(workspace, state=state),
                many=True,
            ).data
        )
        feature_settings = list(
            AIProviderFeatureSettingSerializer(
                AIProviderHandler.list_feature_settings(workspace, state=state),
                many=True,
                context={"workspace_id": workspace.id},
            ).data
        )
        provider_payload = {
            **base_payload,
            "ai_providers_by_workspace": {workspace_key: providers},
            "ai_provider_feature_settings_by_workspace": {
                workspace_key: feature_settings
            },
        }
        rendered.append((workspace, base_payload, provider_payload))

    return rendered


def _send_ai_provider_workspace_updates(rendered, renderer_lock) -> None:
    """Permission-batch and send already-rendered workspace payloads."""

    from baserow.core.handler import CoreHandler
    from baserow.core.operations import UpdateWorkspaceOperationType
    from baserow.core.utils import grouper

    for workspace, base_payload, provider_payload in rendered:
        workspace_users = (
            workspace.workspaceuser_set.order_by("id")
            .select_related("user")
            .iterator(chunk_size=AI_PROVIDER_UPDATE_RECIPIENT_BATCH_SIZE)
        )
        for workspace_user_batch in grouper(
            AI_PROVIDER_UPDATE_RECIPIENT_BATCH_SIZE, workspace_users
        ):
            _renew_ai_provider_renderer_lock(renderer_lock)
            users = [workspace_user.user for workspace_user in workspace_user_batch]
            permitted_user_ids = {
                user.id
                for user in CoreHandler().check_permission_for_multiple_actors(
                    users,
                    UpdateWorkspaceOperationType.type,
                    workspace=workspace,
                    context=workspace,
                )
            }

            if base_payload["model_availability_updated"]:
                member_user_ids = [
                    user.id for user in users if user.id not in permitted_user_ids
                ]
                if member_user_ids:
                    payload = _bounded_ai_provider_payload(
                        member_user_ids,
                        base_payload,
                        _ai_provider_refresh_marker(
                            workspace.id,
                            True,
                            refresh_workspace_availability=True,
                            refresh_provider_settings=False,
                        ),
                    )
                    _renew_ai_provider_renderer_lock(renderer_lock)
                    broadcast_to_users(member_user_ids, dict(payload))

            if permitted_user_ids:
                sorted_user_ids = sorted(permitted_user_ids)
                payload = _bounded_ai_provider_payload(
                    sorted_user_ids,
                    provider_payload,
                    _ai_provider_refresh_marker(
                        workspace.id,
                        base_payload["model_availability_updated"],
                        refresh_workspace_availability=base_payload[
                            "model_availability_updated"
                        ],
                        refresh_provider_settings=True,
                    ),
                )
                _renew_ai_provider_renderer_lock(renderer_lock)
                broadcast_to_users(sorted_user_ids, dict(payload))


@app.task(bind=True)
def broadcast_ai_provider_instance_update(self, model_availability_updated: bool):
    """Send public instance availability and staff provider state in bounded batches."""

    _run_ai_provider_renderer(
        _render_ai_provider_instance_update,
        _send_ai_provider_instance_update,
        model_availability_updated,
    )


def _render_ai_provider_instance_update(
    model_availability_updated: bool, renderer_lock
):
    """Render coherent public and privileged instance payloads."""

    from baserow.api.ai_provider.serializers import (
        AIProviderConfigSerializer,
        AIProviderFeatureSettingSerializer,
    )
    from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_KUMA
    from baserow.core.ai_provider.handler import AIProviderHandler
    from baserow.core.ai_provider.registries import (
        ai_provider_model_feature_type_registry,
    )
    from baserow.core.ai_provider.resolution import load_ai_provider_state

    _renew_ai_provider_renderer_lock(renderer_lock)
    state = load_ai_provider_state()[None]
    public_payload = None
    if model_availability_updated:
        # Non-staff clients only need the Kuma availability flip, not provider state.
        public_payload = {
            "type": "ai_provider_updated",
            "model_availability_updated": True,
            "instance_ai_features": {
                feature_type.type: {
                    "is_enabled": feature_type.get_workspace_availability(
                        None, state=state
                    )["is_enabled"]
                }
                for feature_type in ai_provider_model_feature_type_registry.get_all()
                if feature_type.type == AI_PROVIDER_FEATURE_KUMA
            },
        }

    payload = {
        "type": "ai_provider_updated",
        "model_availability_updated": model_availability_updated,
        "instance_ai_providers": list(
            AIProviderConfigSerializer(
                AIProviderHandler.list_providers(state=state), many=True
            ).data
        ),
        "instance_ai_provider_feature_settings": list(
            AIProviderFeatureSettingSerializer(
                AIProviderHandler.list_feature_settings(state=state),
                many=True,
                context={"workspace_id": None},
            ).data
        ),
    }
    return public_payload, payload


def _send_ai_provider_instance_update(rendered, renderer_lock) -> None:
    """Recipient-batch and send already-rendered instance payloads."""

    from django.contrib.auth import get_user_model

    from baserow.core.utils import grouper

    public_payload, payload = rendered
    if public_payload is not None:
        _renew_ai_provider_renderer_lock(renderer_lock)
        broadcast_to_users([], public_payload, send_to_all_users=True)

    staff_user_ids = (
        get_user_model()
        .objects.filter(is_active=True, is_staff=True)
        .order_by("id")
        .values_list("id", flat=True)
        .iterator(chunk_size=AI_PROVIDER_UPDATE_RECIPIENT_BATCH_SIZE)
    )
    for user_id_batch in grouper(
        AI_PROVIDER_UPDATE_RECIPIENT_BATCH_SIZE, staff_user_ids
    ):
        user_ids = list(user_id_batch)
        bounded_payload = _bounded_ai_provider_payload(
            user_ids,
            payload,
            _ai_provider_refresh_marker(
                None,
                model_availability_updated=payload["model_availability_updated"],
                refresh_workspace_availability=False,
                refresh_provider_settings=True,
            ),
        )
        _renew_ai_provider_renderer_lock(renderer_lock)
        broadcast_to_users(user_ids, dict(bounded_payload))


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
