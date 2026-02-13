"""
Tests for baserow.core.serialization — payload normalization for safe msgpack
serialization.

These tests verify that:
1. Integers exceeding the msgpack uint64 max (2^64 - 1) are converted to strings
2. Integers below the msgpack int64 min (-(2^63)) are converted to strings
3. Integers within the safe range are preserved as-is
4. Booleans (which are int subclasses in Python) are not affected
5. Other types (strings, floats, None) pass through unchanged
6. Nested structures (dicts, lists, tuples) are recursively normalized
7. The actual msgpack serialization succeeds after normalization
"""

import msgpack
import pytest

from baserow.core.serialization import (
    MSGPACK_INT_MAX,
    MSGPACK_INT_MIN,
    normalize_payload_for_serialization,
    normalize_value_for_serialization,
)


class TestNormalizeValueForSerialization:
    """Tests for the single-value normalization function."""

    def test_safe_positive_integer_unchanged(self):
        assert normalize_value_for_serialization(42) == 42
        assert isinstance(normalize_value_for_serialization(42), int)

    def test_safe_negative_integer_unchanged(self):
        assert normalize_value_for_serialization(-100) == -100
        assert isinstance(normalize_value_for_serialization(-100), int)

    def test_zero_unchanged(self):
        assert normalize_value_for_serialization(0) == 0
        assert isinstance(normalize_value_for_serialization(0), int)

    def test_max_safe_integer_unchanged(self):
        result = normalize_value_for_serialization(MSGPACK_INT_MAX)
        assert result == MSGPACK_INT_MAX
        assert isinstance(result, int)

    def test_min_safe_integer_unchanged(self):
        result = normalize_value_for_serialization(MSGPACK_INT_MIN)
        assert result == MSGPACK_INT_MIN
        assert isinstance(result, int)

    def test_overflow_positive_converted_to_string(self):
        overflow = MSGPACK_INT_MAX + 1  # 2^64 = 18446744073709551616
        result = normalize_value_for_serialization(overflow)
        assert result == str(overflow)
        assert isinstance(result, str)

    def test_overflow_negative_converted_to_string(self):
        underflow = MSGPACK_INT_MIN - 1  # -(2^63) - 1
        result = normalize_value_for_serialization(underflow)
        assert result == str(underflow)
        assert isinstance(result, str)

    def test_very_large_positive_converted_to_string(self):
        huge = 10**100
        result = normalize_value_for_serialization(huge)
        assert result == str(huge)
        assert isinstance(result, str)

    def test_very_large_negative_converted_to_string(self):
        huge_neg = -(10**100)
        result = normalize_value_for_serialization(huge_neg)
        assert result == str(huge_neg)
        assert isinstance(result, str)

    def test_boolean_true_unchanged(self):
        result = normalize_value_for_serialization(True)
        assert result is True
        assert isinstance(result, bool)

    def test_boolean_false_unchanged(self):
        result = normalize_value_for_serialization(False)
        assert result is False
        assert isinstance(result, bool)

    def test_string_unchanged(self):
        assert normalize_value_for_serialization("hello") == "hello"

    def test_float_unchanged(self):
        assert normalize_value_for_serialization(3.14) == 3.14

    def test_none_unchanged(self):
        assert normalize_value_for_serialization(None) is None


class TestNormalizePayloadForSerialization:
    """Tests for the recursive payload normalization function."""

    def test_flat_dict_with_safe_values(self):
        payload = {"name": "test", "count": 42, "active": True}
        result = normalize_payload_for_serialization(payload)
        assert result == payload

    def test_flat_dict_with_overflow_integer(self):
        overflow = 18446744073709551616  # 2^64
        payload = {"overflow": overflow, "safe": 42}
        result = normalize_payload_for_serialization(payload)
        assert result == {"overflow": "18446744073709551616", "safe": 42}

    def test_nested_dict_with_overflow(self):
        overflow = 18446744073709551616
        payload = {
            "level1": {
                "level2": {
                    "big_number": overflow,
                    "normal": "hello",
                }
            }
        }
        result = normalize_payload_for_serialization(payload)
        assert result["level1"]["level2"]["big_number"] == str(overflow)
        assert result["level1"]["level2"]["normal"] == "hello"

    def test_list_with_overflow(self):
        overflow = 18446744073709551616
        payload = [1, 2, overflow, 4]
        result = normalize_payload_for_serialization(payload)
        assert result == [1, 2, str(overflow), 4]
        assert isinstance(result, list)

    def test_tuple_preserved_as_tuple(self):
        overflow = 18446744073709551616
        payload = (1, overflow, 3)
        result = normalize_payload_for_serialization(payload)
        assert result == (1, str(overflow), 3)
        assert isinstance(result, tuple)

    def test_dict_with_list_values(self):
        overflow = 18446744073709551616
        payload = {
            "items": [
                {"id": 1, "value": overflow},
                {"id": 2, "value": 100},
            ]
        }
        result = normalize_payload_for_serialization(payload)
        assert result["items"][0]["value"] == str(overflow)
        assert result["items"][1]["value"] == 100

    def test_empty_structures(self):
        assert normalize_payload_for_serialization({}) == {}
        assert normalize_payload_for_serialization([]) == []
        assert normalize_payload_for_serialization(()) == ()

    def test_mixed_overflow_and_underflow(self):
        payload = {
            "too_big": MSGPACK_INT_MAX + 1,
            "too_small": MSGPACK_INT_MIN - 1,
            "just_right_max": MSGPACK_INT_MAX,
            "just_right_min": MSGPACK_INT_MIN,
        }
        result = normalize_payload_for_serialization(payload)
        assert isinstance(result["too_big"], str)
        assert isinstance(result["too_small"], str)
        assert isinstance(result["just_right_max"], int)
        assert isinstance(result["just_right_min"], int)

    def test_does_not_mutate_original(self):
        overflow = 18446744073709551616
        original = {"value": overflow, "nested": {"inner": overflow}}
        normalize_payload_for_serialization(original)
        # Original should be unchanged
        assert original["value"] == overflow
        assert isinstance(original["value"], int)

    def test_realistic_http_trigger_payload(self):
        """Simulates the exact payload structure from an HTTP trigger."""
        payload = {
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "query_params": {},
            "body": {
                "user_id": 12345,
                "transaction_id": 18446744073709551616,
                "amount": 99.99,
                "description": "Test payment",
                "metadata": {
                    "tracking_code": 99999999999999999999999,
                },
            },
            "raw_body": '{"user_id": 12345, "transaction_id": 18446744073709551616}',
            "remote_addr": "127.0.0.1",
            "user_agent": "TestClient/1.0",
        }
        result = normalize_payload_for_serialization(payload)
        assert result["body"]["user_id"] == 12345
        assert result["body"]["transaction_id"] == "18446744073709551616"
        assert result["body"]["amount"] == 99.99
        assert result["body"]["metadata"]["tracking_code"] == str(
            99999999999999999999999
        )
        # raw_body is a string, so it passes through unchanged
        assert result["raw_body"] == payload["raw_body"]


