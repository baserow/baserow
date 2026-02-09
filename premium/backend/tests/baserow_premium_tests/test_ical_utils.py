from datetime import date, datetime, timedelta, timezone
from operator import attrgetter
from zoneinfo import ZoneInfo

from django.utils.timezone import override

import pytest

from baserow.contrib.database.views.handler import ViewHandler
from baserow_premium.ical_utils import (
    build_calendar,
    description_maker,
    make_dtstamp,
    make_field_renderer,
)
from baserow_premium.views.models import CalendarView

NUM_EVENTS = 20
BASEROW_ICAL_VIEW_MAX_EVENTS = 5


def test_ical_generation_with_datetime(
    db, premium_data_fixture, api_client, data_fixture
):
    """
    Test ical feed with calendar with datetime field
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_long_text_field(table=table, user=user)
    field_extra = data_fixture.create_text_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=True,
    )
    all_fields = [field_title, field_description, field_extra, field_num, date_field]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()

    amsterdam = ZoneInfo("Europe/Amsterdam")
    start = datetime.now(tz=amsterdam).replace(microsecond=0)

    def make_values(num):
        curr = 0
        field_names = [f"field_{f.id}" for f in all_fields]

        while curr < num:
            values = [
                f"title {curr}",
                f"description {curr}",
                f"extra {curr}",
                curr,
                start + timedelta(days=1, hours=curr),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            tmodel.objects.create(**row)

    make_values(NUM_EVENTS)

    assert not calendar_view.ical_public
    assert not calendar_view.ical_feed_url

    cal = build_calendar(tmodel.objects.all(), calendar_view)
    events = cal.walk("VEVENT")
    assert len(events)
    for idx, evt in enumerate(events):
        elm = evt.get("DTSTART")
        # elm.dt is a date
        assert isinstance(elm.dt, datetime)
        assert elm.dt.astimezone(timezone.utc) == (
            start + timedelta(days=1, hours=idx)
        ).astimezone(timezone.utc)


def test_ical_generation_with_datetime_with_tz(
    db, premium_data_fixture, api_client, data_fixture
):
    """
    Test ical feed with calendar with datetime field
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_text_field(table=table, user=user)
    field_extra = data_fixture.create_text_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True, date_force_timezone="Australia/Canberra"
    )
    all_fields = [field_title, field_description, field_extra, field_num, date_field]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()

    amsterdam = ZoneInfo("Europe/Amsterdam")
    start = datetime.now(tz=amsterdam).replace(microsecond=0)

    def make_values(num):
        curr = 0
        field_names = [f"field_{f.id}" for f in all_fields]

        while curr < num:
            values = [
                f"title {curr}",
                f"description {curr}",
                f"extra {curr}",
                curr,
                start + timedelta(days=1, hours=curr),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            tmodel.objects.create(**row)

    make_values(NUM_EVENTS)

    assert not calendar_view.ical_public
    assert not calendar_view.ical_feed_url

    cal = build_calendar(tmodel.objects.all(), calendar_view)
    events = cal.walk("VEVENT")
    assert len(events)
    for idx, evt in enumerate(events):
        elm = evt.get("DTSTART")
        # elm.dt is a date
        assert isinstance(elm.dt, datetime)
        assert elm.dt.astimezone(timezone.utc) == (
            start + timedelta(days=1, hours=idx)
        ).astimezone(timezone.utc)


def test_ical_generation_with_date(db, premium_data_fixture, api_client, data_fixture):
    """
    Test ical feed with calendar with datetime field
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_text_field(table=table, user=user)
    field_extra = data_fixture.create_text_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )
    all_fields = [field_title, field_description, field_extra, field_num, date_field]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()

    amsterdam = ZoneInfo("Europe/Amsterdam")
    start = date.today()

    def make_values(num):
        curr = 0
        field_names = [f"field_{f.id}" for f in all_fields]

        while curr < num:
            values = [
                f"title {curr}",
                f"description {curr}",
                f"extra {curr}",
                curr,
                start + timedelta(days=curr + 1),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            tmodel.objects.create(**row)

    make_values(NUM_EVENTS)

    assert not calendar_view.ical_public
    assert not calendar_view.ical_feed_url

    cal = build_calendar(tmodel.objects.all(), calendar_view)
    events = cal.walk("VEVENT")
    assert len(events)
    for idx, evt in enumerate(events):
        elm = evt.get("DTSTART")
        # elm.dt is a date
        assert isinstance(elm.dt, date)
        assert not isinstance(elm.dt, datetime)
        assert elm.dt == start + timedelta(days=1 + idx)


@pytest.mark.parametrize(
    "current_timezone,test_input,expected_output,raises",
    [
        (
            "UTC",
            (datetime(year=2020, month=1, day=1),),
            datetime(year=2020, month=1, day=1),
            None,
        ),
        (
            "UTC",
            (datetime(year=2020, month=1, day=1), ZoneInfo("CET")),
            datetime(year=2020, month=1, day=1, hour=1, tzinfo=ZoneInfo("CET")),
            None,
        ),
        (
            "CET",
            (date(year=2020, month=1, day=1), "UTC"),
            date(year=2020, month=1, day=1),
            None,
        ),
    ],
)
def test_make_dtstamp(current_timezone, test_input, expected_output, raises):
    """
    Test make_dtstamp util function.
    """

    with override(current_timezone):
        output = make_dtstamp(*test_input)
        assert output == expected_output


def test_make_dtstamp_invalid_inputs():
    """
    Test make_dtstamp util function invalid inputs.
    """

    with pytest.raises(TypeError):
        output = make_dtstamp("2020-01-01")
    with pytest.raises(TypeError):
        output = make_dtstamp(None)
    with pytest.raises(TypeError):
        output = make_dtstamp(1)


def test_description_maker():
    fields = [
        make_field_renderer(attrgetter("foo"), str),
        make_field_renderer(attrgetter("bar"), str),
        make_field_renderer(attrgetter("foo"), str),
    ]

    row_description = description_maker(fields)

    class R:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    with pytest.raises(AttributeError):
        row_description(R())

    assert row_description(R(foo="abc", bar=None)) == "abc - None - abc"
