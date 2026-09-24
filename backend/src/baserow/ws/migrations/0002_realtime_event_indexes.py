from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import migrations, models, transaction

TABLE = "ws_realtime_events"
OLD_INDEX = "ws_realtime_payload_gin_idx"
USERS_INDEX = "ws_realtime_users_payload_idx"
TARGETS_INDEX = "ws_realtime_targets_idx"
ALL_USERS_INDEX = "ws_realtime_all_users_idx"
CREATED_INDEX = "ws_realtime_created_id_idx"

TARGETS_FUNCTION = """
CREATE OR REPLACE FUNCTION ws_set_realtime_event_targets() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Called by ws_realtime_event_targets_before_write for INSERTs and updates
    -- to payload/channel_group, including record_events() bulk inserts and old
    -- workers that do not know these columns. These indexed fields are read by
    -- RealtimeEventHandler.get_users_channel_live_delivery_filter() during replay.
    -- Reset them first so changing an event's channel cannot leave stale targets.
    NEW.target_user_ids := ARRAY[]::integer[];
    NEW.all_users := false;
    -- Page broadcasts use channel_group/id and need no JSON traversal on INSERT.
    IF NEW.channel_group <> 'users' THEN
        RETURN NEW;
    END IF;

    IF NEW.payload->>'type' = 'broadcast_to_users' THEN
        -- Only the JSON boolean true denotes an all-user broadcast.
        NEW.all_users := COALESCE(
            NEW.payload->'send_to_all_users' = 'true'::jsonb, false
        );
        -- Store a sorted set of int32 recipients. Guard the casts to ignore
        -- malformed values without rejecting the write: numeric strings,
        -- booleans, fractions and out-of-range numbers are not user IDs.
        SELECT COALESCE(array_agg(DISTINCT recipient ORDER BY recipient),
                        ARRAY[]::integer[])
        INTO NEW.target_user_ids
        FROM (
            SELECT CASE WHEN jsonb_typeof(value) = 'number' THEN
                CASE WHEN value::text::numeric BETWEEN -2147483648 AND 2147483647
                          AND trunc(value::text::numeric) = value::text::numeric
                     THEN value::text::numeric::integer END
                END AS recipient
            FROM jsonb_array_elements(
                CASE WHEN jsonb_typeof(NEW.payload->'user_ids') = 'array'
                     THEN NEW.payload->'user_ids' ELSE '[]'::jsonb END
            )
        ) recipients
        WHERE recipient IS NOT NULL;
    ELSIF NEW.payload->>'type' = 'broadcast_to_users_individual_payloads' THEN
        -- Delivery looks up payload_map[str(user_id)], so accept only canonical
        -- int32 keys ("42", not "0042" or "-0"). Length/range guards make casts safe;
        -- the string round trip prevents treating a different key as a recipient.
        SELECT COALESCE(array_agg(DISTINCT recipient ORDER BY recipient),
                        ARRAY[]::integer[])
        INTO NEW.target_user_ids
        FROM (
            SELECT CASE WHEN key ~ '^-?(0|[1-9][0-9]{0,9})$' THEN
                CASE WHEN key::bigint BETWEEN -2147483648 AND 2147483647
                          AND key::bigint::text = key
                     THEN key::integer END
                END AS recipient
            FROM jsonb_object_keys(
                CASE WHEN jsonb_typeof(NEW.payload->'payload_map') = 'object'
                     THEN NEW.payload->'payload_map' ELSE '{}'::jsonb END
            ) AS keys(key)
        ) recipients
        WHERE recipient IS NOT NULL;
    END IF;
    RETURN NEW;
END;
$$
"""


def _reset_buffer(cursor):
    # Keep stricter deployment timeouts, and don't leak ours onto the connection.
    for setting, timeout in [("lock_timeout", "1s"), ("statement_timeout", "3s")]:
        cursor.execute(
            "SELECT set_config(%s, %s, true) WHERE "
            "current_setting(%s)::interval = interval '0' OR "
            "current_setting(%s)::interval > %s::interval",
            [setting, timeout, setting, setting, timeout],
        )
    cursor.execute(f'LOCK TABLE "{TABLE}" IN ACCESS EXCLUSIVE MODE')
    # Both upgrade and rollback discard this disposable replay buffer, avoiding
    # any payload backfill or large index rebuild. Preserve IDs so old cursors
    # cannot accidentally anchor to unrelated events after the reset.
    cursor.execute(f'TRUNCATE TABLE "{TABLE}" CONTINUE IDENTITY')


def _drop_indexes(cursor):
    # Also replace invalid indexes left by the earlier concurrent-build draft.
    for name in (OLD_INDEX, USERS_INDEX, TARGETS_INDEX, ALL_USERS_INDEX, CREATED_INDEX):
        cursor.execute(f'DROP INDEX IF EXISTS "{name}"')


