# Store expired delivery evidence separately so cleanup can delete full payloads.
# The PostgreSQL helper initializes a safe replay boundary on deployment and after
# an UNLOGGED reset. Existing event data and indexes remain unchanged; drain old
# cleanup and update readers before enabling the new cleanup.

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import migrations, models, transaction

INITIALIZE_HISTORY = """
CREATE OR REPLACE FUNCTION ws_initialize_realtime_history() RETURNS void
LANGUAGE plpgsql AS $function$
DECLARE
    event_sequence regclass;
    sequence_value bigint;
    sequence_called boolean;
    history_floor bigint;
BEGIN
    -- Called by migration, replay and cleanup when history state is missing.
    -- UNLOGGED history can disappear after a crash; cursors below its new floor
    -- must refresh because neither full events nor summaries prove their gap.
    IF EXISTS (SELECT 1 FROM ws_realtime_event_history_state WHERE id = 1) THEN
        RETURN;
    END IF;
    -- Wait for pending INSERTs before trusting their allocated IDs as a boundary.
    LOCK TABLE ws_realtime_events IN SHARE MODE;
    IF EXISTS (SELECT 1 FROM ws_realtime_event_history_state WHERE id = 1) THEN
        RETURN;
    END IF;
    event_sequence := pg_get_serial_sequence('ws_realtime_events', 'id')::regclass;
    -- ws.0002 keeps this sequence LOGGED. Cached IDs could otherwise be inserted
    -- below the new floor after this transaction releases its table lock.
    IF NOT EXISTS (
        SELECT 1 FROM pg_sequence WHERE seqrelid = event_sequence AND seqcache = 1
    ) THEN
        RAISE EXCEPTION 'Realtime history requires CACHE 1 for the event sequence';
    END IF;
    EXECUTE format('SELECT last_value, is_called FROM %s', event_sequence)
        INTO sequence_value, sequence_called;
    history_floor := CASE WHEN sequence_called THEN sequence_value ELSE 0 END;
    INSERT INTO ws_realtime_event_history_state (id, floor, compacted_event_id)
    VALUES (1, history_floor, history_floor)
    ON CONFLICT (id) DO NOTHING;
END;
$function$;
"""


def _set_timeouts(cursor):
    for setting, timeout in [("lock_timeout", "1s"), ("statement_timeout", "3s")]:
        cursor.execute(
            "SELECT set_config(%s, %s, true) WHERE "
            "current_setting(%s)::interval = interval '0' OR "
            "current_setting(%s)::interval > %s::interval",
            [setting, timeout, setting, setting, timeout],
        )


def forwards(apps, schema_editor):
    """Install history initialization; the scheduled task performs compaction."""

    db = schema_editor.connection
    with transaction.atomic(using=db.alias), db.cursor() as cursor:
        _set_timeouts(cursor)
        cursor.execute("ALTER TABLE ws_realtime_event_history_summary SET UNLOGGED")
        cursor.execute("ALTER TABLE ws_realtime_event_history_state SET UNLOGGED")
        cursor.execute(INITIALIZE_HISTORY)
        cursor.execute("SELECT ws_initialize_realtime_history()")


def backwards(apps, schema_editor):
    # Django drops only the two new tables afterward. Remaining full events and
    # the durable sequence are preserved; rollback cannot restore deleted events.
    # Disable replay and re-establish client baselines before restoring old readers.
    db = schema_editor.connection
    with transaction.atomic(using=db.alias), db.cursor() as cursor:
        _set_timeouts(cursor)
        cursor.execute("DROP FUNCTION IF EXISTS ws_initialize_realtime_history()")


class Migration(migrations.Migration):
    dependencies = [("ws", "0002_realtime_event_indexes")]

    operations = [
        migrations.CreateModel(
            name="RealtimeEventHistorySummary",
            fields=[
                ("route_key", models.BinaryField(primary_key=True, serialize=False)),
                ("channel_group", models.TextField()),
                ("payload", models.JSONField()),
                (
                    "target_user_ids",
                    ArrayField(
                        models.IntegerField(),
                        default=list,
                        db_default=[],
                        editable=False,
                    ),
                ),
                (
                    "all_users",
                    models.BooleanField(
                        default=False, db_default=False, editable=False
                    ),
                ),
                ("latest_event_id", models.BigIntegerField()),
                ("latest_socket_id", models.TextField(null=True)),
                ("previous_event_id", models.BigIntegerField(null=True)),
                ("previous_socket_id", models.TextField(null=True)),
            ],
            options={
                "db_table": "ws_realtime_event_history_summary",
                "indexes": [
                    models.Index(
                        fields=["channel_group"],
                        name="ws_history_summary_channel_idx",
                    ),
                    GinIndex(
                        fields=["target_user_ids"],
                        condition=models.Q(channel_group="users"),
                        name="ws_history_summary_targets_idx",
                    ),
                    models.Index(
                        fields=["all_users"],
                        condition=models.Q(channel_group="users", all_users=True),
                        name="ws_history_summary_all_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            previous_event_id__isnull=True,
                            previous_socket_id__isnull=True,
                        )
                        | (
                            models.Q(previous_event_id__isnull=False)
                            & models.Q(
                                previous_event_id__lt=models.F("latest_event_id")
                            )
                        ),
                        name="ws_history_previous_pair",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="RealtimeEventHistoryState",
            fields=[
                (
                    "id",
                    models.PositiveSmallIntegerField(
                        primary_key=True, serialize=False, db_default=1
                    ),
                ),
                ("floor", models.BigIntegerField(db_default=0)),
                ("compacted_event_id", models.BigIntegerField(db_default=0)),
            ],
            options={
                "db_table": "ws_realtime_event_history_state",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(id=1), name="ws_history_state_singleton"
                    )
                ],
            },
        ),
        migrations.RunPython(forwards, backwards),
    ]
