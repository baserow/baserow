"""
Benchmark actual realtime event code paths against a real table.

Calls the real handler methods — no simulations, no query rebuilding.
Run after populate_realtime_events.

    python manage.py benchmark_realtime
    python manage.py benchmark_realtime --explain

Glossary
--------
page_types  Page type subscriptions — channel groups like "table-42" or
            "dashboard-7" that a client joins when viewing a specific page.
users       The "users" channel group — every authenticated WebSocket
            client joins it; carries user-level notifications (workspace
            updates, invitations, etc.).
last_seen_id
            The event id the client reports on reconnect. The server
            checks this exact id still exists in the table; if it has been
            cleaned up by retention, replay is impossible.
last_seen_id gone
            Scenario where last_seen_id no longer exists — retention
            deleted it. The check fails immediately (fast path).
behind      How many event ids separate the client's last_seen_id from
            the current max id. Larger gap = more rows to scan.
replay      Fetching and re-dispatching missed events between
            last_seen_id and now so the client catches up after a
            disconnect.
rare user   A user_id that does not appear in any user_ids arrays or
            payload_maps. Only send_to_all_users events match — tests
            worst-case JSONB scan density.
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Max

from baserow.ws.models import RealtimeEvent
from baserow.ws.realtime_events import RealtimeEventHandler


class Command(BaseCommand):
    help = "Benchmark actual realtime event handler methods against real data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--iterations", type=int, default=5, help="Timing iterations per scenario"
        )
        parser.add_argument(
            "--explain", action="store_true", help="Print EXPLAIN ANALYZE for queries"
        )

    def handle(self, **options):
        iterations = options["iterations"]
        show_explain = options["explain"]

        total = RealtimeEvent.objects.count()
        if total == 0:
            self.stdout.write("No events. Run populate_realtime_events first.")
            return

        max_id = RealtimeEvent.objects.aggregate(m=Max("id"))["m"]
        min_id = (
            RealtimeEvent.objects.order_by("id").values_list("id", flat=True).first()
        )
        self.stdout.write(f"Table: {total:,} rows, id range: {min_id:,} — {max_id:,}")
        self._print_indexes()

        user_id = 1
        web_socket_id = "ws-1"
        groups_pages = ["table-1", "table-2", "users"]
        groups_users = ["users"]

        rare_user_id = 99999

        scenarios = [
            ("replay: 50 behind, page_types", max_id - 50, groups_pages, user_id),
            ("replay: 1k behind, page_types", max_id - 1000, groups_pages, user_id),
            ("replay: 50 behind, users only", max_id - 50, groups_users, user_id),
            ("replay: 1k behind, users only", max_id - 1000, groups_users, user_id),
            (
                "replay fails: 50k behind, page_types",
                max_id - 50000,
                groups_pages,
                user_id,
            ),
            (
                "replay fails: 50k behind, users only",
                max_id - 50000,
                groups_users,
                user_id,
            ),
            ("worst: full gap, rare user", min_id, groups_users, rare_user_id),
            ("replay fails: last_seen_id gone", 1, groups_pages, user_id),
            ("replay fails: last_seen_id gone, users", 1, groups_users, user_id),
            ("baseline: last_seen=None", None, groups_pages, user_id),
        ]

        header = (
            f"{'Scenario':<45} {'Method':<25} "
            f"{'Avg ms':>8} {'Best ms':>8} {'Result':<25}"
        )
        sep = "-" * len(header)
        self.stdout.write(f"\n{header}")
        self.stdout.write(sep)

        for label, last_seen_id, groups, scenario_user_id in scenarios:
            self._benchmark_scenario(
                label,
                scenario_user_id,
                groups,
                last_seen_id,
                web_socket_id,
                iterations,
                show_explain,
            )
            self.stdout.write(sep)

    def _benchmark_scenario(
        self,
        label,
        user_id,
        groups,
        last_seen_id,
        web_socket_id,
        iterations,
        show_explain,
    ):
        def run_replay_events_result():
            result = RealtimeEventHandler.get_replay_events_result(
                user_id,
                groups,
                last_seen_id,
                web_socket_id,
            )
            return (
                f"force_refresh={result.force_refresh}, "
                f"replay={len(result.replay_events)}, "
                f"latest={result.latest_event_id}"
            )

        avg_r, best_r, result_r = self._time(run_replay_events_result, iterations)
        self.stdout.write(
            f"{label:<45} {'replay_events_result':<25} "
            f"{avg_r:>8.2f} {best_r:>8.2f} {result_r:<25}"
        )

        if show_explain and last_seen_id is not None:
            self._explain_replay(user_id, groups, last_seen_id, web_socket_id)

    def _explain_replay(self, user_id, groups, last_seen_id, web_socket_id):
        from django.db.models import Q

        conditions = RealtimeEventHandler.get_relevant_events_filter(
            user_id,
            groups,
        )
        qs = RealtimeEvent.objects.filter(
            Q(id__gte=last_seen_id)
            & RealtimeEventHandler.get_not_own_event_filter(web_socket_id)
            & conditions
        )
        qs = qs.order_by("id")[: settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 2]
        self._run_explain(qs, "replay_events replay query")

    def _run_explain(self, qs, label):
        sql, params = qs.query.sql_with_params()
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS) {sql}", params)
            plan = "\n".join(row[0] for row in cursor.fetchall())
        self.stdout.write(f"\n  EXPLAIN: {label}")
        self.stdout.write(f"  {plan.replace(chr(10), chr(10) + '  ')}\n")

    def _print_indexes(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = %s ORDER BY indexname",
                ["ws_realtime_events"],
            )
            names = [r[0] for r in cursor.fetchall()]
        self.stdout.write(f"Indexes: {', '.join(names)}\n")

    @staticmethod
    def _time(fn, iterations):
        times = []
        result = None
        for _ in range(iterations):
            t0 = time.perf_counter()
            result = fn()
            times.append(time.perf_counter() - t0)
        avg = sum(times) / len(times) * 1000
        best = min(times) * 1000
        return avg, best, result
