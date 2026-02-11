import pytest
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.urls import reverse
from rest_framework.status import HTTP_204_NO_CONTENT

from baserow.config.asgi import application
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.msgpack import (
    MSG_PACK_MAX_INT,
    MSG_PACK_MAX_UINT,
    MSG_PACK_MIN_INT,
    normalize_msgpack_unsafe_values,
)
from baserow.ws.tasks import (
    broadcast_to_channel_group,
    broadcast_to_group,
    broadcast_to_groups,
    broadcast_to_users,
    broadcast_to_users_individual_payloads,
    force_disconnect_users,
)


# Unit tests for normalize_msgpack_unsafe_values function


def test_normalize_none():
    """Test that None values are preserved."""
    assert normalize_msgpack_unsafe_values(None) is None


def test_normalize_boolean():
    """Test that boolean values are preserved (not converted to integers)."""
    assert normalize_msgpack_unsafe_values(True) is True
    assert normalize_msgpack_unsafe_values(False) is False


def test_normalize_integers_within_range():
    """Test that integers within msgpack range are preserved."""
    # Test signed 64-bit boundaries
    assert normalize_msgpack_unsafe_values(MSG_PACK_MIN_INT) == MSG_PACK_MIN_INT
    assert normalize_msgpack_unsafe_values(MSG_PACK_MAX_INT) == MSG_PACK_MAX_INT
    
    # Test unsigned 64-bit boundary
    assert normalize_msgpack_unsafe_values(MSG_PACK_MAX_UINT) == MSG_PACK_MAX_UINT
    
    # Test zero and common values
    assert normalize_msgpack_unsafe_values(0) == 0
    assert normalize_msgpack_unsafe_values(1) == 1
    assert normalize_msgpack_unsafe_values(-1) == -1
    assert normalize_msgpack_unsafe_values(42) == 42
    assert normalize_msgpack_unsafe_values(-42) == -42


def test_normalize_integers_out_of_range():
    """Test that integers outside msgpack range are converted to strings."""
    # Test overflow (greater than max unsigned 64-bit)
    overflow_value = MSG_PACK_MAX_UINT + 1
    assert normalize_msgpack_unsafe_values(overflow_value) == str(overflow_value)
    
    # Test large overflow
    large_overflow = 2**64
    assert normalize_msgpack_unsafe_values(large_overflow) == str(large_overflow)
    
    # Test underflow (less than min signed 64-bit)
    underflow_value = MSG_PACK_MIN_INT - 1
    assert normalize_msgpack_unsafe_values(underflow_value) == str(underflow_value)
    
    # Test large underflow
    large_underflow = -(2**63) - 1
    assert normalize_msgpack_unsafe_values(large_underflow) == str(large_underflow)
    
    # Test the specific value from the bug report
    bug_value = 18446744073709551616  # 2^64
    assert normalize_msgpack_unsafe_values(bug_value) == str(bug_value)


def test_normalize_strings():
    """Test that strings are preserved."""
    assert normalize_msgpack_unsafe_values("") == ""
    assert normalize_msgpack_unsafe_values("hello") == "hello"
    assert normalize_msgpack_unsafe_values("123") == "123"
    assert normalize_msgpack_unsafe_values("true") == "true"


def test_normalize_floats():
    """Test that float values are preserved."""
    assert normalize_msgpack_unsafe_values(0.0) == 0.0
    assert normalize_msgpack_unsafe_values(1.5) == 1.5
    assert normalize_msgpack_unsafe_values(-1.5) == -1.5
    assert normalize_msgpack_unsafe_values(3.14159) == 3.14159


def test_normalize_lists():
    """Test that lists are recursively normalized."""
    # Simple list with valid integers
    assert normalize_msgpack_unsafe_values([1, 2, 3]) == [1, 2, 3]
    
    # List with overflow integers
    assert normalize_msgpack_unsafe_values([2**64, 1, 2]) == [str(2**64), 1, 2]
    
    # Nested lists
    assert normalize_msgpack_unsafe_values([[1, 2**64], [3, 4]]) == [
        [1, str(2**64)],
        [3, 4],
    ]
    
    # Mixed types
    assert normalize_msgpack_unsafe_values([1, "hello", 2**64, True, None]) == [
        1,
        "hello",
        str(2**64),
        True,
        None,
    ]
    
    # Empty list
    assert normalize_msgpack_unsafe_values([]) == []