class TestMsgpackSerializationSafety:
    """
    Tests that verify the actual msgpack serialization succeeds after
    normalization. These tests demonstrate the concrete failure mode
    that this fix addresses.
    """

    def test_overflow_integer_fails_msgpack_without_normalization(self):
        """
        Proves the bug: msgpack cannot serialize integers > uint64 max.
        This test FAILS on the buggy version (before the fix) because
        it demonstrates the OverflowError that crashes websocket broadcasts.
        """
        overflow_payload = {"overflow": 18446744073709551616}
        with pytest.raises(OverflowError):
            msgpack.packb(overflow_payload)

    def test_underflow_integer_fails_msgpack_without_normalization(self):
        """Proves msgpack also fails for integers below int64 min."""
        underflow_payload = {"underflow": -(2**63) - 1}
        with pytest.raises(OverflowError):
            msgpack.packb(underflow_payload)

    def test_normalized_overflow_succeeds_msgpack(self):
        """After normalization, the payload serializes without error."""
        overflow_payload = {"overflow": 18446744073709551616}
        normalized = normalize_payload_for_serialization(overflow_payload)
        # This must not raise
        packed = msgpack.packb(normalized)
        unpacked = msgpack.unpackb(packed)
        assert unpacked["overflow"] == "18446744073709551616"

    def test_normalized_underflow_succeeds_msgpack(self):
        """After normalization, negative overflow also serializes safely."""
        underflow_payload = {"underflow": -(2**63) - 1}
        normalized = normalize_payload_for_serialization(underflow_payload)
        packed = msgpack.packb(normalized)
        unpacked = msgpack.unpackb(packed)
        assert unpacked["underflow"] == str(-(2**63) - 1)

    def test_safe_integers_roundtrip_through_msgpack(self):
        """Safe integers survive msgpack round-trip as integers."""
        payload = {"positive": 42, "negative": -100, "zero": 0}
        normalized = normalize_payload_for_serialization(payload)
        packed = msgpack.packb(normalized)
        unpacked = msgpack.unpackb(packed)
        assert unpacked["positive"] == 42
        assert unpacked["negative"] == -100
        assert unpacked["zero"] == 0

    def test_complex_nested_payload_survives_msgpack(self):
        """
        A realistic nested payload with mixed types including overflow
        integers successfully serializes after normalization.
        """
        payload = {
            "type": "broadcast_to_users",
            "user_ids": [1, 2, 3],
            "payload": {
                "type": "automation_data",
                "body": {
                    "normal_int": 42,
                    "big_int": 18446744073709551616,
                    "nested": [
                        {"value": -(2**63) - 1},
                        {"value": "safe_string"},
                        {"value": True},
                    ],
                },
            },
        }
        normalized = normalize_payload_for_serialization(payload)
        # Must not raise
        packed = msgpack.packb(normalized)
        unpacked = msgpack.unpackb(packed)
        inner = unpacked["payload"]["body"]
        assert inner["normal_int"] == 42
        assert inner["big_int"] == "18446744073709551616"
        assert inner["nested"][0]["value"] == str(-(2**63) - 1)

    def test_boundary_values_at_exact_limits(self):
        """Test the exact boundary values of msgpack's integer range."""
        payload = {
            "max_uint64": MSGPACK_INT_MAX,
            "min_int64": MSGPACK_INT_MIN,
            "max_plus_one": MSGPACK_INT_MAX + 1,
            "min_minus_one": MSGPACK_INT_MIN - 1,
        }
        normalized = normalize_payload_for_serialization(payload)

        # Boundary values should remain as integers
        assert isinstance(normalized["max_uint64"], int)
        assert isinstance(normalized["min_int64"], int)
        # Just outside boundary should be strings
        assert isinstance(normalized["max_plus_one"], str)
        assert isinstance(normalized["min_minus_one"], str)

        # All must serialize safely
        packed = msgpack.packb(normalized)
        unpacked = msgpack.unpackb(packed)
        assert unpacked["max_uint64"] == MSGPACK_INT_MAX
        assert unpacked["min_int64"] == MSGPACK_INT_MIN
