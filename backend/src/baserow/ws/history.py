"""Keep compact delivery evidence when full realtime events expire."""

import json
from time import monotonic

from django.db import connection, transaction

# Preserve delivery and recovery rules, including individual recipients' event
# types, but discard business data. Socket exclusions are summarized separately.
_ROUTING_SQL = """
jsonb_build_object(
    'type', payload->'type',
    'send_to_all_users', COALESCE(payload->'send_to_all_users', 'false'),
    'user_ids', (
        SELECT COALESCE(jsonb_agg(DISTINCT value ORDER BY value), '[]')
        FROM jsonb_array_elements(
            CASE WHEN jsonb_typeof(payload->'user_ids') = 'array'
            THEN payload->'user_ids' ELSE '[]' END
        )
    ),
    'exclude_user_ids', (
        SELECT COALESCE(jsonb_agg(DISTINCT value ORDER BY value), '[]')
        FROM jsonb_array_elements(
            CASE WHEN jsonb_typeof(payload->'exclude_user_ids') = 'array'
            THEN payload->'exclude_user_ids' ELSE '[]' END
        )
    ),
    'payload', jsonb_build_object('type', payload #> '{payload,type}'),
    'payload_map', (
        SELECT COALESCE(jsonb_object_agg(
            recipient, jsonb_build_object('type', message->'type')
        ), '{}')
        FROM jsonb_each(
            CASE WHEN jsonb_typeof(payload->'payload_map') = 'object'
            THEN payload->'payload_map' ELSE '{}' END
        ) AS messages(recipient, message)
    )
)
"""

_SELECT_EXPIRED_SQL = f"""
WITH candidates AS MATERIALIZED (
    SELECT id, channel_group, payload, target_user_ids, all_users
    FROM ws_realtime_events WHERE created_at < %s
    ORDER BY created_at, id LIMIT %s FOR UPDATE SKIP LOCKED
), routes AS MATERIALIZED (
    SELECT id, channel_group, {_ROUTING_SQL} AS route,
           target_user_ids, all_users,
           CASE WHEN jsonb_typeof(payload->'ignore_web_socket_id') = 'string'
                THEN payload->>'ignore_web_socket_id' END AS ignored_socket
    FROM candidates
)
SELECT id, sha256(convert_to(jsonb_build_array(
           channel_group, route, target_user_ids, all_users)::text, 'UTF8')),
       channel_group, route::text, target_user_ids, all_users, ignored_socket
FROM routes
""".strip()  # noqa: S608

_UPSERT_HISTORY_SQL = """
INSERT INTO ws_realtime_event_history_summary AS history (
    route_key, channel_group, payload, target_user_ids, all_users,
    latest_event_id, latest_socket_id, previous_event_id, previous_socket_id
)
SELECT decode(route_key, 'hex'), channel_group, payload_text::jsonb,
       target_user_ids, all_users,
       latest_event_id, latest_socket_id, previous_event_id, previous_socket_id
FROM jsonb_to_recordset(%s::jsonb) AS batch(
    route_key text, channel_group text, payload_text text,
    target_user_ids integer[], all_users boolean,
    latest_event_id bigint, latest_socket_id text,
    previous_event_id bigint, previous_socket_id text
)
ORDER BY route_key
ON CONFLICT (route_key) DO UPDATE SET
    (latest_event_id, latest_socket_id, previous_event_id, previous_socket_id) = (
        SELECT (array_agg(event_id ORDER BY event_id DESC))[1],
               (array_agg(socket_id ORDER BY event_id DESC))[1],
               (array_agg(event_id ORDER BY event_id DESC))[2],
               (array_agg(socket_id ORDER BY event_id DESC))[2]
        FROM (
            SELECT DISTINCT ON (socket_id) event_id, socket_id
            FROM (VALUES
                (history.latest_event_id, history.latest_socket_id),
                (history.previous_event_id, history.previous_socket_id),
                (excluded.latest_event_id, excluded.latest_socket_id),
                (excluded.previous_event_id, excluded.previous_socket_id)
            ) AS evidence(event_id, socket_id)
            WHERE event_id IS NOT NULL
            ORDER BY socket_id, event_id DESC
        ) AS latest_per_socket
    )
RETURNING route_key, channel_group, payload::text, target_user_ids, all_users
""".strip()

_DELETE_EXPIRED_SQL = "DELETE FROM ws_realtime_events WHERE id = ANY(%s)"

_ADVANCE_HIGH_WATER_SQL = """
UPDATE ws_realtime_event_history_state
SET compacted_event_id = GREATEST(compacted_event_id, %s)
WHERE id = 1
""".strip()