def test_normalize_tuples():
    """Test that tuples are recursively normalized and type is preserved."""
    # Simple tuple with valid integers
    result = normalize_msgpack_unsafe_values((1, 2, 3))
    assert result == (1, 2, 3)
    assert isinstance(result, tuple)
    
    # Tuple with overflow integers
    result = normalize_msgpack_unsafe_values((2**64, 1, 2))
    assert result == (str(2**64), 1, 2)
    assert isinstance(result, tuple)
    
    # Nested tuples
    result = normalize_msgpack_unsafe_values(((1, 2**64), (3, 4)))
    assert result == ((1, str(2**64)), (3, 4))
    assert isinstance(result, tuple)
    assert isinstance(result[0], tuple)
    
    # Empty tuple
    result = normalize_msgpack_unsafe_values(())
    assert result == ()
    assert isinstance(result, tuple)


def test_normalize_sets():
    """Test that sets are converted to lists and normalized."""
    # Set with valid integers
    result = normalize_msgpack_unsafe_values({1, 2, 3})
    assert isinstance(result, list)
    assert set(result) == {1, 2, 3}
    
    # Set with overflow integer
    result = normalize_msgpack_unsafe_values({2**64, 1})
    assert isinstance(result, list)
    assert set(result) == {str(2**64), 1}
    
    # Frozenset
    result = normalize_msgpack_unsafe_values(frozenset({1, 2, 3}))
    assert isinstance(result, list)
    assert set(result) == {1, 2, 3}


def test_normalize_dicts():
    """Test that dictionaries are recursively normalized (both keys and values)."""
    # Simple dict with valid integers
    assert normalize_msgpack_unsafe_values({"a": 1, "b": 2}) == {"a": 1, "b": 2}
    
    # Dict with overflow integer values
    assert normalize_msgpack_unsafe_values({"overflow": 2**64, "normal": 1}) == {
        "overflow": str(2**64),
        "normal": 1,
    }
    
    # Dict with overflow integer keys
    result = normalize_msgpack_unsafe_values({2**64: "value", 1: "normal"})
    assert result == {str(2**64): "value", 1: "normal"}
    
    # Nested dicts
    assert normalize_msgpack_unsafe_values(
        {"outer": {"inner": 2**64, "normal": 1}, "value": 2}
    ) == {"outer": {"inner": str(2**64), "normal": 1}, "value": 2}
    
    # Mixed types in dict
    assert normalize_msgpack_unsafe_values(
        {
            "int": 42,
            "overflow": 2**64,
            "string": "hello",
            "bool": True,
            "none": None,
            "list": [1, 2**64],
            "nested": {"deep": -(2**63) - 1},
        }
    ) == {
        "int": 42,
        "overflow": str(2**64),
        "string": "hello",
        "bool": True,
        "none": None,
        "list": [1, str(2**64)],
        "nested": {"deep": str(-(2**63) - 1)},
    }
    
    # Empty dict
    assert normalize_msgpack_unsafe_values({}) == {}


def test_normalize_complex_nested_structure():
    """Test normalization of deeply nested complex structures."""
    complex_data = {
        "users": [
            {
                "id": 1,
                "large_id": 2**64,
                "metadata": {
                    "created": 1234567890,
                    "huge_timestamp": 2**65,
                    "tags": ["admin", "user"],
                    "counts": (100, 2**64, 300),
                },
            },
            {
                "id": 2,
                "negative_overflow": -(2**63) - 1,
                "flags": {True, False},
            },
        ],
        "summary": {
            "total": 2,
            "max_value": 2**100,
            "nested_list": [[1, 2], [3, 2**64]],
        },
    }
    
    expected = {
        "users": [
            {
                "id": 1,
                "large_id": str(2**64),
                "metadata": {
                    "created": 1234567890,
                    "huge_timestamp": str(2**65),
                    "tags": ["admin", "user"],
                    "counts": (100, str(2**64), 300),
                },
            },
            {
                "id": 2,
                "negative_overflow": str(-(2**63) - 1),
                "flags": [True, False],  # Set converted to list
            },
        ],
        "summary": {
            "total": 2,
            "max_value": str(2**100),
            "nested_list": [[1, 2], [3, str(2**64)]],
        },
    }
    
    result = normalize_msgpack_unsafe_values(complex_data)
    
    # Compare everything except the set (which becomes a list with unpredictable order)
    assert result["users"][0] == expected["users"][0]
    assert result["users"][1]["id"] == expected["users"][1]["id"]
    assert result["users"][1]["negative_overflow"] == expected["users"][1]["negative_overflow"]
    assert set(result["users"][1]["flags"]) == {True, False}
    assert result["summary"] == expected["summary"]


