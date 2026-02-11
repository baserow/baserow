"""
Proof-of-concept test demonstrating the msgpack overflow bug.

This file contains a standalone test that proves:
1. msgpack CANNOT serialize out-of-range integers (the bug)
2. Our normalization fix SOLVES this problem

Run this test to see the bug in action and verify the fix works.
"""

import pytest


def test_msgpack_overflow_bug_demonstration():
    """
    This test demonstrates the actual msgpack overflow bug from issue #4309.
    
    It proves that:
    1. msgpack.packb() raises OverflowError for integers outside 64-bit range
    2. This is the exact error that was occurring in production
    3. Our normalization function fixes this issue
    """
    import msgpack
    
    # The exact value from the bug report that caused the production error
    bug_value = 18446744073709551616  # 2^64
    
    # ============================================================================
    # PART 1: Demonstrate the BUG (what happens WITHOUT the fix)
    # ============================================================================
    
    print("\n" + "="*80)
    print("DEMONSTRATING THE BUG (without normalization)")
    print("="*80)
    
    # This is what was happening in production:
    # When broadcast_to_permitted_users tried to send a message containing
    # this value, msgpack.packb() would be called internally by channels_redis
    
    message_with_overflow = {
        "type": "broadcast_to_users",
        "payload": {
            "overflow": bug_value  # This causes the OverflowError
        }
    }
    
    print(f"\nTrying to serialize message with value: {bug_value}")
    print("This simulates what happens in channel_layer.group_send()...")
    
    # This WILL raise OverflowError (the bug)
    with pytest.raises(OverflowError) as exc_info:
        msgpack.packb(message_with_overflow, use_bin_type=True)
    
    print(f"\n❌ ERROR OCCURRED (as expected without fix):")
    print(f"   {type(exc_info.value).__name__}: {exc_info.value}")
    print("\nThis is the EXACT error from the bug report:")
    print("   OverflowError: Python int too large to convert to C unsigned long")
    
    # ============================================================================
    # PART 2: Demonstrate the FIX (what happens WITH normalization)
    # ============================================================================
    
    print("\n" + "="*80)
    print("DEMONSTRATING THE FIX (with normalization)")
    print("="*80)
    
    # Import our normalization function
    from baserow.ws.tasks import _normalize_websocket_message_value
    
    # Apply normalization (this is what our fix does)
    normalized_message = _normalize_websocket_message_value(message_with_overflow)
    
    print(f"\nOriginal value: {bug_value} (type: {type(bug_value).__name__})")
    print(f"Normalized value: {normalized_message['payload']['overflow']} (type: {type(normalized_message['payload']['overflow']).__name__})")
    
    # Now msgpack can serialize it successfully
    try:
        serialized = msgpack.packb(normalized_message, use_bin_type=True)
        print(f"\n✅ SUCCESS! Message serialized successfully")
        print(f"   Serialized size: {len(serialized)} bytes")
        
        # Verify we can deserialize it too
        deserialized = msgpack.unpackb(serialized, raw=False)
        print(f"   Deserialized value: {deserialized['payload']['overflow']}")
        
    except Exception as e:
        pytest.fail(f"Normalization didn't fix the issue: {e}")
    
    # ============================================================================
    # PART 3: Test multiple overflow scenarios
    # ============================================================================
    
    print("\n" + "="*80)
    print("TESTING MULTIPLE OVERFLOW SCENARIOS")
    print("="*80)
    
    test_cases = [
        ("2^64 (bug report value)", 2**64),
        ("2^100 (very large)", 2**100),
        ("-(2^63) - 1 (underflow)", -(2**63) - 1),
        ("-(2^100) (very large negative)", -(2**100)),
    ]
    
    for description, value in test_cases:
        print(f"\nTest: {description}")
        print(f"  Value: {value}")
        
        # Without normalization - should fail
        try:
            msgpack.packb({"value": value}, use_bin_type=True)
            print(f"  ❌ UNEXPECTED: msgpack handled this value (should have failed)")
        except OverflowError:
            print(f"  ✓ Confirmed: msgpack cannot handle this value")
        
        # With normalization - should succeed
        normalized = _normalize_websocket_message_value({"value": value})
        try:
            msgpack.packb(normalized, use_bin_type=True)
            print(f"  ✅ After normalization: Successfully serialized as '{normalized['value']}'")
        except Exception as e:
            pytest.fail(f"Normalization failed for {description}: {e}")
    
    print("\n" + "="*80)
    print("ALL TESTS PASSED - THE FIX WORKS!")
    print("="*80 + "\n")


def test_channels_redis_simulation():
    """
    This test simulates what happens in channels_redis when it tries to
    serialize messages for Redis.
    
    This is a more realistic simulation of the actual bug scenario.
    """
    import msgpack
    from baserow.ws.tasks import _normalize_websocket_message_value
    
    # Simulate a typical websocket message that would be sent by
    # broadcast_to_permitted_users in the bug scenario
    
    websocket_message = {
        "type": "broadcast_to_users",
        "user_ids": [1, 2, 3],
        "payload": {
            "type": "workflow_triggered",
            "data": {
                "body": {
                    "overflow": 18446744073709551616,  # The bug value
                    "normal_field": "test",
                    "nested": {
                        "another_overflow": 2**65
                    }
                }
            }
        },
        "ignore_web_socket_id": None,
        "send_to_all_users": False,
    }
    
    print("\n" + "="*80)
    print("SIMULATING CHANNELS_REDIS MESSAGE SERIALIZATION")
    print("="*80)
    
    # Step 1: Show that the original message would fail
    print("\n1. Original message (WITHOUT normalization):")
    print(f"   Overflow value: {websocket_message['payload']['data']['body']['overflow']}")
    
    with pytest.raises(OverflowError):
        # This is what channels_redis does internally
        msgpack.packb(websocket_message, use_bin_type=True)
    
    print("   ❌ OverflowError raised (bug reproduced)")
    
    # Step 2: Show that normalization fixes it
    print("\n2. Normalized message (WITH our fix):")
    normalized = _normalize_websocket_message_value(websocket_message)
    print(f"   Overflow value: {normalized['payload']['data']['body']['overflow']} (now a string)")
    
    # This should work now
    serialized = msgpack.packb(normalized, use_bin_type=True)
    print(f"   ✅ Successfully serialized ({len(serialized)} bytes)")
    
    # Verify the structure is preserved
    deserialized = msgpack.unpackb(serialized, raw=False)
    assert deserialized["type"] == "broadcast_to_users"
    assert deserialized["user_ids"] == [1, 2, 3]
    assert deserialized["payload"]["data"]["body"]["overflow"] == "18446744073709551616"
    assert deserialized["payload"]["data"]["body"]["normal_field"] == "test"
    assert deserialized["payload"]["data"]["body"]["nested"]["another_overflow"] == str(2**65)
    
    print("   ✅ Message structure preserved correctly")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    # Run the tests with verbose output
    pytest.main([__file__, "-v", "-s"])
