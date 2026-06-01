import json
import random
import time

from django.core.management.base import BaseCommand
from django.db import connection

from baserow.core.psycopg import sql


class Command(BaseCommand):
    help = "Populate ws_realtime_events with realistic data for performance testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=100_000, help="Number of events to insert"
        )
        parser.add_argument(
            "--groups", type=int, default=30, help="Number of table-N channel groups"
        )
        parser.add_argument(
            "--users", type=int, default=100, help="Number of simulated user IDs"
        )
        parser.add_argument(
            "--batch-size", type=int, default=2000, help="INSERT batch size"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="TRUNCATE table before populating",
        )

    def handle(self, **options):
        count = options["count"]
        num_groups = options["groups"]
        num_users = options["users"]
        batch_size = options["batch_size"]

        table = sql.Identifier("ws_realtime_events")

        if options["clear"]:
            self.stdout.write("Truncating ws_realtime_events...")
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY").format(table))

        table_groups = [f"table-{i}" for i in range(1, num_groups + 1)]
        user_ids = list(range(1, num_users + 1))
        ws_ids = [f"ws-{i}" for i in range(1, 20)]

        self.stdout.write(
            f"Populating {count:,} events across {num_groups} table groups "
            f"+ users group, {num_users} users (batch {batch_size:,})"
        )

        total_inserted = 0
        t_start = time.perf_counter()

        with connection.cursor() as cursor:
            batch_values = []
            batch_params = []

            for i in range(count):
                ws_id = random.choice(ws_ids)
                r = random.random()

                if r < 0.6:
                    group = random.choice(table_groups)
                    payload = self._broadcast_to_group(group, ws_id)
                elif r < 0.9:
                    group = "users"
                    subset = random.sample(
                        user_ids, min(len(user_ids), random.randint(1, 20))
                    )
                    payload = self._broadcast_to_users(subset, ws_id)
                else:
                    group = "users"
                    payload = self._individual_payloads(user_ids, ws_id)

                batch_values.append(
                    sql.SQL("(%s, %s::jsonb, NOW() - INTERVAL '%s seconds')")
                )
                age_seconds = int((count - i) * 0.5)
                batch_params.extend([group, json.dumps(payload), age_seconds])

                if len(batch_values) >= batch_size:
                    self._insert_batch(cursor, batch_values, batch_params)
                    total_inserted += len(batch_values)
                    batch_values = []
                    batch_params = []

                    elapsed = time.perf_counter() - t_start
                    rate = total_inserted / elapsed
                    self.stdout.write(
                        f"  {total_inserted:>10,} / {count:,}  ({rate:,.0f} rows/s)"
                    )

            if batch_values:
                self._insert_batch(cursor, batch_values, batch_params)
                total_inserted += len(batch_values)

        elapsed = time.perf_counter() - t_start
        self.stdout.write(
            f"\nDone: {total_inserted:,} rows in {elapsed:.1f}s "
            f"({total_inserted / elapsed:,.0f} rows/s)"
        )

        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(table))
            self.stdout.write(f"Total rows: {cursor.fetchone()[0]:,}")
            cursor.execute(
                sql.SQL("SELECT MIN({id}), MAX({id}) FROM {tbl}").format(
                    id=sql.Identifier("id"), tbl=table
                )
            )
            min_id, max_id = cursor.fetchone()
            self.stdout.write(f"ID range: {min_id:,} — {max_id:,}")
            cursor.execute(
                sql.SQL("SELECT pg_size_pretty(pg_total_relation_size(%s))"),
                ["ws_realtime_events"],
            )
            self.stdout.write(f"Table size (incl indexes): {cursor.fetchone()[0]}")

    @staticmethod
    def _insert_batch(cursor, batch_values, batch_params):
        table = sql.Identifier("ws_realtime_events")
        cols = sql.SQL(", ").join(
            sql.Identifier(c) for c in ("channel_group", "payload", "created_at")
        )
        query = sql.SQL("INSERT INTO {} ({}) VALUES {}").format(
            table, cols, sql.SQL(", ").join(batch_values)
        )
        cursor.execute(query, batch_params)

    @staticmethod
    def _broadcast_to_group(group_name, ws_id):
        return {
            "type": "broadcast_to_group",
            "payload": {
                "type": random.choice(
                    [
                        "rows_created",
                        "rows_updated",
                        "rows_deleted",
                        "field_created",
                        "field_updated",
                        "field_deleted",
                        "view_created",
                        "view_updated",
                        "view_filter_created",
                    ]
                ),
                "table_id": random.randint(1, 500),
            },
            "ignore_web_socket_id": ws_id,
            "exclude_user_ids": None,
        }

    @staticmethod
    def _broadcast_to_users(user_ids, ws_id):
        send_to_all = False
        return {
            "type": "broadcast_to_users",
            "user_ids": user_ids if not send_to_all else [],
            "payload": {
                "type": random.choice(
                    [
                        "group_updated",
                        "group_user_updated",
                        "application_created",
                        "application_updated",
                        "user_data_updated",
                        "notifications_created",
                    ]
                ),
            },
            "ignore_web_socket_id": ws_id,
            "send_to_all_users": send_to_all,
        }

    @staticmethod
    def _individual_payloads(user_ids, ws_id):
        subset = random.sample(user_ids, min(len(user_ids), random.randint(1, 10)))
        payload_map = {}
        for uid in subset:
            payload_map[str(uid)] = {
                "type": "application_created",
                "application": {"id": random.randint(1, 1000)},
            }
        return {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": payload_map,
            "ignore_web_socket_id": ws_id,
        }
