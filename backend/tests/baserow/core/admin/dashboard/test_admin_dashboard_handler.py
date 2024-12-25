from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from django.test.utils import override_settings

import pytest

from baserow.core.admin.dashboard.handler import AdminDashboardHandler
from baserow.core.models import UserLogEntry


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_new_user_counts(data_fixture):
    tz = timezone.utc

    data_fixture.create_user(date_joined=datetime(2020, 12, 30, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 1, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 2, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 3, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 4, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 5, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 10, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 23, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 24, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 25, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 26, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 27, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 28, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 29, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 30, 12, 1, tzinfo=tz))
    data_fixture.create_user(date_joined=datetime(2021, 1, 30, 15, 1, tzinfo=tz))

    handler = AdminDashboardHandler()
    now = datetime(2021, 1, 30, 23, 59, tzinfo=tz)

    assert handler.get_new_user_counts(
        {
            "last_24_hours": timedelta(hours=24),
            "last_7_days": timedelta(days=7),
            "last_30_days": timedelta(days=30),
            "last_40_days": timedelta(days=40),
            "last_10_days": timedelta(days=10),
            "last_2_days": timedelta(days=2),
        },
        now=now,
    ) == {
        "last_24_hours": 2,
        "last_7_days": 8,
        "last_30_days": 15,
        "last_40_days": 16,
        "last_10_days": 9,
        "last_2_days": 3,
    }

    assert handler.get_new_user_counts(
        {
            "last_24_hours": timedelta(hours=24),
            "last_7_days": timedelta(days=7),
        },
        now=now,
        include_previous=True,
    ) == {
        "last_24_hours": 2,
        "last_7_days": 8,
        "previous_last_24_hours": 1,
        "previous_last_7_days": 1,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_active_user_counts(data_fixture):
    tz = timezone.utc

    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()

    def create_entries(user, dates):
        for d in dates:
            entry = UserLogEntry()
            entry.actor = user
            entry.action = "SIGNED_IN"
            entry.save()
            # To override the auto_now_add.
            entry.timestamp = d
            entry.save()

    create_entries(
        user_1,
        [
            datetime(2020, 12, 30, tzinfo=tz),
            datetime(2021, 1, 1, tzinfo=tz),
            datetime(2021, 1, 2, tzinfo=tz),
            datetime(2021, 1, 3, tzinfo=tz),
            datetime(2021, 1, 4, tzinfo=tz),
            datetime(2021, 1, 5, tzinfo=tz),
            datetime(2021, 1, 7, tzinfo=tz),
            datetime(2021, 1, 7, tzinfo=tz),
            datetime(2021, 1, 7, tzinfo=tz),
            datetime(2021, 1, 8, tzinfo=tz),
            datetime(2021, 1, 9, tzinfo=tz),
            datetime(2021, 1, 10, tzinfo=tz),
            datetime(2021, 1, 20, tzinfo=tz),
            datetime(2021, 1, 21, tzinfo=tz),
            datetime(2021, 1, 22, tzinfo=tz),
            datetime(2021, 1, 29, tzinfo=tz),
        ],
    )

    create_entries(
        user_2,
        [
            datetime(2020, 12, 20, tzinfo=tz),
            datetime(2021, 1, 1, tzinfo=tz),
            datetime(2021, 1, 2, tzinfo=tz),
            datetime(2021, 1, 3, tzinfo=tz),
            datetime(2021, 1, 4, tzinfo=tz),
            datetime(2021, 1, 10, tzinfo=tz),
            datetime(2021, 1, 11, tzinfo=tz),
            datetime(2021, 1, 12, tzinfo=tz),
            datetime(2021, 1, 13, tzinfo=tz),
            datetime(2021, 1, 14, tzinfo=tz),
            datetime(2021, 1, 15, tzinfo=tz),
            datetime(2021, 1, 16, tzinfo=tz),
            datetime(2021, 1, 20, tzinfo=tz),
            datetime(2021, 1, 21, tzinfo=tz),
            datetime(2021, 1, 24, tzinfo=tz),
        ],
    )

    create_entries(
        user_3,
        [
            datetime(2020, 12, 20, tzinfo=tz),
            datetime(2020, 12, 21, tzinfo=tz),
            datetime(2020, 12, 23, tzinfo=tz),
            datetime(2020, 12, 25, tzinfo=tz),
            datetime(2020, 12, 27, tzinfo=tz),
            datetime(2020, 12, 30, tzinfo=tz),
        ],
    )

    handler = AdminDashboardHandler()
    now = datetime(2021, 1, 30, 23, 59, tzinfo=tz)

    assert handler.get_active_user_count(
        {
            "last_24_hours": timedelta(hours=24),
            "last_7_days": timedelta(days=7),
            "last_30_days": timedelta(days=30),
            "last_40_days": timedelta(days=40),
            "last_10_days": timedelta(days=10),
        },
        now=now,
    ) == {
        "last_24_hours": 0,
        "last_7_days": 2,
        "last_30_days": 2,
        "last_40_days": 3,
        "last_10_days": 2,
    }

    assert handler.get_active_user_count(
        {
            "last_24_hours": timedelta(hours=24),
            "last_7_days": timedelta(days=7),
            "last_30_days": timedelta(days=30),
            "last_40_days": timedelta(days=40),
            "last_10_days": timedelta(days=10),
        },
        now=now,
        include_previous=True,
    ) == {
        "last_24_hours": 0,
        "last_7_days": 2,
        "last_30_days": 2,
        "last_40_days": 3,
        "last_10_days": 2,
        "previous_last_24_hours": 1,
        "previous_last_7_days": 2,
        "previous_last_30_days": 3,
        "previous_last_40_days": 2,
        "previous_last_10_days": 2,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_new_users_per_day(data_fixture):
    utc = timezone.utc
    gmt3 = ZoneInfo("Etc/GMT+3")

    data_fixture.create_user(date_joined=datetime(2020, 12, 29, 12, 1, tzinfo=utc))
    data_fixture.create_user(date_joined=datetime(2021, 1, 1, 1, 1, tzinfo=utc))
    data_fixture.create_user(date_joined=datetime(2021, 1, 1, 12, 1, tzinfo=utc))
    data_fixture.create_user(date_joined=datetime(2021, 1, 2, 12, 1, tzinfo=utc))
    data_fixture.create_user(date_joined=datetime(2021, 1, 2, 12, 1, tzinfo=utc))
    data_fixture.create_user(date_joined=datetime(2021, 1, 2, 12, 1, tzinfo=utc))
    data_fixture.create_user(date_joined=datetime(2021, 1, 30, 12, 1, tzinfo=utc))
    data_fixture.create_user(date_joined=datetime(2021, 1, 30, 15, 1, tzinfo=utc))

    handler = AdminDashboardHandler()

    now = datetime(2021, 1, 30, 23, 59, tzinfo=utc)
    counts = handler.get_new_user_count_per_day(timedelta(days=30), now)
    assert len(counts) == 3
    assert counts[0]["date"] == date(2021, 1, 1)
    assert counts[0]["count"] == 2
    assert counts[1]["date"] == date(2021, 1, 2)
    assert counts[1]["count"] == 3
    assert counts[2]["date"] == date(2021, 1, 30)
    assert counts[2]["count"] == 2

    now = datetime(2021, 1, 1, 13, 00, tzinfo=utc)
    counts = handler.get_new_user_count_per_day(timedelta(days=1), now)
    assert len(counts) == 1
    assert counts[0]["date"] == date(2021, 1, 1)
    assert counts[0]["count"] == 2

    now = datetime(2021, 1, 1, 13, 00, tzinfo=gmt3)
    counts = handler.get_new_user_count_per_day(timedelta(days=1), now)
    assert len(counts) == 2
    assert counts[0]["date"] == date(2020, 12, 31)
    assert counts[0]["count"] == 1
    assert counts[1]["date"] == date(2021, 1, 1)
    assert counts[1]["count"] == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_active_users_per_day(data_fixture):
    utc = timezone.utc
    gmt3 = ZoneInfo("Etc/GMT+3")

    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()

    def create_entries(user, dates):
        for d in dates:
            entry = UserLogEntry()
            entry.actor = user
            entry.action = "SIGNED_IN"
            entry.save()
            # To override the auto_now_add.
            entry.timestamp = d
            entry.save()

    create_entries(
        user_1,
        [
            datetime(2020, 12, 29, tzinfo=utc),
            datetime(2021, 1, 1, 1, 1, tzinfo=utc),
            datetime(2021, 1, 1, 12, 1, tzinfo=utc),
            datetime(2021, 1, 1, 13, 1, tzinfo=utc),
            datetime(2021, 1, 1, 14, 1, tzinfo=utc),
            datetime(2021, 1, 10, 14, 1, tzinfo=utc),
        ],
    )

    create_entries(
        user_2,
        [
            datetime(2020, 12, 29, tzinfo=utc),
            datetime(2021, 1, 1, 1, 1, tzinfo=utc),
            datetime(2021, 1, 10, 12, 1, tzinfo=utc),
            datetime(2021, 1, 10, 13, 1, tzinfo=utc),
        ],
    )

    create_entries(
        user_3,
        [
            datetime(2021, 1, 2, tzinfo=utc),
            datetime(2021, 1, 10, tzinfo=utc),
        ],
    )

    handler = AdminDashboardHandler()

    now = datetime(2021, 1, 30, 23, 59, tzinfo=utc)
    counts = handler.get_active_user_count_per_day(timedelta(days=30), now)
    assert len(counts) == 3
    assert counts[0]["date"] == date(2021, 1, 1)
    assert counts[0]["count"] == 2
    assert counts[1]["date"] == date(2021, 1, 2)
    assert counts[1]["count"] == 1
    assert counts[2]["date"] == date(2021, 1, 10)
    assert counts[2]["count"] == 3

    now = datetime(2021, 1, 1, 13, 00, tzinfo=utc)
    counts = handler.get_active_user_count_per_day(timedelta(days=1), now)
    assert len(counts) == 1
    assert counts[0]["date"] == date(2021, 1, 1)
    assert counts[0]["count"] == 2

    now = datetime(2021, 1, 1, 13, 00, tzinfo=gmt3)
    counts = handler.get_active_user_count_per_day(timedelta(days=1), now)
    assert len(counts) == 2
    assert counts[0]["date"] == date(2020, 12, 31)
    assert counts[0]["count"] == 2
    assert counts[1]["date"] == date(2021, 1, 1)
    assert counts[1]["count"] == 1
