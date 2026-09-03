from contextlib import contextmanager
from unittest.mock import patch

from django.db import DEFAULT_DB_ALIAS, connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_KUMA
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import (
    AIProviderConfig,
    AIProviderFeatureSetting,
    AIProviderModel,
    AIProviderWorkspaceOverride,
)
from baserow.core.ai_provider.registries import (
    ai_provider_model_feature_type_registry,
)
from baserow.core.db import IsolationLevel
from baserow.core.models import WORKSPACE_USER_PERMISSION_MEMBER
from baserow.ws.tasks import (
    broadcast_ai_provider_instance_update,
    broadcast_ai_provider_update,
    broadcast_to_channel_group,
    broadcast_to_group,
    broadcast_to_groups,
    broadcast_to_users,
    broadcast_to_users_individual_payloads,
    force_disconnect_users,
)


@pytest.mark.django_db
def test_workspace_ai_provider_update_payloads_are_complete_permission_scoped_and_bounded(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    staff = data_fixture.create_user(is_staff=True)
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    outsider = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    data_fixture.create_user_workspace(
        user=member,
        workspace=workspace,
        permissions=WORKSPACE_USER_PERMISSION_MEMBER,
    )
    AIProviderHandler.create_provider(
        "openai",
        api_key="instance-secret",
        extra_settings={"organization": "instance-organization"},
        models_data=[{"model_identifier": "gpt-5"}],
    )

    with (
        patch("baserow.ws.tasks.AI_PROVIDER_UPDATE_RECIPIENT_BATCH_SIZE", 1),
        patch("baserow.ws.tasks.broadcast_to_users") as mock_broadcast,
    ):
        broadcast_ai_provider_update(workspace.id, True)

    payloads_by_user = {
        user_id: payload
        for call in mock_broadcast.call_args_list
        for user_id in call.args[0]
        for payload in [call.args[1]]
    }
    workspace_key = str(workspace.id)
    expected_ai_features = (
        ai_provider_model_feature_type_registry.get_workspace_availability(workspace)
    )

    assert outsider.id not in payloads_by_user
    assert staff.id not in payloads_by_user
    assert all(len(call.args[0]) <= 1 for call in mock_broadcast.call_args_list)
    assert payloads_by_user[member.id] == {
        "type": "ai_provider_updated",
        "model_availability_updated": True,
        "generative_ai_models_enabled_by_workspace": {
            workspace_key: {"openai": ["gpt-5"]}
        },
        "ai_features_by_workspace": {workspace_key: expected_ai_features},
    }

    admin_payload = payloads_by_user[admin.id]
    assert admin_payload["generative_ai_models_enabled_by_workspace"] == {
        workspace_key: {"openai": ["gpt-5"]}
    }
    workspace_providers = admin_payload["ai_providers_by_workspace"][workspace_key]
    assert workspace_providers[0]["provider_type"] == "openai"
    assert workspace_providers[0]["extra_settings"] == {}
    workspace_feature_settings = admin_payload[
        "ai_provider_feature_settings_by_workspace"
    ][workspace_key]
    assert [setting["feature_type"] for setting in workspace_feature_settings] == [
        "kuma"
    ]

    assert "instance_ai_providers" not in admin_payload


@pytest.mark.django_db
def test_workspace_ai_provider_metadata_update_only_notifies_permitted_users(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    data_fixture.create_user_workspace(
        user=member,
        workspace=workspace,
        permissions=WORKSPACE_USER_PERMISSION_MEMBER,
    )

    with patch("baserow.ws.tasks.broadcast_to_users") as mock_broadcast:
        broadcast_ai_provider_update(workspace.id, False)

    mock_broadcast.assert_called_once()
    assert mock_broadcast.call_args.args[0] == [admin.id]
    payload = mock_broadcast.call_args.args[1]
    assert payload["model_availability_updated"] is False
    assert "generative_ai_models_enabled_by_workspace" not in payload
    assert "ai_features_by_workspace" not in payload
    assert str(workspace.id) in payload["ai_providers_by_workspace"]
    assert str(workspace.id) in payload["ai_provider_feature_settings_by_workspace"]


@pytest.mark.django_db
def test_oversized_workspace_ai_provider_payloads_use_permission_scoped_markers(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    data_fixture.create_user_workspace(
        user=member,
        workspace=workspace,
        permissions=WORKSPACE_USER_PERMISSION_MEMBER,
    )

    with (
        patch("baserow.ws.tasks.AI_PROVIDER_UPDATE_MAX_ENVELOPE_BYTES", 1),
        patch("baserow.ws.tasks.broadcast_to_users") as mock_broadcast,
    ):
        broadcast_ai_provider_update(workspace.id, True)

    payloads_by_user = {
        user_id: call.args[1]
        for call in mock_broadcast.call_args_list
        for user_id in call.args[0]
    }
    assert payloads_by_user[member.id] == {
        "type": "ai_provider_updated",
        "model_availability_updated": True,
        "requires_refresh": True,
        "workspace_id": workspace.id,
        "refresh_workspace_availability": True,
        "refresh_provider_settings": False,
    }
    assert payloads_by_user[admin.id] == {
        **payloads_by_user[member.id],
        "refresh_provider_settings": True,
    }


@pytest.mark.django_db(transaction=True)
def test_ai_provider_renderer_is_primary_repeatable_and_cross_worker_locked(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    events = []

    @contextmanager
    def tracked_snapshot():
        events.append("snapshot_entered")
        yield
        events.append("snapshot_exited")

    with (
        patch("django.core.cache.cache.lock") as mock_cache_lock,
        patch(
            "baserow.config.db_routers.set_db_alias",
            return_value=DEFAULT_DB_ALIAS,
        ) as mock_set_db_alias,
        patch(
            "baserow.core.db.transaction_atomic", return_value=tracked_snapshot()
        ) as mock_atomic,
        patch(
            "baserow.ws.tasks.broadcast_to_users",
            side_effect=lambda *_args, **_kwargs: events.append("sent"),
        ),
    ):
        broadcast_ai_provider_update(workspace.id, True)

    lock = mock_cache_lock.return_value
    lock.acquire.assert_called_once_with()
    lock.reacquire.assert_called()
    lock.release.assert_called_once_with()
    mock_set_db_alias.assert_called_with(DEFAULT_DB_ALIAS)
    mock_atomic.assert_called_once_with(
        using=DEFAULT_DB_ALIAS,
        isolation_level=IsolationLevel.REPEATABLE_READ,
    )
    assert events.index("snapshot_exited") < events.index("sent")


@pytest.mark.django_db
def test_instance_ai_provider_update_schedules_bounded_workspace_batches(
    data_fixture,
):
    workspaces = [data_fixture.create_workspace() for _ in range(5)]

    with (
        patch("baserow.ws.tasks.AI_PROVIDER_UPDATE_WORKSPACE_BATCH_SIZE", 2),
        patch(
            "baserow.ws.tasks.broadcast_ai_provider_workspace_update_batch.delay"
        ) as mock_workspace_batch,
        patch(
            "baserow.ws.tasks.broadcast_ai_provider_instance_update.delay"
        ) as mock_instance_update,
    ):
        broadcast_ai_provider_update(None, True)

    assert [call.args for call in mock_workspace_batch.call_args_list] == [
        ([workspaces[0].id, workspaces[1].id], True),
        ([workspaces[2].id, workspaces[3].id], True),
        ([workspaces[4].id], True),
    ]
    mock_instance_update.assert_called_once_with(True)


@pytest.mark.django_db
def test_instance_ai_provider_update_payload_is_staff_only_and_bounded(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    staff_users = [data_fixture.create_user(is_staff=True) for _ in range(3)]
    inactive_staff = data_fixture.create_user(is_staff=True, is_active=False)
    data_fixture.create_user()
    AIProviderHandler.create_provider(
        "openai",
        api_key="instance-secret",
        extra_settings={"organization": "instance-organization"},
        models_data=[{"model_identifier": "gpt-5"}],
    )

    with (
        patch("baserow.ws.tasks.AI_PROVIDER_UPDATE_RECIPIENT_BATCH_SIZE", 2),
        patch("baserow.ws.tasks.broadcast_to_users") as mock_broadcast,
    ):
        broadcast_ai_provider_instance_update(False)

    recipient_batches = [call.args[0] for call in mock_broadcast.call_args_list]
    assert recipient_batches == [
        [staff_users[0].id, staff_users[1].id],
        [staff_users[2].id],
    ]
    assert inactive_staff.id not in {
        user_id for recipient_batch in recipient_batches for user_id in recipient_batch
    }
    assert all(len(recipient_batch) <= 2 for recipient_batch in recipient_batches)

    for call in mock_broadcast.call_args_list:
        payload = call.args[1]
        assert payload["type"] == "ai_provider_updated"
        assert payload["model_availability_updated"] is False
        assert payload["instance_ai_providers"][0]["provider_type"] == "openai"
        assert payload["instance_ai_providers"][0]["extra_settings"] == {
            "organization": "instance-organization"
        }
        assert [
            setting["feature_type"]
            for setting in payload["instance_ai_provider_feature_settings"]
        ] == ["kuma"]


@pytest.mark.django_db
def test_oversized_instance_provider_payload_uses_staff_only_refresh_marker(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    staff = data_fixture.create_user(is_staff=True)
    data_fixture.create_user()

    with (
        patch("baserow.ws.tasks.AI_PROVIDER_UPDATE_MAX_ENVELOPE_BYTES", 1),
        patch("baserow.ws.tasks.broadcast_to_users") as mock_broadcast,
    ):
        broadcast_ai_provider_instance_update(True)

    public_call = next(
        call
        for call in mock_broadcast.call_args_list
        if call.kwargs.get("send_to_all_users") is True
    )
    assert "instance_ai_features" in public_call.args[1]

    staff_call = next(
        call for call in mock_broadcast.call_args_list if staff.id in call.args[0]
    )
    assert staff_call.args[1] == {
        "type": "ai_provider_updated",
        "model_availability_updated": True,
        "requires_refresh": True,
        "workspace_id": None,
        "refresh_workspace_availability": False,
        "refresh_provider_settings": True,
    }


@pytest.mark.django_db
def test_instance_ai_provider_availability_update_reaches_every_connected_user(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    data_fixture.create_user(is_staff=True)
    data_fixture.create_user()

    with patch("baserow.ws.tasks.broadcast_to_users") as mock_broadcast:
        broadcast_ai_provider_instance_update(True)

    public_calls = [
        call
        for call in mock_broadcast.call_args_list
        if call.kwargs.get("send_to_all_users") is True
    ]
    assert len(public_calls) == 1
    public_call = public_calls[0]
    assert public_call.args[0] == []
    assert public_call.args[1] == {
        "type": "ai_provider_updated",
        "model_availability_updated": True,
        "instance_ai_features": {
            AI_PROVIDER_FEATURE_KUMA: {
                "is_enabled": ai_provider_model_feature_type_registry.get(
                    AI_PROVIDER_FEATURE_KUMA
                ).get_workspace_availability(None)["is_enabled"]
            }
        },
    }
    assert "ai_fields" not in public_call.args[1]["instance_ai_features"]

    staff_calls = [
        call
        for call in mock_broadcast.call_args_list
        if call.kwargs.get("send_to_all_users") is not True
    ]
    assert staff_calls
    assert all("instance_ai_features" not in call.args[1] for call in staff_calls)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_force_disconnect_users(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    await sync_to_async(force_disconnect_users)([user_1.id])
    await communicator_2.receive_nothing(0.1)

    payload = await communicator_1.receive_output(0.1)
    assert payload["type"] == "websocket.send"
    assert payload["text"] == '{"type": "force_disconnect"}'

    payload = await communicator_1.receive_output(0.1)
    assert payload["type"] == "websocket.close"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_users(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = "ws-1"

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    await sync_to_async(broadcast_to_users)([user_1.id], {"message": "test"})
    response_1 = await communicator_1.receive_json_from(0.1)
    await communicator_2.receive_nothing(0.1)
    assert response_1["message"] == "test"

    await sync_to_async(broadcast_to_users)(
        [user_1.id, user_2.id],
        {"message": "test"},
        ignore_web_socket_id=web_socket_id_1,
    )
    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2["message"] == "test"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_channel_group(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(users=[user_1, user_2])
    database = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(user=user_1)
    table_2 = data_fixture.create_database_table(user=user_2)
    table_3 = data_fixture.create_database_table(database=database)

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = "ws-1"

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    # We don't expect any communicator to receive anything because they didn't join a
    # workspace.
    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_1.id}", {"message": "nothing2"}
    )
    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)

    # User 1 is not allowed to join table 2 so we don't expect any response.
    await communicator_1.send_json_to({"page": "table", "table_id": table_2.id})
    await communicator_1.receive_nothing(0.1)

    # Because user 1 did not join table 2 we don't expect anything
    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_2.id}", {"message": "nothing"}
    )
    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)

    # Join the table page.
    await communicator_1.send_json_to({"page": "table", "table_id": table_1.id})
    response = await communicator_1.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "table"
    assert response["parameters"]["table_id"] == table_1.id
    members_resp = await communicator_1.receive_json_from(0.1)
    assert members_resp["type"] == "presence.members"

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_1.id}", {"message": "test"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    assert response_1["message"] == "test"
    await communicator_2.receive_nothing(0.1)

    await communicator_1.send_json_to({"page": "table", "table_id": table_3.id})

    response = await communicator_1.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "table"
    assert response["parameters"]["table_id"] == table_3.id
    members_resp = await communicator_1.receive_json_from(0.1)
    assert members_resp["type"] == "presence.members"

    await communicator_2.send_json_to({"page": "table", "table_id": table_3.id})
    response = await communicator_2.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "table"
    assert response["parameters"]["table_id"] == table_3.id
    members_resp = await communicator_2.receive_json_from(0.1)
    assert members_resp["type"] == "presence.members"
    # comm_1 receives presence.join when comm_2 subscribes to the same table
    join = await communicator_1.receive_json_from(0.1)
    assert join["type"] == "presence.join"

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_3.id}", {"message": "test2"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    assert response_1["message"] == "test2"
    response_1 = await communicator_2.receive_json_from(0.1)
    assert response_1["message"] == "test2"

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_3.id}", {"message": "test3"}, web_socket_id_1
    )
    await communicator_1.receive_nothing(0.1)
    response_1 = await communicator_2.receive_json_from(0.1)
    assert response_1["message"] == "test3"

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_2.id}", {"message": "test4"}
    )
    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_workspace(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    user_3, token_3 = data_fixture.create_user_and_token()
    user_4, token_4 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(users=[user_1, user_2, user_4])
    workspace_2 = data_fixture.create_workspace(users=[user_2, user_3])

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = "ws-1"

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    web_socket_id_2 = "ws-2"

    communicator_3 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_3}&web_socket_id=ws-3",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_3.connect()
    await communicator_3.receive_json_from()

    await database_sync_to_async(broadcast_to_group)(
        workspace_1.id, {"message": "test"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_1["message"] == "test"
    assert response_2["message"] == "test"

    await database_sync_to_async(broadcast_to_group)(
        workspace_1.id, {"message": "test2"}, ignore_web_socket_id=web_socket_id_1
    )

    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_2["message"] == "test2"

    await database_sync_to_async(broadcast_to_group)(
        workspace_2.id, {"message": "test3"}, ignore_web_socket_id=web_socket_id_2
    )

    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)
    await communicator_3.receive_json_from(0.1)

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0
    assert communicator_3.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()
    await communicator_3.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_workspaces(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    user_3, token_3 = data_fixture.create_user_and_token()
    user_4, token_4 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(users=[user_1, user_2, user_4])
    workspace_2 = data_fixture.create_workspace(users=[user_2, user_3])

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = "ws-1"

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    web_socket_id_2 = "ws-2"

    communicator_3 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_3}&web_socket_id=ws-3",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_3.connect()
    await communicator_3.receive_json_from()

    await database_sync_to_async(broadcast_to_groups)(
        [workspace_1.id], {"message": "test"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_1["message"] == "test"
    assert response_2["message"] == "test"

    await database_sync_to_async(broadcast_to_groups)(
        [workspace_1.id], {"message": "test2"}, ignore_web_socket_id=web_socket_id_1
    )

    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_2["message"] == "test2"

    communicator_4 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_4}&web_socket_id=ws-4",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_4.connect()
    response_4 = await communicator_4.receive_json_from()
    web_socket_id_4 = "ws-4"

    await database_sync_to_async(broadcast_to_groups)(
        [workspace_1.id, workspace_2.id],
        {"message": "test3"},
        ignore_web_socket_id=web_socket_id_4,
    )

    await communicator_1.receive_json_from(0.1)
    await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_json_from(0.1)
    await communicator_4.receive_nothing(0.1)

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0
    assert communicator_3.output_queue.qsize() == 0
    assert communicator_4.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()
    await communicator_3.disconnect()
    await communicator_4.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_can_broadcast_to_every_single_user(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    await sync_to_async(broadcast_to_users)(
        [], {"message": "test"}, send_to_all_users=True
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    await communicator_2.receive_nothing(0.1)
    assert response_1["message"] == "test"

    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2["message"] == "test"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_can_still_ignore_when_sending_to_all_users(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    websocket_id_1 = "ws-1"

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    await sync_to_async(broadcast_to_users)(
        [],
        {"message": "test"},
        ignore_web_socket_id=websocket_id_1,
        send_to_all_users=True,
    )
    await communicator_1.receive_nothing(0.1)

    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2["message"] == "test"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_users_individual_payloads(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = "ws-1"

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}&web_socket_id=ws-2",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    # Assert each user gets a unique message
    await sync_to_async(broadcast_to_users_individual_payloads)(
        {str(user_1.id): "payload1", str(user_2.id): "payload2"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    assert response_1 == "payload1"

    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2 == "payload2"

    # Assert we can ignore a websocket for one user
    await sync_to_async(broadcast_to_users_individual_payloads)(
        {str(user_1.id): "payload1", str(user_2.id): "payload2"},
        ignore_web_socket_id=web_socket_id_1,
    )
    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2 == "payload2"

    # Assert not including a user id wont send them anything
    await sync_to_async(broadcast_to_users_individual_payloads)(
        {str(user_2.id): "payload2"},
    )
    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2 == "payload2"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.django_db
def test_broadcast_application_created_does_not_fail_for_trashed_applications(
    data_fixture,
):
    from baserow.ws.tasks import broadcast_application_created

    application = data_fixture.create_database_application()
    application.trashed = True
    application.save()

    try:
        broadcast_application_created(application.id)
    except Exception as e:
        pytest.fail(f"broadcast_application_created raised an exception: {e}")


@pytest.mark.django_db
def test_broadcast_to_permitted_users_does_not_fail_for_trashed_objects(data_fixture):
    from baserow.ws.tasks import broadcast_to_permitted_users

    user_1, token_1 = data_fixture.create_user_and_token()

    workspace = data_fixture.create_workspace(users=[user_1])
    application = data_fixture.create_database_application(workspace=workspace)

    workspace.trashed = True
    workspace.save()

    try:
        broadcast_to_permitted_users(
            workspace.id,
            "workspace.create_application",
            "application",
            application.id,
            {},
            None,
        )
    except Exception as e:
        pytest.fail(f"broadcast_to_permitted_users raised an exception: {e}")

    # Now let's try with a deleted scope
    workspace.trashed = False
    workspace.save()

    application_id = application.id
    application.delete()

    try:
        broadcast_to_permitted_users(
            workspace.id,
            "workspace.create_application",
            "application",
            application_id,
            {},
            None,
        )
    except Exception as e:
        pytest.fail(f"broadcast_to_permitted_users raised an exception: {e}")


@pytest.mark.django_db
@override_settings(BASEROW_REALTIME_REPLAY_MAX_EVENTS=0)
def test_cleanup_task_skips_query_when_recording_disabled(django_assert_num_queries):
    from baserow.ws.tasks import cleanup_old_realtime_events

    # With recording disabled the periodic task must not touch the database.
    with django_assert_num_queries(0):
        cleanup_old_realtime_events()


@pytest.mark.django_db
@override_settings(BASEROW_REALTIME_REPLAY_MAX_EVENTS=5)
def test_cleanup_task_runs_when_recording_enabled():
    from baserow.ws.models import RealtimeEvent
    from baserow.ws.tasks import cleanup_old_realtime_events

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ws_realtime_events "
            "(channel_group, payload, created_at) "
            "VALUES (%s, %s, now() - interval '60 days') RETURNING id",
            ["table-1", '{"type": "x"}'],
        )
        old_id = cursor.fetchone()[0]

    cleanup_old_realtime_events()

    assert not RealtimeEvent.objects.filter(id=old_id).exists()


@pytest.mark.django_db
def test_workspace_ai_provider_broadcast_reuses_the_loaded_provider_state(
    data_fixture, settings
):
    """
    The broadcast loads every scope up front, so serializing the providers of a
    workspace must not go back to the provider tables per workspace.
    """

    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_USE_LOCAL_CACHE = False
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    AIProviderHandler.create_provider(
        "openai",
        api_key="instance-secret",
        models_data=[{"model_identifier": "gpt-5"}],
    )

    with patch("baserow.ws.tasks.broadcast_to_users"):
        with CaptureQueriesContext(connection) as queries:
            broadcast_ai_provider_update(workspace.id, True)

    provider_tables = {
        AIProviderConfig._meta.db_table,
        AIProviderModel._meta.db_table,
        AIProviderFeatureSetting._meta.db_table,
        AIProviderWorkspaceOverride._meta.db_table,
    }
    provider_queries = [
        query["sql"]
        for query in queries.captured_queries
        if any(table in query["sql"] for table in provider_tables)
    ]
    assert len(provider_queries) == 4, provider_queries


@pytest.mark.django_db
def test_broadcast_keeps_instance_disabled_providers_and_models_private(
    data_fixture, settings
):
    """
    A workspace must never learn about an instance provider its admin disabled, nor
    about the individual models disabled on an active one.
    """

    settings.FEATURE_FLAGS = ["ai-providers"]
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    inactive_provider = AIProviderHandler.create_provider(
        "anthropic",
        api_key="hidden-secret",
        models_data=[{"model_identifier": "hidden-model"}],
    )
    AIProviderHandler.update_provider(inactive_provider, is_active=False)
    active_provider = AIProviderHandler.create_provider(
        "openai",
        api_key="instance-secret",
        models_data=[{"model_identifier": "gpt-5"}],
    )
    disabled_model = AIProviderModel.objects.create(
        provider_config=active_provider,
        model_identifier="disabled-model",
        is_enabled=False,
    )

    with patch("baserow.ws.tasks.broadcast_to_users") as mock_broadcast:
        broadcast_ai_provider_update(workspace.id, True)

    payload = next(
        call.args[1]
        for call in mock_broadcast.call_args_list
        if "ai_providers_by_workspace" in call.args[1]
    )
    providers = payload["ai_providers_by_workspace"][str(workspace.id)]

    assert [provider["provider_type"] for provider in providers] == ["openai"]
    assert [model["model_identifier"] for model in providers[0]["models"]] == ["gpt-5"]
    assert disabled_model.id not in [model["id"] for model in providers[0]["models"]]