def test_normalize_edge_case_boundary_values():
    """Test exact boundary values for msgpack limits."""
    # Test exact boundaries (should NOT be converted)
    assert normalize_msgpack_unsafe_values(-(2**63)) == -(2**63)
    assert normalize_msgpack_unsafe_values(2**63 - 1) == 2**63 - 1
    assert normalize_msgpack_unsafe_values(2**64 - 1) == 2**64 - 1
    
    # Test one beyond boundaries (should be converted)
    assert normalize_msgpack_unsafe_values(-(2**63) - 1) == str(-(2**63) - 1)
    assert normalize_msgpack_unsafe_values(2**64) == str(2**64)


def test_normalize_issue_4309_exact_bug_value():
    """
    Regression test for issue #4309 - the exact value from the bug report.
    
    This test verifies that the specific value 18446744073709551616 (2^64)
    that caused the OverflowError in production is properly converted to a string.
    
    Without the fix, attempting to serialize this value with msgpack would fail with:
    OverflowError: Python int too large to convert to C unsigned long
    """
    bug_value = 18446744073709551616  # 2^64 from the bug report
    
    # The normalization function should convert this to a string
    result = normalize_msgpack_unsafe_values(bug_value)
    assert result == "18446744073709551616"
    assert isinstance(result, str)
    
    # Test in a nested structure (as it would appear in HTTP trigger payload)
    payload = {"overflow": bug_value}
    normalized = normalize_msgpack_unsafe_values(payload)
    assert normalized["overflow"] == "18446744073709551616"
    assert isinstance(normalized["overflow"], str)


