from typing import Any

MSG_PACK_MAX_INT = 2**63 - 1
MSG_PACK_MIN_INT = -(2**63)
MSG_PACK_MAX_UINT = 2**64 - 1


def normalize_msgpack_unsafe_values(value: Any) -> Any:
    """
    Recursively converts values that msgpack cannot serialize safely.

    channels_redis uses msgpack to serialize websocket group messages. msgpack only
    supports integers in the signed/unsigned 64-bit range. Python integers can exceed
    those limits, which then raises an OverflowError at serialization time.
    """

    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, int):
        if value < MSG_PACK_MIN_INT or value > MSG_PACK_MAX_UINT:
            return str(value)
        return value

    if isinstance(value, list):
        return [normalize_msgpack_unsafe_values(v) for v in value]

    if isinstance(value, tuple):
        return tuple(normalize_msgpack_unsafe_values(v) for v in value)

    if isinstance(value, (set, frozenset)):
        return [normalize_msgpack_unsafe_values(v) for v in value]

    if isinstance(value, dict):
        return {
            normalize_msgpack_unsafe_values(k): normalize_msgpack_unsafe_values(v)
            for k, v in value.items()
        }

    return value
