from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo

from django.contrib.auth.models import AbstractUser
from django.db.models import Count, Q, QuerySet

from baserow_premium.views.exceptions import CalendarViewHasNoDateField
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL, TimelineView
from baserow_premium.views.view_types import TimelineViewType
from rest_framework.request import Request

from baserow.contrib.database.api.views.utils import (
    PublicViewFilteredQuerySet,
    get_public_view_filtered_queryset,
    get_view_filtered_queryset,
)
from baserow.contrib.database.fields.models import Field, SingleSelectField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import (
    view_ownership_type_registry,
    view_type_registry,
)


def get_rows_grouped_by_single_select_field(
    user: Optional[AbstractUser],
    view: View,
    single_select_field: SingleSelectField,
    option_settings: Dict[str, Dict[str, int]] = None,
    default_limit: int = 40,
    default_offset: int = 0,
    adhoc_filters: Optional[AdHocFilters] = None,
    model: Optional[GeneratedTableModel] = None,
    base_queryset: Optional[QuerySet] = None,
) -> Dict[str, Dict[str, Union[int, list]]]:
    """
    This method fetches the rows grouped by a single select field in a query
    efficient manner. Optionally `limit` and `offset` settings can be provided per
    option. If the option settings not provided, then rows for all the select options
    will be fetched. If one or more options have been provided, then only the rows
    for those will be fetched.

    Example:

    get_rows_grouped_by_single_select_field(
        ...
        options_settings={
            "1": {"limit": 10, "offset": 10},
            "2": {"limit": 10, "offset": 20}
        }
    )

    :param user: The user on whose behalf the view is requested. Can be used for
        permission checks.
    :param view: The view where to fetch the fields from.
    :param single_select_field: The single select field where the rows must be
        grouped by.
    :param option_settings: Optionally, additional `limit` and `offset`
        configurations per field option can be provided.
    :param default_limit: The default limit that applies to all options if no
        specific settings for that field have been provided.
    :param default_offset: The default offset that applies to all options if no
        specific settings for that field have been provided.
    :param adhoc_filters: The optional ad hoc filters if they should be used
        instead of view filters.
    :param model: Additionally, an existing model can be provided so that it doesn't
        have to be generated again.
    :param base_queryset: Optionally an alternative base queryset can be provided
        that will be used to fetch the rows. This should be provided if additional
        filters and/or sorts must be added.
    :return: The fetched rows including the total count.
    """

    table = view.table

    if option_settings is None:
        option_settings = {}

    if model is None:
        model = table.get_model()

    if base_queryset is None:
        base_queryset = model.objects.all().enhance_by_fields().order_by("order", "id")

    if adhoc_filters is None:
        adhoc_filters = AdHocFilters()

    base_option_queryset = base_queryset

    # Check if the view ownership type is enforcing the filters to be applied. If
    # so, then regardless of what argument is provided, the filters are applied to
    # the queryset. This can be useful if the view restricts access to rows that
    # don't match the filters.
    view_ownership_type = view_ownership_type_registry.get(view.ownership_type)
    if not adhoc_filters.has_any_filters or view_ownership_type.enforce_apply_filters(
        user, view
    ):
        base_option_queryset = ViewHandler().apply_filters(view, base_option_queryset)

    if adhoc_filters.has_any_filters:
        base_option_queryset = adhoc_filters.apply_to_queryset(
            model, base_option_queryset
        )

    all_filters = Q()
    count_aggregates = {}
    all_options = list(single_select_field.select_options.all())
    all_option_ids = [option.id for option in all_options]

    def get_id_and_string(option):
        return (
            option.id if option else None,
            str(option.id) if option else "null",
        )

    for select_option in [None] + all_options:
        option_id, option_string = get_id_and_string(select_option)

        # If option settings have been provided, we only want to return rows for
        # those options, otherwise we will include all options.
        if len(option_settings) > 0 and option_string not in option_settings:
            continue

        option_setting = option_settings.get(option_string, {})
        limit = option_setting.get("limit", default_limit)
        offset = option_setting.get("offset", default_offset)

        if option_id is None:
            # Somehow the `Count` aggregate doesn't support an empty `__in` lookup.
            # That's why we always add the `-1` value that never exists to make sure
            # there is always a value in there.
            filters = ~Q(
                **{f"field_{single_select_field.id}_id__in": all_option_ids + [-1]}
            )
        else:
            filters = Q(**{f"field_{single_select_field.id}_id": option_id})

        # We don't want to execute a single query for each select option,
        # so we create a subquery that finds the ids of the rows related to the
        # option group. After the single query has been executed we can group the rows.
        sub_queryset = base_option_queryset.filter(filters).values_list(
            "id", flat=True
        )[offset : offset + limit]
        all_filters |= Q(id__in=sub_queryset)

        # Same goes for fetching the total count. We will construct a single query,
        # that calculates to total amount of rows per option.
        count_aggregates[option_string] = Count(
            "pk",
            filter=filters,
        )

    queryset = list(base_queryset.filter(all_filters))
    counts = base_option_queryset.aggregate(**count_aggregates)

    rows = defaultdict(lambda: {"count": 0, "results": []})

    for row in queryset:
        option_id = getattr(row, f"field_{single_select_field.id}_id")
        option_string = str(option_id) if option_id in all_option_ids else "null"
        rows[option_string]["results"].append(row)

    for key, value in counts.items():
        rows[key]["count"] = value

    return rows


