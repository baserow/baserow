import collections
import typing
from datetime import date, datetime, timezone
from functools import partial
from operator import attrgetter
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import QuerySet

from baserow_premium.views.exceptions import CalendarViewHasNoDateField
from baserow_premium.views.models import CalendarView
from icalendar import Calendar, Event

from baserow.contrib.database.fields.models import Field
from baserow.core.db import specific_queryset

# required by https://icalendar.org/iCalendar-RFC-5545/3-7-3-product-identifier.html
ICAL_PROD_ID = "Baserow / baserow.io"
# required by https://icalendar.org/iCalendar-RFC-5545/3-7-4-version.html
ICAL_VERSION = "2.0"


def row_url_maker(view: CalendarView) -> typing.Callable[[str], str]:
    """
    Builds row url maker function.

    :param view:
    :return:
    """

    view_id = view.id
    table_id = view.table_id
    database_id = view.table.database_id

    def url_maker(row_id: str) -> str:
        """
        Generate view-specific frontend url for a given row id.

        :return: Full frontend url
        """

        return urljoin(
            settings.PUBLIC_WEB_FRONTEND_URL,
            f"/database/{database_id}" f"/table/{table_id}/{view_id}" f"/row/{row_id}",
        )

    return url_maker


def description_maker(
    fields: list[typing.Callable],
) -> typing.Callable[[collections.abc.Iterable], str]:
    """
    Builds a helper function to build description from visible fields in a view.

    :param fields: Each element of `fields` is a callable that should do two things:
      * retrieve specific field's value
      * make human-friendly value out of it. Internally, we use
      `FieldType.get_human_readable_value` here to render such representation.
    :returns: a callable to be used on a row with fields corresponding to ones
    expected in `fields` list.
    """

    def convert(row: typing.Any) -> typing.Generator[str, None, None]:
        """
        Iterates over row's fields and yields stringified values
        """

        for converter in fields:
            out = converter(row)
            yield out

    def make_descriptions(row: typing.Any) -> str:
        """
        Build an event description from a row
        """

        desc = [v for v in convert(row)]
        return " - ".join(desc)

    return make_descriptions


def make_dtstamp(
    in_dtstamp: datetime | date, target_tz: ZoneInfo | None = None
) -> date | datetime:
    """
    helper function to make tz-aware datetime object in user-specified timezone.

    If in_dtstamp is a date, it will be returned as-is.
    """

    if not isinstance(in_dtstamp, date):
        raise TypeError(f"Invalid date/time type: {type(in_dtstamp).__name__}")
    if not isinstance(in_dtstamp, datetime):
        return in_dtstamp
    if target_tz:
        return in_dtstamp.astimezone(target_tz)
    return in_dtstamp


def make_field_renderer(
    getter: typing.Callable, renderer: typing.Callable
) -> typing.Callable[[typing.Any], str]:
    """
    Chains together functions to get a field value and render it to readable form.

    Used by description_maker call.
    """

    def _call(row: typing.Any) -> str:
        return renderer(getter(row))

    return _call


def build_calendar(
    qs: QuerySet,
    view: CalendarView,
    user_timezone: str = "UTC",
    limit: int | None = None,
) -> Calendar:
    """
    Build Calendar object from a CalendarView-related QuerySet.

    :param qs: QuerySet's model must match view's model. QuerySet should not have any
    sorting/limiting applied, because it will be processed in this function. Events will
    be sorted by a CalendarView's selected date field.
    :param view: provides information about selected date field and visible fields in
      selected order for this view, which are used to build description string.
    :param user_timezone: is an optional timezone name to set on timestamps. It will be
      used if CalendarView's date field was created as a datetime field. It won't be
      used if date field is a date.
    :param limit: when provided, tells how many events should be returned in ICalendar
      feed.
    """

    date_field = view.date_field
    if not date_field or not date_field.specific:
        raise CalendarViewHasNoDateField()

    date_field_name = date_field.db_column
    dget: typing.Callable[[typing.Any], datetime | date] = attrgetter(date_field_name)

    # we skip CalendarViewType.get_visible_field_options_in_order to retrieve fields in
    # more optimized way, but still requires n queries depending on number of different
    # field types related - each field type will have own prefetch related call.
    fields = specific_queryset(
        Field.objects.filter(
            calendarviewfieldoptions__calendar_view_id=view.id,
            calendarviewfieldoptions__hidden=False,
        )
        .order_by("calendarviewfieldoptions__order", "id")
        .select_related("content_type")
    )

    field_type_registry = Field.get_type_registry()
    visible_fields: list[typing.Callable] = []

    # we're reaching for updated_on and date field even if they're not visible
    # when creating vevents for Calendar
    query_field_names = {date_field_name, "updated_on"}

    for field in fields:
        field = field.specific
        field_class = field.specific_class
        field_type = field_type_registry.get_for_class(field_class)
        field_name = field.db_column

        field_value_getter = attrgetter(field_name)

        # internally converter uses ViewType.get_human_readable_value interface which
        # requires a context object in field_object. We don't use this object outside
        # this call, so we'll pack it to a standalone callable which will build a
        # string from a field value
        field_value_converter = partial(
            field_type.get_human_readable_value,
            field_object={"type": field_type, "name": field_name, "field": field},
        )

        field_value_renderer = make_field_renderer(
            field_value_getter,
            field_value_converter,
        )

        visible_fields.append(field_value_renderer)
        query_field_names.add(field_name)

    filter_qs = {f"{date_field_name}__isnull": False}

    # Calculate which fields must be deferred to optimize performance. The idea is
    # that only the `query_field_names` and `select_related_fields` are kept because
    # they must be included in the result.
    model_field_names = {field.name for field in qs.model._meta.get_fields()}
    select_related_fields = set(qs.query.select_related or [])
    fields_to_defer = model_field_names - query_field_names - select_related_fields

    qs = qs.filter(**filter_qs).defer(*fields_to_defer)
    if limit:
        qs = qs[:limit]

    target_timezone_info = ZoneInfo(user_timezone) if user_timezone else timezone.utc

    if getattr(date_field, "date_include_time", False) and (
        field_timezone := getattr(date_field, "date_force_timezone", None)
    ):
        target_timezone_info = ZoneInfo(field_timezone)

    make_description = description_maker(visible_fields)

    ical = Calendar()
    # prodid and version are constant and required by ical spec
    ical.add("prodid", ICAL_PROD_ID)
    ical.add("version", ICAL_VERSION)
    # X-WR-CALNAME:test
    # X-WR-TIMEZONE:Europe/Warsaw
    ical.add("x-wr-calname", view.name)
    ical.add("name", view.name)
    ical.add("x-wr-timezone", target_timezone_info)
    url_maker = row_url_maker(view)

    for row in qs:
        dstart = dget(row)
        description = make_description(row)
        evt = Event()
        row_url = url_maker(row.id)
        modified_at = make_dtstamp(row.updated_on, target_timezone_info)
        # uid required to identify the event.
        # Some calendar apps, like Google Calendar require uid to be not a simple value.
        # uid 1 won't work, but row url will.
        evt.add("uid", row_url)

        # row modification will tell if the event was modified since last read
        evt.add("dtstamp", modified_at)
        evt.add("last-modified", modified_at)
        # event start
        evt.add("dtstart", make_dtstamp(dstart, target_timezone_info))
        # event summary and description
        evt.add("summary", description)
        evt.add("description", description)
        evt.add("location", row_url)
        ical.add_component(evt)
    return ical