def forwards(apps, schema_editor):
    """Reset the disposable buffer and install indexed targets for future writes."""

    db = schema_editor.connection
    with transaction.atomic(using=db.alias), db.cursor() as cursor:
        _reset_buffer(cursor)
        cursor.execute(f'ALTER TABLE "{TABLE}" SET UNLOGGED')
        cursor.execute(
            f'ALTER TABLE "{TABLE}" '
            "ADD COLUMN IF NOT EXISTS target_user_ids integer[] NOT NULL "
            "DEFAULT '{}'::integer[], "
            "ADD COLUMN IF NOT EXISTS all_users boolean NOT NULL DEFAULT false"
        )
        # PG14 sequences are already logged and do not support SET LOGGED.
        # Dynamic SQL is reached only on versions with unlogged sequences. Keep
        # the sequence durable even though a crash can reset the event table.
        cursor.execute(
            """
            DO $$
            DECLARE event_sequence regclass :=
                pg_get_serial_sequence('ws_realtime_events', 'id');
            BEGIN
                IF (SELECT relpersistence FROM pg_class
                    WHERE oid = event_sequence) <> 'p' THEN
                    EXECUTE format('ALTER SEQUENCE %s SET LOGGED', event_sequence);
                END IF;
            END;
            $$
            """
        )
        cursor.execute(TARGETS_FUNCTION)
        cursor.execute(
            f'DROP TRIGGER IF EXISTS ws_realtime_event_targets_before_write ON "{TABLE}"'
        )
        cursor.execute(
            f"""
            CREATE TRIGGER ws_realtime_event_targets_before_write
            BEFORE INSERT OR UPDATE OF payload, channel_group ON "{TABLE}"
            FOR EACH ROW EXECUTE FUNCTION ws_set_realtime_event_targets()
            """
        )
        _drop_indexes(cursor)
        cursor.execute(
            f'CREATE INDEX "{TARGETS_INDEX}" ON "{TABLE}" '
            "USING gin (target_user_ids) WHERE channel_group = 'users'"
        )
        cursor.execute(
            f'CREATE INDEX "{ALL_USERS_INDEX}" ON "{TABLE}" '
            "(id) WHERE channel_group = 'users' AND all_users"
        )
        cursor.execute(f'CREATE INDEX "{CREATED_INDEX}" ON "{TABLE}" (created_at, id)')
        # Match database.0209's high-churn pending-search table settings.
        cursor.execute(
            f"""
            ALTER TABLE "{TABLE}" SET (
                autovacuum_analyze_threshold = 2000,
                autovacuum_analyze_scale_factor = 0.002,
                autovacuum_vacuum_threshold = 5000,
                autovacuum_vacuum_scale_factor = 0.01,
                autovacuum_vacuum_insert_threshold = 5000,
                autovacuum_vacuum_insert_scale_factor = 0.01
            )
            """
        )


def backwards(apps, schema_editor):
    db = schema_editor.connection
    with transaction.atomic(using=db.alias), db.cursor() as cursor:
        _reset_buffer(cursor)
        cursor.execute(
            f'DROP TRIGGER IF EXISTS ws_realtime_event_targets_before_write ON "{TABLE}"'
        )
        cursor.execute("DROP FUNCTION IF EXISTS ws_set_realtime_event_targets()")
        _drop_indexes(cursor)
        cursor.execute(
            f'ALTER TABLE "{TABLE}" DROP COLUMN IF EXISTS target_user_ids, '
            "DROP COLUMN IF EXISTS all_users"
        )
        cursor.execute(
            f'CREATE INDEX "{OLD_INDEX}" ON "{TABLE}" '
            "USING gin (payload jsonb_path_ops)"
        )
        cursor.execute(
            f"""
            ALTER TABLE "{TABLE}" RESET (
                autovacuum_analyze_threshold,
                autovacuum_analyze_scale_factor,
                autovacuum_vacuum_threshold,
                autovacuum_vacuum_scale_factor,
                autovacuum_vacuum_insert_threshold,
                autovacuum_vacuum_insert_scale_factor
            )
            """
        )
        # Intentionally keep the sequence LOGGED: rollback must not reuse IDs.


class Migration(migrations.Migration):
    dependencies = [("ws", "0001_initial")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(forwards, backwards)],
            state_operations=[
                migrations.AddField(
                    model_name="realtimeevent",
                    name="target_user_ids",
                    field=ArrayField(
                        models.IntegerField(),
                        default=list,
                        db_default=[],
                        editable=False,
                    ),
                ),
                migrations.AddField(
                    model_name="realtimeevent",
                    name="all_users",
                    field=models.BooleanField(
                        default=False, db_default=False, editable=False
                    ),
                ),
                migrations.AddIndex(
                    model_name="realtimeevent",
                    index=GinIndex(
                        fields=["target_user_ids"],
                        condition=models.Q(channel_group="users"),
                        name=TARGETS_INDEX,
                    ),
                ),
                migrations.AddIndex(
                    model_name="realtimeevent",
                    index=models.Index(
                        fields=["id"],
                        condition=models.Q(channel_group="users", all_users=True),
                        name=ALL_USERS_INDEX,
                    ),
                ),
                migrations.AddIndex(
                    model_name="realtimeevent",
                    index=models.Index(fields=["created_at", "id"], name=CREATED_INDEX),
                ),
                migrations.RemoveIndex(model_name="realtimeevent", name=OLD_INDEX),
            ],
        ),
    ]