def test_msgpack_serialization_would_fail_without_normalization():
    """
    This test demonstrates that msgpack CANNOT serialize out-of-range integers.
    
    This test proves that without our normalization fix, the bug would occur.
    We test that msgpack.packb() raises OverflowError for out-of-range integers,
    but works fine after normalization.
    """
    import msgpack
    
    # These values would cause OverflowError without normalization
    overflow_value = 2**64
    underflow_value = -(2**63) - 1
    bug_report_value = 18446744073709551616  # From issue #4309
    
    # Verify that msgpack CANNOT handle these values directly
    with pytest.raises(OverflowError):
        msgpack.packb({"value": overflow_value}, use_bin_type=True)
    
    with pytest.raises(OverflowError):
        msgpack.packb({"value": underflow_value}, use_bin_type=True)
    
    with pytest.raises(OverflowError):
        msgpack.packb({"value": bug_report_value}, use_bin_type=True)
    
    # But after normalization, it should work fine
    normalized_overflow = normalize_msgpack_unsafe_values({"value": overflow_value})
    normalized_underflow = normalize_msgpack_unsafe_values({"value": underflow_value})
    normalized_bug = normalize_msgpack_unsafe_values({"value": bug_report_value})
    
    # These should NOT raise OverflowError
    msgpack.packb(normalized_overflow, use_bin_type=True)
    msgpack.packb(normalized_underflow, use_bin_type=True)
    msgpack.packb(normalized_bug, use_bin_type=True)
    
    # Verify the values were converted to strings
    assert normalized_overflow["value"] == str(overflow_value)
    assert normalized_underflow["value"] == str(underflow_value)
    assert normalized_bug["value"] == str(bug_report_value)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_force_disconnect_users(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    response_2["web_socket_id"]

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
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    response_2["web_socket_id"]

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
async def test_broadcast_to_users_sanitizes_out_of_range_msgpack_integers(data_fixture):
    """
    Test that out-of-range integers are converted to strings during broadcast.
    
    This test would FAIL on the buggy version with:
    OverflowError: Integer value out of range
    
    The bug occurs because msgpack cannot serialize integers outside the range
    of signed/unsigned 64-bit integers.
    """
    user, token = data_fixture.create_user_and_token()

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    payload = {
        "overflow": 2**64,
        "nested": {
            "underflow": -(2**63) - 1,
            "within_range": [1, True, 2**64 - 1, -(2**63)],
        },
    }

    # Without the fix, this would raise OverflowError during msgpack serialization
    await sync_to_async(broadcast_to_users)([user.id], payload)
    response = await communicator.receive_json_from(0.1)

    assert response["overflow"] == str(2**64)
    assert response["nested"]["underflow"] == str(-(2**63) - 1)
    assert response["nested"]["within_range"] == [1, True, 2**64 - 1, -(2**63)]

    assert communicator.output_queue.qsize() == 0
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_issue_4309_http_trigger_with_unsigned_64bit_integer(
    data_fixture, api_client
):
    """
    Regression test for issue #4309.
    
    Test that HTTP trigger payloads containing unsigned 64-bit integers
    (e.g., 18446744073709551616) can be broadcast without OverflowError.
    
    Without the fix, this test would FAIL with:
    OverflowError: Python int too large to convert to C unsigned long
    
    The exact error from the bug report:
    File "msgpack/_packer.pyx", line 171, in msgpack._cmsgpack.Packer._pack_inner
    OverflowError: Python int too large to convert to C unsigned long
    """
    from baserow.contrib.automation.workflows.models import WorkflowState

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        user=user, automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger_node = data_fixture.create_http_trigger_node(
        workflow=workflow, service_kwargs={"is_public": False}
    )

    # Put the workflow in "waiting for test trigger" mode so a ?test=true webhook call
    # runs a simulation and broadcasts automation_node_updated with sample_data.
    await sync_to_async(AutomationWorkflowHandler().toggle_test_run)(
        workflow, simulate_until_node=trigger_node
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    url = reverse("api:http_trigger", kwargs={"webhook_uid": trigger_node.service.uid})
    overflow_payload = {"overflow": 18446744073709551616}

    response = await sync_to_async(api_client.post)(
        f"{url}?test=true",
        overflow_payload,
        format="json",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # There can be intermediary websocket events, so consume until we find node update.
    node_updated_event = None
    for _ in range(6):
        event = await communicator.receive_json_from(1)
        if event.get("type") == "automation_node_updated":
            node_updated_event = event
            break

    assert node_updated_event is not None
    sample_data = node_updated_event["node"]["service"]["sample_data"]["data"]["body"]

    assert sample_data["overflow"] == "18446744073709551616"
    assert isinstance(sample_data["overflow"], str)

    await communicator.disconnect()


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
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    response_2["web_socket_id"]

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

    await communicator_2.send_json_to({"page": "table", "table_id": table_3.id})
    response = await communicator_2.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "table"
    assert response["parameters"]["table_id"] == table_3.id

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
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    web_socket_id_2 = response_2["web_socket_id"]

    communicator_3 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_3}",
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
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    web_socket_id_2 = response_2["web_socket_id"]

    communicator_3 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_3}",
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
        f"ws/core/?jwt_token={token_4}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_4.connect()
    response_4 = await communicator_4.receive_json_from()
    web_socket_id_4 = response_4["web_socket_id"]

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
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
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
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    websocket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
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
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
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


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_users_individual_payloads_sanitizes_out_of_range_integers(
    data_fixture,
):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    await communicator_1.receive_json_from()

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    await communicator_2.receive_json_from()

    await sync_to_async(broadcast_to_users_individual_payloads)(
        {
            str(user_1.id): {"overflow": 2**64},
            str(user_2.id): {"underflow": -(2**63) - 1},
        }
    )

    response_1 = await communicator_1.receive_json_from(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)

    assert response_1 == {"overflow": str(2**64)}
    assert response_2 == {"underflow": str(-(2**63) - 1)}

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