def get_rows_grouped_by_date_field(
    user: Optional[AbstractUser],
    view: View,
    date_field: Field,
    from_timestamp: datetime,
    to_timestamp: datetime,
    user_timezone: str,
    search: Optional[str] = None,
    search_mode: Optional[str] = None,
    limit: int = 40,
    offset: int = 0,
    model: Optional[GeneratedTableModel] = None,
    base_queryset: Optional[QuerySet] = None,
    adhoc_filters: Optional[AdHocFilters] = None,
    combine_filters: bool = False,
) -> Dict[str, Dict[str, Union[int, list]]]:
    """
    This method fetches the rows grouped into per day buckets given the row's values
    in the provided date_field. Rows which don't have a cell value in the date_field
    field within the from_timestamp and to_timestamp range will be excluded.

    :param user: The user on whose behalf the rows are request. Can be used for
        permission checking.
    :param view: The view where to fetch the fields from.
    :param date_field: The date field that rows will be grouped into day buckets for
    :param from_timestamp: Only rows with a date_field cell value >= to this value
        will be fetched.
    :param to_timestamp: Only rows with a date_field cell value < to this value
        will be fetched.
    :param user_timezone: The timezone of the user.
    :param limit: The maximum number of rows per date bucket.
    :param offset: The offset in number of rows to fetch per date bucket. For example
        when offset=0 rows will be returned starting from the 0th row in each bucket,
        when offset=40 the first 40 rows will be skipped in each bucket.
    :param model: Additionally, an existing model can be provided so that it doesn't
        have to be generated again.
    :param base_queryset: Optionally an alternative base queryset can be provided
        that will be used to fetch the rows. This should be provided if additional
        filters and/or sorts must be added.
    :param adhoc_filters: The optional ad hoc filters. Depending on `combine_filters`
        they will be added on top of or replace view filters.
    :param combine_filters: If set to `True`, both view filters and adhoc filters will
        be applied. If set to `False` adhoc filters will be applied instead of view
        filters, if present. This flag should be set by a caller depending on a view's
        publicity status.
    :return: The fetched rows including the total count.
    """

    table = view.table

    if model is None:
        model = table.get_model()

    date_field = date_field.specific
    date_field_type = field_type_registry.get_by_model(date_field)
    if not date_field_type.can_represent_date(date_field):
        raise CalendarViewHasNoDateField()
    if base_queryset is None:
        base_queryset = (
            model.objects.all()
            .enhance_by_fields()
            .order_by(f"field_{date_field.id}", "order", "id")
        )
    if search is not None:
        base_queryset = base_queryset.search_all_fields(search, search_mode=search_mode)

    # Check if the view ownership type is enforcing the filters to be applied. If
    # so, then regardless of what argument is provided, the filters are applied to
    # the queryset. This can be useful if the view restricts access to rows that
    # don't match the filters.
    view_ownership_type = view_ownership_type_registry.get(view.ownership_type)
    if view_ownership_type.enforce_apply_filters(user, view):
        combine_filters = True

    if combine_filters:
        base_option_queryset = ViewHandler().apply_filters(view, base_queryset)
        if adhoc_filters and adhoc_filters.has_any_filters:
            base_option_queryset = adhoc_filters.apply_to_queryset(
                model, base_option_queryset
            )

    else:
        if adhoc_filters and adhoc_filters.has_any_filters:
            base_option_queryset = adhoc_filters.apply_to_queryset(model, base_queryset)
        else:
            base_option_queryset = ViewHandler().apply_filters(view, base_queryset)

    all_filters = Q()
    count_aggregates = {}

    # Target timezone is the timezone that will be used
    # for aggregation of the results into date buckets
    if getattr(date_field, "date_include_time", False):
        field_timezone = getattr(date_field, "date_force_timezone", "UTC")
        target_timezone = field_timezone or user_timezone
        target_timezone_info = ZoneInfo(target_timezone) if target_timezone else None
        from_timestamp = from_timestamp.astimezone(tz=target_timezone_info)
        to_timestamp = to_timestamp.astimezone(tz=target_timezone_info)
    else:
        # If our field is just representing dates, then it makes no sense to split it
        # by timezone as a date on its own cannot have a timezone.
        target_timezone_info = timezone.utc
        # We are querying upto but not including to_timestamp, so if someone
        # queries to_timestamp=2023-01-01 00:00 we should include rows with dates
        # on the 1st, however if we don't add one day django with query for
        # date < 2023-01-01 so we add one to make sure to include those.
        to_timestamp = (to_timestamp + timedelta(days=1)).date()
        from_timestamp = from_timestamp.date()

    for start, end in generate_per_day_intervals(from_timestamp, to_timestamp):
        date_filters = Q(
            **{
                f"field_{date_field.id}__gte": start,
                f"field_{date_field.id}__lt": end,
            }
        )

        sub_queryset = base_option_queryset.filter(date_filters).values_list(
            "id", flat=True
        )[offset : offset + limit]
        all_filters |= Q(id__in=sub_queryset)

        start_date = start.date() if isinstance(start, datetime) else start
        count_aggregates[str(start_date)] = Count(
            "pk",
            filter=date_filters,
        )

    queryset = list(base_queryset.filter(all_filters))
    counts = base_option_queryset.aggregate(**count_aggregates)

    rows = defaultdict(lambda: {"count": 0, "results": []})

    for row in queryset:
        date_field_value = getattr(row, f"field_{date_field.id}")
        if isinstance(date_field_value, date):
            date_value = str(date_field_value)
        if isinstance(date_field_value, datetime):
            date_value = str(
                date_field_value.astimezone(tz=target_timezone_info).date()
            )
        rows[date_value]["results"].append(row)

    for key, value in counts.items():
        rows[key]["count"] = value

    return rows


