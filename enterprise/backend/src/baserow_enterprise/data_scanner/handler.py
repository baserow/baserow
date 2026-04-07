import re
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Optional

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.search import SearchQuery
from django.core.exceptions import PermissionDenied
from django.db.models import Count, QuerySet, TextField
from django.db.models.functions import Cast
from django.utils import timezone

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.models import AbstractSearchValue
from baserow.contrib.database.table.models import Table
from baserow.core.models import Workspace
from baserow_enterprise.data_scanner.constants import (
    FREQUENCY_INTERVALS,
    SCAN_TYPE_LIST_OF_VALUES,
    SCAN_TYPE_LIST_TABLE,
    SCAN_TYPE_PATTERN,
    STALE_SCAN_THRESHOLD_HOURS,
)
from baserow_enterprise.data_scanner.exceptions import (
    DataScanDoesNotExist,
    DataScanIsAlreadyRunning,
    DataScanResultDoesNotExist,
)
from baserow_enterprise.data_scanner.models import (
    DataScan,
    DataScanListItem,
    DataScanResult,
)
from baserow_enterprise.data_scanner.tasks import run_data_scan
from baserow_enterprise.features import DATA_SCANNER
from baserow_premium.license.handler import LicenseHandler

TOKEN_MAP = {
    "A": "[A-Za-z]",
    "D": "[0-9]",
    "X": ".",
}

TOKEN_CHARS = {"A", "D", "X"}


def convert_pattern_to_regex(pattern: str) -> str:
    """
    Converts a custom pattern syntax to a regex string.

    Tokens:
    - `A` -> any letter `[A-Za-z]`
    - `D` -> any digit `[0-9]`
    - `X` -> any character `.`
    - ``\\c`` -> literal character ``c``

    :param pattern: The custom pattern string (e.g. `AADDAAAADDDDDDDDDD`).
    :return: A regex string equivalent.
    """

    parts: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            # Escaped literal
            parts.append(re.escape(pattern[i + 1]))
            i += 2
        elif char in TOKEN_MAP:
            parts.append(TOKEN_MAP[char])
            i += 1
        else:
            parts.append(re.escape(char))
            i += 1
    return "".join(parts)


def _pattern_has_special_chars(pattern: str) -> bool:
    """
    Returns True if the pattern contains escaped literal characters that are not
    alphanumeric (e.g. ``\\-``, ``\\.``). These characters are stripped during tsvector
    tokenization so pattern matching against the search table requires a two-phase
    approach.
    """

    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            next_char = pattern[i + 1]
            if not next_char.isalnum():
                return True
            i += 2
        elif char in TOKEN_CHARS:
            i += 1
        else:
            if not char.isalnum():
                return True
            i += 1
    return False


def _build_broad_token_regex(pattern: str) -> str:
    """
    Builds a broad regex that can match individual tsvector tokens. The pattern is
    split on escaped special characters and unescaped non-alphanumeric literals, and
    the longest resulting token-level regex fragment is returned. This is used as a
    fast pre-filter on the search table before verifying against actual cell values.

    For example ``DDDD\\-DD\\-DD`` yields token fragments ``[0-9]{4}``, ``[0-9]{2}``,
    ``[0-9]{2}`` and returns the longest one: ``[0-9][0-9][0-9][0-9]``.
    """

    fragments: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            next_char = pattern[i + 1]
            if next_char.isalnum():
                # Escaped alphanumeric literal – stays in the current token.
                current.append(re.escape(next_char))
            else:
                # Escaped special char – token boundary.
                if current:
                    fragments.append("".join(current))
                    current = []
            i += 2
        elif char in TOKEN_MAP:
            current.append(TOKEN_MAP[char])
            i += 1
        else:
            if char.isalnum():
                current.append(re.escape(char))
            else:
                # Unescaped special char – token boundary.
                if current:
                    fragments.append("".join(current))
                    current = []
            i += 1

    if current:
        fragments.append("".join(current))

    if not fragments:
        return convert_pattern_to_regex(pattern)

    return max(fragments, key=len)