_CONFIGURE_TRANSACTION_SQL = """
SELECT
    set_config('statement_timeout', CASE
        WHEN current_setting('statement_timeout')::interval = interval '0'
          OR current_setting('statement_timeout')::interval > %s::interval
        THEN %s ELSE current_setting('statement_timeout') END, true),
    set_config('lock_timeout', CASE
        WHEN current_setting('lock_timeout')::interval = interval '0'
          OR current_setting('lock_timeout')::interval > %s::interval
        THEN %s ELSE current_setting('lock_timeout') END, true)
""".strip()


class _CleanupDeadlineExceeded(Exception):
    pass


def _make_executor(cursor, deadline, statement_timeout_ms, lock_timeout_ms):
    """Apply transaction-local limits, tightening them as the budget runs out."""

    configured_timeout_ms = None

    def execute(sql, params=None):
        nonlocal configured_timeout_ms
        remaining_ms = int((deadline - monotonic()) * 1000)
        if remaining_ms <= 0:
            raise _CleanupDeadlineExceeded
        timeout_ms = min(statement_timeout_ms, remaining_ms)
        if timeout_ms != configured_timeout_ms:
            statement_limit = f"{timeout_ms}ms"
            lock_limit = f"{lock_timeout_ms}ms"
            cursor.execute(
                _CONFIGURE_TRANSACTION_SQL,
                [statement_limit, statement_limit, lock_limit, lock_limit],
            )
            configured_timeout_ms = timeout_ms
        if monotonic() >= deadline:
            raise _CleanupDeadlineExceeded
        cursor.execute(sql, params)
        if monotonic() >= deadline:
            raise _CleanupDeadlineExceeded

    return execute


def _summarize_candidates(candidates):
    """Keep the newest two different socket exclusions for each exact audience.

    Any client can exclude at most one socket. Its latest relevant expired event
    is therefore either the newest event or the newest with a different socket.
    """

    audiences = {}
    for event_id, key, channel, payload, targets, all_users, socket in candidates:
        key = bytes(key).hex()
        audience = (channel, payload, targets, all_users)
        if key not in audiences:
            audiences[key] = (audience, {})
        original, sockets = audiences[key]
        if original != audience:
            raise RuntimeError("Realtime history route hash collision")
        sockets[socket] = max(event_id, sockets.get(socket, 0))

    summaries = []
    for key, ((channel, payload, targets, all_users), sockets) in audiences.items():
        latest, *rest = sorted(sockets.items(), key=lambda pair: pair[1], reverse=True)
        previous_socket, previous_id = rest[0] if rest else (None, None)
        summaries.append(
            {
                "route_key": key,
                "channel_group": channel,
                "payload_text": payload,
                "target_user_ids": targets,
                "all_users": all_users,
                "latest_event_id": latest[1],
                "latest_socket_id": latest[0],
                "previous_event_id": previous_id,
                "previous_socket_id": previous_socket,
            }
        )
    return summaries


def compact_events_batch(
    cutoff, deadline, *, batch_size, statement_timeout_ms, lock_timeout_ms
):
    """Publish expired-event evidence and delete full payloads in one commit."""

    try:
        with transaction.atomic(durable=True), connection.cursor() as cursor:
            execute = _make_executor(
                cursor, deadline, statement_timeout_ms, lock_timeout_ms
            )
            execute("SELECT ws_initialize_realtime_history()")
            execute(_SELECT_EXPIRED_SQL, [cutoff, batch_size])
            candidates = cursor.fetchall()
            if not candidates:
                return 0
            summaries = _summarize_candidates(candidates)
            execute(_UPSERT_HISTORY_SQL, [json.dumps(summaries)])
            expected = {entry["route_key"]: entry for entry in summaries}
            for key, channel, payload, targets, all_users in cursor.fetchall():
                entry = expected[bytes(key).hex()]
                if (channel, payload, targets, all_users) != (
                    entry["channel_group"],
                    entry["payload_text"],
                    entry["target_user_ids"],
                    entry["all_users"],
                ):
                    # ON CONFLICT serializes concurrent summaries. A hash collision
                    # must roll back that merge as well as leave originals intact.
                    raise RuntimeError("Realtime history route hash collision")
            ids = [row[0] for row in candidates]
            execute(_DELETE_EXPIRED_SQL, [ids])
            deleted = cursor.rowcount
            execute(_ADVANCE_HIGH_WATER_SQL, [max(ids)])
            if cursor.rowcount != 1:
                raise RuntimeError("Realtime history state is missing")
            return deleted
    except _CleanupDeadlineExceeded:
        # Roll back the summary and deletion together before reporting no progress.
        return 0