def get_timeline_view_filtered_queryset(
    user: AbstractUser,
    view: TimelineView,
    adhoc_filters: Optional[AdHocFilters] = None,
    order_by: Optional[str] = None,
    query_params: Optional[Dict[str, str]] = None,
) -> QuerySet:
    """
    Checks if the provided timeline view has a valid date field and raises an exception
    if it doesn't. If the date fields are valid, then the filtered queryset is returned.

    :param user: The user on whose behalf the queryset is filtered.  This is needed for
        permission checks.
    :param view: The timeline view where to fetch the fields from.
    :param adhoc_filters: The optional ad hoc filters if they should be used
        instead of view filters.
    :param order_by: The order by fields and directions.
    :param query_params: The query parameters that can be used to filter the rows.
    :return: The filtered queryset.
    """

    timeline_view_type: TimelineViewType = view_type_registry.get_by_model(view)
    timeline_view_type.raise_if_invalid_date_settings(view)

    return get_view_filtered_queryset(user, view, adhoc_filters, order_by, query_params)


def get_public_timeline_view_filtered_queryset(
    view: TimelineView, request: Request, query_params: Optional[Dict[str, str]] = None
) -> PublicViewFilteredQuerySet:
    """
    Validates the provided timeline view and raises an exception if it's invalid. If the
    view is valid, then the public filtered queryset is returned.

    :param view: The timeline view where to fetch the fields from.
    :param request: The request object.
    :param query_params: The validated query parameters that can be used to filter the
        rows.
    :return: The public filtered queryset.
    """

    timeline_view_type: TimelineViewType = view_type_registry.get_by_model(view)
    timeline_view_type.raise_if_invalid_date_settings(view)

    return get_public_view_filtered_queryset(view, request, query_params)


def to_midnight(dt: datetime) -> datetime:
    """
    Converts a date time to midnight on that date.
    """

    return datetime.combine(
        dt.date(),
        datetime.min.time(),
        tzinfo=dt.tzinfo,
    )


def generate_per_day_intervals(
    from_timestamp: Union[datetime, date],
    to_timestamp: Union[datetime, date],
) -> Union[List[Tuple[datetime, datetime]], List[Tuple[date, date]]]:
    """
    Generates a series of which date intervals splitting date interval
    starting at from_timestamp and ending at to_timestamp into days starting at midnight
    and ending at the next midnight.

    The first interval will start at from_timestamp and the last interval will end at
    to_timestamp.

    For example:

    from_timestamp = 9AM 2023/01/01
    to_timestamp = 10PM 2023/01/03
    result = [
        (9AM 2023/01/01, 12AM 2023/01/02),
        (12AM 2023/01/02, 12AM 2023/01/03),
        (12AM 2023/01/03, 10PM 2023/01/03),
    ]
    """

    intervals = []

    interval_start = from_timestamp
    while interval_start < to_timestamp:
        start_plus_day = interval_start + timedelta(days=1)
        if isinstance(start_plus_day, datetime):
            next_midnight = to_midnight(start_plus_day)
        else:
            next_midnight = start_plus_day
        interval_end = min(next_midnight, to_timestamp)
        intervals.append((interval_start, interval_end))
        interval_start = interval_end

    return intervals


def delete_personal_views(user_id: int):
    """
    Deletes all personal views associated with the provided user.

    :param user_id: The id of the user for whom to delete personal views.
    """

    View.objects.filter(ownership_type=OWNERSHIP_TYPE_PERSONAL).filter(
        owned_by__id=user_id
    ).delete()
