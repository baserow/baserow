"""
Payload normalization utilities for safe serialization across transport layers.

Python supports arbitrary-precision integers, but msgpack (used internally by
channels_redis for websocket message serialization) only supports integers in
the range -(2^63) to (2^64 - 1). When data from external sources (e.g. HTTP
trigger payloads) contains integers exceeding these limits, websocket broadcasts
fail with:

    OverflowError: Python int too large to convert to C unsigned long

This cannot be fixed in a single file because the data enters the system at the
HTTP trigger boundary, flows through workflow execution and dispatch contexts,
and eventually reaches multiple independent broadcast paths. A normalization
layer is needed both at the input boundary (to catch the problem early) and at
the broadcast boundary (as a defensive measure for any data path that reaches
the channel layer).

Behavior: Out-of-range integers are converted to their string representation.
This is chosen over alternatives because:
  - Rejecting the payload would break valid workflows for a serialization limit.
  - Silently dropping fields would lose data without explanation.
  - Wrapping in structured objects (e.g. {"__type": "bigint"}) adds complexity
    with minimal benefit for realtime clients.
  - String conversion is deterministic, preserves the exact value, and follows
    the standard practice for large integers in JSON-based protocols.

The conversion is applied consistently to all websocket broadcasts, regardless
of whether data originates from HTTP triggers, test runs, or future sources.
"""

# msgpack supports signed 64-bit integers and unsigned 64-bit integers.
# The effective safe range for any Python int that must survive msgpack
# round-tripping through channels_redis is:
MSGPACK_INT_MAX = 2**64 - 1  # 18446744073709551615
MSGPACK_INT_MIN = -(2**63)  # -9223372036854775808


def normalize_value_for_serialization(value):
    """
    Normalize a single value for safe msgpack serialization.

    Integers outside the msgpack-safe range are converted to strings.
    Booleans are excluded since they are a subclass of int in Python
    but are handled natively by msgpack.
    All other types pass through unchanged.

    :param value: Any Python value.
    :return: The value, or its string representation if it's an out-of-range int.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, int) and (value > MSGPACK_INT_MAX or value < MSGPACK_INT_MIN):
        return str(value)
    return value


def normalize_payload_for_serialization(data):
    """
    Recursively normalize a data structure so that all values are safe for
    msgpack serialization via channels_redis.

    Walks dicts, lists, and tuples, converting any integer outside the
    msgpack-safe range to its string representation. All other types
    (strings, floats, booleans, None) pass through unchanged.

    Safe integers (within msgpack range) are preserved as-is to avoid
    unnecessary type changes for valid payloads.

    :param data: A dict, list, tuple, or scalar value.
    :return: A normalized copy of the data structure.
    """

    if isinstance(data, dict):
        return {
            key: normalize_payload_for_serialization(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [normalize_payload_for_serialization(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(normalize_payload_for_serialization(item) for item in data)
    else:
        return normalize_value_for_serialization(data)