def _check_data_scanner_access(user: AbstractUser) -> None:
    """
    Verifies that the given user holds the DATA_SCANNER enterprise feature
    and is a staff member. Raises if either check fails.

    :param user: The user to verify.
    :raises FeaturesNotAvailableError: When the enterprise license is missing.
    :raises PermissionDenied: When the user is not staff.
    """

    LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(DATA_SCANNER, user)
    if not user.is_staff:
        raise PermissionDenied()


class DataScannerHandler:
    @staticmethod
    def create_scan(
        user: AbstractUser,
        name: str,
        scan_type: str,
        pattern: Optional[str] = None,
        frequency: str = "manual",
        scan_all_workspaces: bool = True,
        workspace_ids: Optional[list[int]] = None,
        list_items: Optional[list[str]] = None,
        source_table_id: Optional[int] = None,
        source_field_id: Optional[int] = None,
        whole_words: bool = True,
    ) -> DataScan:
        """
        Creates a new data scan configuration.

        :param user: The staff user performing the action.
        :param name: Human-readable name for the scan.
        :param scan_type: One of `pattern`, `list_of_values`, or `list_table`.
        :param pattern: Required when scan_type is `pattern`.
        :param frequency: How often the scan runs automatically.
        :param scan_all_workspaces: When False, only the given workspace_ids are
            scanned.
        :param workspace_ids: Workspace IDs to restrict scanning to.
        :param list_items: Values to match when scan_type is `list_of_values`.
        :param source_table_id: Source table ID when scan_type is `list_table`.
        :param source_field_id: Source field ID when scan_type is `list_table`.
        :param whole_words: When True, only match whole words/tokens.
        :return: The newly created DataScan instance.
        """

        _check_data_scanner_access(user)

        scan = DataScan.objects.create(
            name=name,
            scan_type=scan_type,
            pattern=pattern,
            frequency=frequency,
            scan_all_workspaces=scan_all_workspaces,
            whole_words=whole_words,
            created_by=user,
            source_table_id=source_table_id
            if scan_type == SCAN_TYPE_LIST_TABLE
            else None,
            source_field_id=source_field_id
            if scan_type == SCAN_TYPE_LIST_TABLE
            else None,
        )

        if not scan_all_workspaces and workspace_ids:
            workspaces = Workspace.objects.filter(id__in=workspace_ids)
            scan.workspaces.set(workspaces)

        if scan_type == SCAN_TYPE_LIST_OF_VALUES and list_items:
            DataScanListItem.objects.bulk_create(
                [DataScanListItem(scan=scan, value=v) for v in list_items]
            )

        return scan

    @staticmethod
    def update_scan(user: AbstractUser, scan_id: int, **kwargs) -> DataScan:
        """
        Updates an existing data scan and cleans up stale results when the
        configuration changes in a way that invalidates them.

        :param user: The staff user performing the action.
        :param scan_id: Primary key of the scan to update.
        :param kwargs: Fields to update (name, scan_type, pattern, frequency,
            scan_all_workspaces, workspace_ids, list_items, source_table_id,
            source_field_id).
        :return: The updated DataScan instance.
        :raises DataScanDoesNotExist: When the scan is not found.
        """

        _check_data_scanner_access(user)

        try:
            scan = DataScan.objects.select_for_update(of=("self",)).get(id=scan_id)
        except DataScan.DoesNotExist:
            raise DataScanDoesNotExist()

        if scan.is_running:
            raise DataScanIsAlreadyRunning()

        simple_fields = [
            "name",
            "scan_type",
            "pattern",
            "frequency",
            "scan_all_workspaces",
            "source_table_id",
            "source_field_id",
            "whole_words",
        ]
        for field_name in simple_fields:
            if field_name in kwargs:
                setattr(scan, field_name, kwargs[field_name])
        scan.save()

        if "workspace_ids" in kwargs:
            if scan.scan_all_workspaces:
                scan.workspaces.clear()
            else:
                workspaces = Workspace.objects.filter(id__in=kwargs["workspace_ids"])
                scan.workspaces.set(workspaces)

        if "list_items" in kwargs:
            scan.list_items.all().delete()
            items = kwargs["list_items"]
            if items:
                DataScanListItem.objects.bulk_create(
                    [DataScanListItem(scan=scan, value=v) for v in items]
                )

        DataScannerHandler._cleanup_stale_results(scan, kwargs)

        return scan

    @staticmethod
    def _cleanup_stale_results(scan: DataScan, kwargs: dict) -> None:
        """
        Removes results that are no longer valid after a scan update. For
        example, if the pattern or scan type changed, all existing results are
        cleared. If list items changed, only results whose matched value is no
        longer in the list are removed.

        :param scan: The scan whose results may need pruning.
        :param kwargs: The update kwargs that were applied to the scan.
        """

        if "scan_type" in kwargs:
            scan.results.all().delete()
            return

        if "pattern" in kwargs and scan.scan_type == SCAN_TYPE_PATTERN:
            scan.results.all().delete()
            return

        if "list_items" in kwargs and scan.scan_type == SCAN_TYPE_LIST_OF_VALUES:
            new_items = set(kwargs["list_items"] or [])
            if not new_items:
                scan.results.all().delete()
            else:
                scan.results.exclude(matched_value__in=new_items).delete()

    @staticmethod
    def delete_scan(user: AbstractUser, scan_id: int) -> None:
        """
        Deletes a data scan and all of its related objects.

        :param user: The staff user performing the action.
        :param scan_id: Primary key of the scan to delete.
        :raises DataScanDoesNotExist: When the scan is not found.
        """

        _check_data_scanner_access(user)

        try:
            scan = DataScan.objects.select_for_update(of=("self",)).get(id=scan_id)
        except DataScan.DoesNotExist:
            raise DataScanDoesNotExist()

        if scan.is_running:
            raise DataScanIsAlreadyRunning()

        scan.delete()

    @staticmethod
    def list_scans(user: AbstractUser) -> QuerySet[DataScan]:
        """
        Returns all data scans. Requires an enterprise license and staff
        access.

        :param user: The staff user performing the action.
        :return: A queryset of all DataScan instances.
        """

        _check_data_scanner_access(user)
        return (
            DataScan.objects.annotate(results_count=Count("results"))
            .prefetch_related(
                "workspaces",
                "list_items",
            )
            .select_related(
                "created_by",
                "source_table__database__workspace",
            )
        )

    @staticmethod
    def get_scan(user: AbstractUser, scan_id: int) -> DataScan:
        """
        Returns a single data scan by its primary key.

        :param user: The staff user performing the action.
        :param scan_id: Primary key of the scan.
        :return: The DataScan instance.
        :raises DataScanDoesNotExist: When the scan is not found.
        """

        _check_data_scanner_access(user)

        try:
            return DataScan.objects.get(id=scan_id)
        except DataScan.DoesNotExist:
            raise DataScanDoesNotExist()

    @staticmethod
    def delete_result(user: AbstractUser, result_id: int) -> None:
        """
        Deletes (resolves) a single data scan result.

        :param user: The staff user performing the action.
        :param result_id: Primary key of the result to delete.
        :raises DataScanResult.DoesNotExist: When the result is not found.
        """

        _check_data_scanner_access(user)

        try:
            result = DataScanResult.objects.get(id=result_id)
        except DataScanResult.DoesNotExist:
            raise DataScanResultDoesNotExist()

        result.delete()

    @staticmethod
    def trigger_scan(user: AbstractUser, scan_id: int) -> DataScan:
        """
        Queues an immediate asynchronous run of the given scan.

        :param user: The staff user triggering the scan.
        :param scan_id: Primary key of the scan to trigger.
        :return: The DataScan instance.
        :raises DataScanDoesNotExist: When the scan is not found.
        :raises DataScanIsAlreadyRunning: When the scan is already in progress.
        """

        _check_data_scanner_access(user)

        try:
            scan = DataScan.objects.get(id=scan_id)
        except DataScan.DoesNotExist:
            raise DataScanDoesNotExist()

        if scan.is_running:
            raise DataScanIsAlreadyRunning()

        run_data_scan.delay(scan_id)
        return scan

    @staticmethod
    def run_scan(scan_id: int) -> None:
        """
        Executes the scan logic synchronously. Typically called from a Celery
        task. Iterates over the relevant workspaces and searches for matches
        using the workspace search tables. Results that were not re-identified
        in this run are removed.

        :param scan_id: Primary key of the scan to execute.
        """

        try:
            scan = DataScan.objects.get(id=scan_id)
        except DataScan.DoesNotExist:
            return

        now = timezone.now()
        scan.is_running = True
        scan.last_run_started_at = now
        scan.last_error = None
        scan.save(update_fields=["is_running", "last_run_started_at", "last_error"])

        new_results_count = 0
        try:
            if not LicenseHandler.instance_has_feature(DATA_SCANNER):
                scan.last_error = "Enterprise license no longer active"
                return

            if scan.scan_all_workspaces:
                workspace_ids = list(
                    Workspace.objects.filter(trashed=False).values_list("id", flat=True)
                )
            else:
                workspace_ids = list(
                    scan.workspaces.filter(trashed=False).values_list("id", flat=True)
                )

            pre_computed: dict = {}

            if scan.scan_type == SCAN_TYPE_PATTERN:
                regex = convert_pattern_to_regex(scan.pattern)
                has_special = _pattern_has_special_chars(scan.pattern)
                pre_computed["has_special_chars"] = has_special

                if has_special:
                    # The full regex cannot be matched against tsvector text because
                    # tokenization strips special characters. Use a broad token-level
                    # regex for the search table pre-filter and the full regex for
                    # verification against actual cell values.
                    broad_regex = _build_broad_token_regex(scan.pattern)
                    pre_computed["broad_regex"] = broad_regex

                if scan.whole_words:
                    # PostgreSQL POSIX word boundaries
                    pre_computed["pg_regex"] = r"\m" + regex + r"\M"
                    pre_computed["compiled"] = re.compile(
                        r"\b" + regex + r"\b", re.IGNORECASE
                    )
                else:
                    pre_computed["pg_regex"] = regex
                    pre_computed["compiled"] = re.compile(regex, re.IGNORECASE)

            elif scan.scan_type == SCAN_TYPE_LIST_OF_VALUES:
                pre_computed["values"] = list(
                    DataScanListItem.objects.filter(scan=scan).values_list(
                        "value", flat=True
                    )
                )

            elif scan.scan_type == SCAN_TYPE_LIST_TABLE:
                if not scan.source_table or not scan.source_field:
                    pre_computed["skip"] = True
                else:
                    source_table = scan.source_table
                    source_field = scan.source_field
                    model = source_table.get_model()
                    field_name = source_field.db_column
                    values = list(
                        model.objects.values_list(field_name, flat=True).distinct()
                    )
                    pre_computed["values"] = [str(v) for v in values if v]
                    pre_computed["exclude_table_id"] = source_table.id

            if not pre_computed.get("skip"):
                # Compute trashed field exclusions once for all workspaces. Three
                # separate indexed queries (one per trashed column) are combined with
                # set union in Python, avoiding an OR that would prevent index usage.
                trashed_field_ids = set(
                    Field.objects_and_trash.filter(trashed=True).values_list(
                        "id", flat=True
                    )
                )
                trashed_field_ids |= set(
                    Field.objects_and_trash.filter(table__trashed=True).values_list(
                        "id", flat=True
                    )
                )
                trashed_field_ids |= set(
                    Field.objects_and_trash.filter(
                        table__database__trashed=True
                    ).values_list("id", flat=True)
                )

                for workspace_id in workspace_ids:
                    if not SearchHandler.workspace_search_table_exists(workspace_id):
                        continue

                    search_model = SearchHandler.get_workspace_search_table_model(
                        workspace_id
                    )

                    if scan.scan_type == SCAN_TYPE_PATTERN:
                        new_results_count += DataScannerHandler._run_pattern_scan(
                            scan,
                            search_model,
                            pre_computed,
                            now,
                            trashed_field_ids,
                        )
                    elif scan.scan_type in (
                        SCAN_TYPE_LIST_OF_VALUES,
                        SCAN_TYPE_LIST_TABLE,
                    ):
                        exclude_table_id = pre_computed.get("exclude_table_id")
                        new_results_count += DataScannerHandler._run_list_scan(
                            scan,
                            search_model,
                            pre_computed["values"],
                            now,
                            trashed_field_ids,
                            exclude_table_id=exclude_table_id,
                        )

            scan.results.filter(last_identified_on__lt=now).delete()

        except Exception:
            scan.last_error = traceback.format_exc()
        finally:
            scan.is_running = False
            scan.last_run_finished_at = timezone.now()
            scan.save(
                update_fields=[
                    "is_running",
                    "last_run_finished_at",
                    "last_error",
                ]
            )

        if new_results_count > 0 and not scan.last_error:
            from baserow_enterprise.data_scanner.notification_types import (
                DataScanNewResultsNotificationType,
            )

            DataScanNewResultsNotificationType.notify_instance_admins(
                scan, new_results_count
            )

    @staticmethod
    def _run_pattern_scan(
        scan: DataScan,
        search_model: "AbstractSearchValue",
        pre_computed: dict,
        now: datetime,
        trashed_field_ids: set[int],
    ) -> int:
        """
        Runs a pattern scan against the workspace search tables. The search table is
        used as a fast pre-filter to find candidate rows, then actual cell values are
        looked up via ``get_search_expression`` to verify matches.

        For patterns with special characters (e.g. hyphens) a broad token-level regex
        is used for the pre-filter because tsvector tokenization strips those
        characters.

        :param scan: The scan being executed.
        :param search_model: The Django model for the workspace search table.
        :param pre_computed: Dict with `pg_regex`, `compiled`, `has_special_chars`, and
            optionally `broad_regex`.
        :param now: The current timestamp used for result bookkeeping.
        :param trashed_field_ids: Set of field IDs to exclude.
        :return: The number of newly created results.
        """

        compiled_regex = pre_computed["compiled"]
        has_special = pre_computed["has_special_chars"]
        search_regex = (
            pre_computed["broad_regex"] if has_special else pre_computed["pg_regex"]
        )

        candidates = list(
            search_model.objects.annotate(text_value=Cast("value", TextField()))
            .filter(text_value__iregex=search_regex)
            .values_list("field_id", "row_id")
        )

        def match_fn(value: str) -> Optional[str]:
            m = compiled_regex.search(value)
            return m.group(0) if m else None

        all_matches = DataScannerHandler._verify_candidates(
            candidates, match_fn, trashed_field_ids
        )
        return DataScannerHandler._bulk_upsert_results(
            scan, all_matches, now, trashed_field_ids
        )

    @staticmethod
    def _run_list_scan(
        scan: DataScan,
        search_model,
        values: list[str],
        now: datetime,
        trashed_field_ids: set[int],
        exclude_table_id: Optional[int] = None,
    ) -> int:
        """
        Searches the workspace search table for rows matching any of the given
        values using PostgreSQL full-text search, then verifies matches against
        actual cell values via ``get_search_expression``.

        :param scan: The scan being executed.
        :param search_model: The Django model for the workspace search table.
        :param values: The list of string values to search for.
        :param now: The current timestamp used for result bookkeeping.
        :param trashed_field_ids: Set of field IDs to exclude because the
            field, table, or database is trashed.
        :param exclude_table_id: When set, fields belonging to this table are
            excluded from results (used for list_table scans to avoid matching
            the source table itself).
        :return: The number of newly created results.
        """

        excluded_field_ids: set[int] = set()
        if exclude_table_id is not None:
            excluded_field_ids = set(
                Field.objects.filter(table_id=exclude_table_id).values_list(
                    "id", flat=True
                )
            )

        # Collect candidate (field_id, row_id) pairs from the search table.
        all_candidates: list[tuple[int, int]] = []
        batch_size = 100
        for i in range(0, len(values), batch_size):
            batch = values[i : i + batch_size]

            sanitized_parts: list[str] = []
            for search_value in batch:
                sanitized = DataScannerHandler._escape_list_value(
                    search_value, whole_words=scan.whole_words
                )
                if sanitized:
                    sanitized_parts.append(sanitized)

            if not sanitized_parts:
                continue

            combined_raw = " | ".join(f"({s})" for s in sanitized_parts)
            combined_query = SearchQuery(
                combined_raw,
                search_type="raw",
                config=SearchHandler.search_config(),
            )
            for field_id, row_id in search_model.objects.filter(
                value=combined_query
            ).values_list("field_id", "row_id"):
                if field_id not in excluded_field_ids:
                    all_candidates.append((field_id, row_id))

        # Build match function: find which list value matches the cell.
        if scan.whole_words:
            # Whole-word matching: the search value must appear as a complete word in
            # the cell. We use regex word boundaries for this.
            word_patterns = [
                (v, re.compile(r"\b" + re.escape(v) + r"\b", re.IGNORECASE))
                for v in values
            ]

            def match_fn(cell_value: str) -> Optional[str]:
                for original, pattern in word_patterns:
                    if pattern.search(cell_value):
                        return original
                return None
        else:
            values_pairs = [(v, v.lower()) for v in values]

            def match_fn(cell_value: str) -> Optional[str]:
                cell_lower = cell_value.lower()
                for original, lower_v in values_pairs:
                    if lower_v in cell_lower:
                        return original
                return None

        all_matches = DataScannerHandler._verify_candidates(
            all_candidates, match_fn, trashed_field_ids
        )
        return DataScannerHandler._bulk_upsert_results(
            scan, all_matches, now, trashed_field_ids
        )

    @staticmethod
    def _verify_candidates(
        candidates: list[tuple[int, int]],
        match_fn: Callable[[str], Optional[str]],
        trashed_field_ids: set[int],
    ) -> list[tuple[int, int, str]]:
        """
        Given ``(field_id, row_id)`` candidate pairs from a search-table pre-filter,
        looks up actual cell values using each field type's `get_search_expression` and
        applies *match_fn* to determine true matches.

        :param candidates: List of (field_id, row_id) pairs.
        :param match_fn: Receives a cell's string value and returns the
            matched substring/value on success, or ``None`` to skip.
        :param trashed_field_ids: Set of field IDs to exclude.
        :return: List of (field_id, row_id, matched_value) triples.
        """

        candidates = [
            (fid, rid) for fid, rid in candidates if fid not in trashed_field_ids
        ]
        if not candidates:
            return []

        candidate_field_ids = {field_id for field_id, _ in candidates}
        tables = Table.objects.filter(field__id__in=candidate_field_ids).distinct()

        # Build a field_id → (table, row_ids) index by iterating tables and checking
        # which candidate field_ids belong to each table's model.
        candidate_map: dict[int, set[int]] = defaultdict(set)
        for field_id, row_id in candidates:
            candidate_map[field_id].add(row_id)

        all_matches: list[tuple[int, int, str]] = []
        for table in tables:
            model = table.get_model()
            table_field_ids = candidate_field_ids & set(model._field_objects.keys())
            if not table_field_ids:
                continue

            row_ids: set[int] = set()
            candidate_set: set[tuple[int, int]] = set()
            for field_id in table_field_ids:
                for row_id in candidate_map[field_id]:
                    row_ids.add(row_id)
                    candidate_set.add((field_id, row_id))

            qs = model.objects.filter(id__in=row_ids)

            annotation_to_field_id: dict[str, int] = {}
            annotations = {}
            for field_id in table_field_ids:
                field_object = model._field_objects.get(field_id)
                if field_object is None:
                    continue
                field = field_object["field"]
                field_type = field_object["type"]
                annotation_name = f"_scan_f{field_id}"
                # Adding the field specific `get_search_expression` as annotation gives
                # us the full searchable string as text, which is exactly what we want
                # to use for the verification of the match.
                annotations[annotation_name] = field_type.get_search_expression(
                    field, qs
                )
                annotation_to_field_id[annotation_name] = field_id

            if not annotations:
                continue

            annotation_names = list(annotation_to_field_id.keys())
            rows = qs.annotate(**annotations).values_list("id", *annotation_names)

            for row_data in rows:
                row_id = row_data[0]
                for i, annotation_name in enumerate(annotation_names):
                    field_id = annotation_to_field_id[annotation_name]
                    if (field_id, row_id) not in candidate_set:
                        continue
                    value = row_data[i + 1]
                    if value is None:
                        continue
                    matched = match_fn(str(value))
                    if matched is not None:
                        all_matches.append((field_id, row_id, matched))

        return all_matches

    @staticmethod
    def _escape_list_value(value: str, whole_words: bool = True) -> str:
        """
        Escapes a search value for use in a PostgreSQL tsquery. When `whole_words` is
        True the trailing `:*` prefix wildcard is omitted so that only exact token
        matches are returned.

        :param value: The raw search value.
        :param whole_words: When True, do not add the `:*` wildcard.
        :return: A sanitized tsquery fragment, or an empty string.
        """

        text = SearchHandler.escape_query(value)
        if not text or not text.strip():
            return ""
        words = text.strip().split()
        parts = " <-> ".join(f"$${w}$$" for w in words)
        if not whole_words:
            parts = f"{parts}:*"
        return parts

    @staticmethod
    def _bulk_upsert_results(
        scan: DataScan,
        matches: list[tuple[int, int, str]],
        now: datetime,
        trashed_field_ids: set[int],
    ) -> int:
        """
        Bulk-upserts DataScanResult rows for a list of matches.

        :param scan: The scan the results belong to.
        :param matches: A list of (field_id, row_id, matched_value) tuples.
        :param now: The current timestamp.
        :param trashed_field_ids: Set of field IDs to exclude because the
            field, table, or database is trashed.
        :return: The number of newly created results.
        """

        if not matches:
            return 0

        # Build field_id -> table_id and table_id -> Table mappings in a single query
        # using select_related to avoid per-table lookups later.
        field_ids = {field_id for field_id, _, _ in matches}
        field_to_table: dict[int, int] = {}
        table_by_id: dict[int, Table] = {}
        for field_obj in Field.objects_and_trash.filter(
            id__in=field_ids
        ).select_related("table"):
            field_to_table[field_obj.id] = field_obj.table_id
            table_by_id[field_obj.table_id] = field_obj.table

        # Filter out matches for fields that no longer exist or where the field,
        # table, or database is trashed. This is done in Python against a small
        # blocklist rather than adding a large `field_id__in` filter to the search
        # query, which would be slower on instances with millions of fields.
        valid_matches = [
            (field_id, row_id, matched_value)
            for field_id, row_id, matched_value in matches
            if field_id in field_to_table and field_id not in trashed_field_ids
        ]

        # Filter out trashed rows. Query each table once for its (typically
        # small) set of trashed row IDs. The intersection with matched row IDs
        # is done in Python to avoid a potentially huge `id__in` clause.
        trashed_row_ids: set[tuple[int, int]] = set()
        for table_id, table in table_by_id.items():
            model = table.get_model()
            trashed_ids = set(
                model.objects_and_trash.filter(trashed=True).values_list(
                    "id", flat=True
                )
            )
            for row_id in trashed_ids:
                trashed_row_ids.add((table_id, row_id))

        if trashed_row_ids:
            valid_matches = [
                (field_id, row_id, matched_value)
                for field_id, row_id, matched_value in valid_matches
                if (field_to_table[field_id], row_id) not in trashed_row_ids
            ]

        if not valid_matches:
            return 0

        count_before = DataScanResult.objects.filter(scan=scan).count()

        batch_size = 500
        for i in range(0, len(valid_matches), batch_size):
            batch = valid_matches[i : i + batch_size]
            objects = [
                DataScanResult(
                    scan=scan,
                    table_id=field_to_table[field_id],
                    field_id=field_id,
                    row_id=row_id,
                    matched_value=str(matched_value),
                    first_identified_on=now,
                    last_identified_on=now,
                )
                for field_id, row_id, matched_value in batch
            ]
            DataScanResult.objects.bulk_create(
                objects,
                update_conflicts=True,
                unique_fields=["scan", "table", "row_id", "field"],
                update_fields=["matched_value", "last_identified_on"],
            )

        count_after = DataScanResult.objects.filter(scan=scan).count()
        return count_after - count_before

    @staticmethod
    def check_scans_due() -> None:
        """
        Periodic check that resets stale running scans and dispatches any
        scheduled scans whose interval has elapsed. Called by the
        `check_data_scans_due` Celery beat task.
        """

        now = timezone.now()

        stale_threshold = now - timedelta(hours=STALE_SCAN_THRESHOLD_HOURS)
        DataScan.objects.filter(
            is_running=True,
            last_run_started_at__lt=stale_threshold,
        ).update(
            is_running=False,
            last_error="Scan timed out and was automatically reset",
        )

        if not LicenseHandler.instance_has_feature(DATA_SCANNER):
            return

        scans = DataScan.objects.filter(is_running=False).exclude(frequency="manual")
        for scan in scans:
            interval = FREQUENCY_INTERVALS.get(scan.frequency)
            if not interval:
                continue

            if scan.last_run_started_at is None or (
                now - scan.last_run_started_at >= interval
            ):
                run_data_scan.delay(scan.id)
