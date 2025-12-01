from collections import defaultdict, namedtuple
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

from django.db.models.expressions import Exists, OuterRef
from django.db.models.query import QuerySet

from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.core.db import specific_iterator

from .handler import ViewHandler
from .models import View
from .registries import view_type_registry

FilterCheck = namedtuple(
    "FilterCheck",
    ["view", "filter_qs", "can_cache", "is_fully_cached"],
)


@dataclass
class FilteredViewRows:
    """
    Keeps track of which rows are allowed to be sent as a public signal
    for a particular view.

    When no row ids are set it is assumed that any row id is allowed.
    """

    ALL_ROWS_ALLOWED = None

    view: View
    allowed_row_ids: Optional[Set[int]]

    def all_allowed(self):
        return self.allowed_row_ids is FilteredViewRows.ALL_ROWS_ALLOWED

    def __iter__(self):
        return iter((self.view, self.allowed_row_ids))


class FilteredViewRowChecker:
    """
    A helper class to check in which views a row is visible. It will pre-calculate
    upfront for a specific table which views are always visible, which public
    views can have row check results cached for and finally will pre-construct and
    reuse querysets for performance reasons.
    """

    def __init__(
        self,
        model: GeneratedTableModel,
        views_queryset: QuerySet,
        only_include_views_which_want_realtime_events: bool,
        updated_field_ids: Optional[Iterable[int]] = None,
    ):
        """
        :param model: The model of the table including all fields.
        :param views_queryset: The queryset to fetch the views where to check the row
            in.
        :param only_include_views_which_want_realtime_events: If True will only look
            for public views where
            ViewType.when_shared_publicly_requires_realtime_events is True.
        :param updated_field_ids: An optional iterable of field ids which will be
            updated on rows passed to the checker. If the checker is used on the same
            row multiple times and that row has been updated it will return invalid
            results unless you have correctly populated this argument.
        """

        self._model = model
        self._views_queryset = views_queryset
        self._updated_field_ids = updated_field_ids
        self._views_with_filters = []
        self._views_without_filters = []
        self._view_row_check_cache = defaultdict(dict)
        handler = ViewHandler()
        for view in specific_iterator(
            self._views_queryset,
            per_content_type_queryset_hook=(
                lambda model, queryset: view_type_registry.get_by_model(
                    model
                ).enhance_queryset(queryset)
            ),
        ):
            if only_include_views_which_want_realtime_events:
                view_type = view_type_registry.get_by_model(view.specific_class)
                if not view_type.when_shared_publicly_requires_realtime_events:
                    continue

            if len(view.viewfilter_set.all()) == 0:
                # If there are no view filters for this view then any row must always
                # be visible in this view.
                self._views_without_filters.append(view)
            else:
                filter_qs = handler.apply_filters(view, model.objects)
                self._views_with_filters.append(
                    (
                        view,
                        filter_qs,
                        self._view_row_checks_can_be_cached(view),
                    )
                )

    def _view_row_checks_can_be_cached(self, view):
        if self._updated_field_ids is None:
            # If the updated field_ids are `None`, then we assume that all the cell
            # values of all fields have been updated.
            return False
        for view_filter in view.viewfilter_set.all():
            if view_filter.field_id in self._updated_field_ids:
                # We found a view filter for a field which will be updated hence we
                # need to check both before and after a row update occurs
                return False
        # There is no filter on any of the updated fields, hence we only need to
        # check if a given row is visible in the view once, because any changes to the
        # fields in said row won't be for fields with filters and so the result of
        # the first check will be still valid for any subsequent checks.
        return True

    def _rows_with_visibility_flags(self, row_ids, views_with_filters):
        """
        Single query over the row model for the given ids, annotated with a boolean
        per view indicating if that row is visible in that view.

        :param row_ids:
        :param views_with_filters:
        """

        base = self._model.objects.filter(id__in=row_ids)

        annotations = {}
        for view, filter_qs, _ in views_with_filters:
            annotations[f"visible_v{view.id}"] = Exists(
                filter_qs.filter(pk=OuterRef("pk"))
            )

        return base.annotate(**annotations).values("id", *annotations.keys())

    def get_filtered_views_where_row_is_visible(self, row):
        return [
            filtered_view_rows.view
            for filtered_view_rows in self.get_filtered_views_where_rows_are_visible(
                [row]
            )
        ]

    def get_filtered_views_where_rows_are_visible(
        self, rows: List[GeneratedTableModel]
    ) -> List[FilteredViewRows]:
        """
        Checks if the provided rows match the filters of all the views provided in the
        `views_queryset` argument as constructor, using one single query when needed.

        We cache per (view_id, row_id) when filters do not involve updated fields.
        Both positive and negative results are cached in that case to avoid future
        reads.

        :param rows: List of rows that must be checked in all the views of the provided
            `_views_queryset` views.
        """

        result_for_views: List[FilteredViewRows] = []
        input_row_ids: List[int] = [row.id for row in rows]

        # Plan which views need querying and which are already fully decided by cache.
        view_checks: List[FilterCheck] = []
        row_ids_to_check: Set[int] = set()

        for view, filter_qs, can_use_cache in self._views_with_filters:
            if can_use_cache:
                cache_for_view: Dict[int, bool] = self._view_row_check_cache[view.id]
                # Fully cached means every row_id has a cached bool (True or False).
                missing_row_ids = [
                    rid for rid in input_row_ids if rid not in cache_for_view
                ]
                is_fully_cached = len(missing_row_ids) == 0
                if not is_fully_cached:
                    row_ids_to_check.update(missing_row_ids)
                view_checks.append(
                    FilterCheck(
                        view=view,
                        filter_qs=filter_qs,
                        can_cache=True,
                        is_fully_cached=is_fully_cached,
                    )
                )
            else:
                row_ids_to_check.update(input_row_ids)
                view_checks.append(
                    FilterCheck(
                        view=view,
                        filter_qs=filter_qs,
                        can_cache=False,
                        is_fully_cached=False,
                    )
                )

        # Run one annotated query for all outstanding (view,row) combinations.
        checks_needing_query = [
            (vc.view, vc.filter_qs, vc.can_cache)
            for vc in view_checks
            if not vc.is_fully_cached
        ]
        visible_row_ids_by_view_id: Dict[int, Set[int]] = {
            vc.view.id: set() for vc in view_checks
        }

        if checks_needing_query and row_ids_to_check:
            # For each row in the batch, each view contributes a visible_v{view.id}
            # boolean.
            for row_record in self._rows_with_visibility_flags(
                row_ids_to_check, checks_needing_query
            ):
                row_id = row_record["id"]
                for view, _filter_qs, can_cache in checks_needing_query:
                    key = f"visible_v{view.id}"
                    is_visible = bool(row_record[key])
                    if is_visible:
                        visible_row_ids_by_view_id[view.id].add(row_id)
                    if can_cache:
                        # Cache both outcomes to allow zero queries later.
                        self._view_row_check_cache[view.id][row_id] = is_visible

        # Emit results in the same order as _views_with_filters.
        for view_check in view_checks:
            cache_for_view: Dict[int, bool] = self._view_row_check_cache[
                view_check.view.id
            ]

            if view_check.is_fully_cached:
                # All rows in this batch are in cache: only return those cached as True.
                visible_ids_for_view = {
                    rid for rid in input_row_ids if cache_for_view.get(rid, False)
                }
            else:
                visible_ids_for_view = set(
                    visible_row_ids_by_view_id[view_check.view.id]
                )
                if view_check.can_cache:
                    visible_ids_for_view.update(
                        rid for rid in input_row_ids if cache_for_view.get(rid, False)
                    )

            if visible_ids_for_view:
                result_for_views.append(
                    FilteredViewRows(view_check.view, visible_ids_for_view)
                )

        # Views without filters allow all rows, so they must be added.
        for view_without_filters in self._views_without_filters:
            result_for_views.append(
                FilteredViewRows(
                    view_without_filters, FilteredViewRows.ALL_ROWS_ALLOWED
                )
            )

        return result_for_views
