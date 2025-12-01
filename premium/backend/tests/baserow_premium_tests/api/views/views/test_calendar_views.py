import json
import typing
from datetime import date, datetime, timedelta, timezone
from functools import partial
from unittest import mock
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from baserow_premium.views.models import CalendarView, CalendarViewFieldOptions
from freezegun import freeze_time
from icalendar import Calendar
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.fields.field_types import TextFieldType
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.test_utils.helpers import (
    AnyInt,
    AnyStr,
    is_dict_subset,
    setup_interesting_test_table,
)


def get_list_url(calendar_view_id: int) -> str:
    queryparams_ts_jan2023 = (
        f"from_timestamp={str(datetime(2023, 1, 1))}"
        f"&to_timestamp={str(datetime(2023, 2, 1))}"
    )
    return (
        reverse(
            "api:database:views:calendar:list", kwargs={"view_id": calendar_view_id}
        )
        + f"?{queryparams_ts_jan2023}"
    )


def get_public_list_url(calendar_view_slug: str) -> str:
    queryparams_ts_jan2023 = (
        f"from_timestamp={str(datetime(2023, 1, 1))}"
        f"&to_timestamp={str(datetime(2023, 2, 1))}"
    )
    return (
        reverse(
            "api:database:views:calendar:public_rows",
            kwargs={"slug": calendar_view_slug},
        )
        + f"?{queryparams_ts_jan2023}"
    )


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_without_valid_premium_license(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=False
    )
    calendar = premium_data_fixture.create_calendar_view(user=user)
    url = get_list_url(calendar.id)

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"

    # The calendar view should work if it's a template.

    premium_data_fixture.create_template(workspace=calendar.table.database.workspace)

    calendar.table.database.workspace.has_template.cache_clear()

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_without_valid_premium_license_for_workspace(
    api_client, premium_data_fixture, alternative_per_workspace_license_service
):
    # without a license

    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    calendar = premium_data_fixture.create_calendar_view(user=user)
    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    url = get_list_url(calendar.id)

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"

    # with a valid license

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [calendar.table.database.workspace.id]
    )
    premium_data_fixture.create_template(workspace=calendar.table.database.workspace)

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_200_OK


# authorization


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_rows_user_not_in_workspace(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    calendar = premium_data_fixture.create_calendar_view()
    url = get_list_url(calendar.id)

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


# invalid view


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_rows_invalid_view(api_client, premium_data_fixture):
    # view doesn't exist

    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    calendar = premium_data_fixture.create_calendar_view(user=user, date_field=None)
    url = get_list_url(0)

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # missing date field

    url = get_list_url(calendar.id)

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD"


# field options


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_rows_include_field_options(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, primary=True)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    date_field = premium_data_fixture.create_date_field(table=table)
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )
    url = get_list_url(calendar.id)

    response = api_client.get(
        f"{url}&include=field_options", **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 3
    assert response_json["field_options"][str(date_field.id)]["hidden"] is True
    assert response_json["field_options"][str(date_field.id)]["order"] == 32767
    assert response_json["field_options"][str(text_field.id)]["hidden"] is True
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    assert response_json["field_options"][str(single_select_field.id)]["hidden"] is True
    assert response_json["field_options"][str(single_select_field.id)]["order"] == 32767


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_patch_calendar_view_field_options(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table)
    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)
    url = reverse("api:database:views:field_options", kwargs={"view_id": calendar.id})

    response = api_client.patch(
        url,
        {"field_options": {text_field.id: {"width": 300, "hidden": False}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 1
    assert response_json["field_options"][str(text_field.id)]["hidden"] is False
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    options = calendar.get_field_options()
    assert len(options) == 1
    assert options[0].field_id == text_field.id
    assert options[0].hidden is False
    assert options[0].order == 32767


# listing rows


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_all_rows(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )
    datetime_from = datetime(2023, 1, 1)
    datetime_to = datetime(2023, 2, 1)
    queryparams_timestamps = (
        f"?from_timestamp={str(datetime_from)}" f"&to_timestamp={str(datetime_to)}"
    )
    datetimes = [
        datetime(2022, 12, 31),  # not in range
        datetime(2023, 1, 1),
        datetime(2023, 1, 10),
        datetime(2023, 1, 31),
        datetime(2023, 1, 31, 23, 59, 59, 999999),
        datetime(2023, 2, 1),  # not in range,
        None,  # not in range
    ]
    model = table.get_model()

    for dt in datetimes:
        model.objects.create(
            **{
                f"field_{date_field.id}": (
                    dt.replace(tzinfo=timezone.utc) if dt is not None else None
                ),
            }
        )

    url = (
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + queryparams_timestamps
    )
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 31

    assert response_json["rows"].get("2022-12-31", None) is None

    assert response_json["rows"]["2023-01-01"]["count"] == 1
    assert len(response_json["rows"]["2023-01-01"]["results"]) == 1
    assert is_dict_subset(
        {
            f"field_{date_field.id}": "2023-01-01T00:00:00Z",
        },
        response_json["rows"]["2023-01-01"]["results"][0],
    )

    assert response_json["rows"]["2023-01-10"]["count"] == 1
    assert len(response_json["rows"]["2023-01-10"]["results"]) == 1
    assert is_dict_subset(
        {
            f"field_{date_field.id}": "2023-01-10T00:00:00Z",
        },
        response_json["rows"]["2023-01-10"]["results"][0],
    )

    assert response_json["rows"]["2023-01-31"]["count"] == 2
    assert len(response_json["rows"]["2023-01-31"]["results"]) == 2
    assert is_dict_subset(
        {
            f"field_{date_field.id}": "2023-01-31T00:00:00Z",
        },
        response_json["rows"]["2023-01-31"]["results"][0],
    )
    assert is_dict_subset(
        {
            f"field_{date_field.id}": "2023-01-31T23:59:59.999999Z",
        },
        response_json["rows"]["2023-01-31"]["results"][1],
    )

    assert response_json["rows"].get("2023-02-01", None) is None


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_all_rows_limit_offset(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )
    datetime_from = datetime(2023, 1, 1)
    datetime_to = datetime(2023, 2, 1)
    queryparams_timestamps = (
        f"?from_timestamp={str(datetime_from)}" f"&to_timestamp={str(datetime_to)}"
    )
    queryparams_limit_offset = f"&limit=3&offset=2"
    datetimes = [
        datetime(2022, 12, 31),  # not in range
        datetime(2023, 1, 1),
        datetime(2023, 1, 10),
        datetime(2023, 1, 31),
        datetime(2023, 2, 1),  # not in range,
    ]
    model = table.get_model()

    for dt in datetimes:
        for i in range(5):
            model.objects.create(
                **{
                    f"field_{date_field.id}": dt.replace(hour=i, tzinfo=timezone.utc),
                }
            )

    url = (
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + queryparams_timestamps
        + queryparams_limit_offset
    )
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 31

    assert response_json["rows"].get("2022-12-31", None) is None

    assert response_json["rows"]["2023-01-01"]["count"] == 5
    assert len(response_json["rows"]["2023-01-01"]["results"]) == 3
    assert is_dict_subset(
        {
            f"field_{date_field.id}": "2023-01-01T02:00:00Z",
        },
        response_json["rows"]["2023-01-01"]["results"][0],
    )

    assert response_json["rows"]["2023-01-10"]["count"] == 5
    assert len(response_json["rows"]["2023-01-10"]["results"]) == 3
    assert is_dict_subset(
        {
            f"field_{date_field.id}": "2023-01-10T02:00:00Z",
        },
        response_json["rows"]["2023-01-10"]["results"][0],
    )

    assert response_json["rows"]["2023-01-31"]["count"] == 5
    assert len(response_json["rows"]["2023-01-31"]["results"]) == 3
    assert is_dict_subset(
        {
            f"field_{date_field.id}": "2023-01-31T02:00:00Z",
        },
        response_json["rows"]["2023-01-31"]["results"][0],
    )

    assert response_json["rows"].get("2023-02-01", None) is None


@pytest.mark.parametrize(
    "from_timestamp,to_timestamp,error_field",
    [
        ("", "2023-01-10 03:00:00", "from_timestamp"),
        ("abc", "2023-01-10 03:00:00", "from_timestamp"),
        ("2023-01-10 03:00:00", "", "to_timestamp"),
        ("2023-01-10 03:00:00", "abc", "to_timestamp"),
    ],
)
@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_all_rows_invalid_from_to_timestamp(
    from_timestamp, to_timestamp, error_field, api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )
    queryparams_timestamps = (
        f"?from_timestamp={from_timestamp}" f"&to_timestamp={to_timestamp}"
    )

    url = (
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + queryparams_timestamps
    )
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["detail"][error_field][0]["code"] == "invalid"


@pytest.mark.parametrize(
    "limit,offset,error_field",
    [
        ("abc", "5", "limit"),
        ("", "5", "limit"),
        ("5", "", "offset"),
        ("5", "abc", "offset"),
    ],
)
@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_all_rows_invalid_limit_offset(
    limit, offset, error_field, api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    queryparams = f"?limit={limit}" f"&offset={offset}"

    url = (
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + queryparams
    )
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["detail"][error_field][0]["code"] == "invalid"


# creating and updating calendar view


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_create_calendar_view(api_client, premium_data_fixture):
    # date field doesn't belong to the table

    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field()

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "calendar",
            "filter_type": "OR",
            "filters_disabled": True,
            "date_field": date_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_NOT_IN_TABLE"

    # date field is null

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "calendar",
            "filter_type": "OR",
            "filters_disabled": True,
            "date_field": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 1"
    assert response_json["type"] == "calendar"
    assert response_json["filter_type"] == "OR"
    assert response_json["filters_disabled"] is True
    assert response_json["date_field"] is None

    calendar_view = CalendarView.objects.all().last()
    assert calendar_view.id == response_json["id"]
    assert calendar_view.date_field_id is None

    # date field is set

    date_field = premium_data_fixture.create_date_field(table=table)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "calendar",
            "filter_type": "AND",
            "filters_disabled": False,
            "date_field": date_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 2"
    assert response_json["type"] == "calendar"
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is False
    assert response_json["date_field"] == date_field.id

    calendar_view = CalendarView.objects.all().last()
    assert calendar_view.id == response_json["id"]
    assert calendar_view.date_field_id == date_field.id


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_create_calendar_view_different_field_types(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table, _, _, _, context = setup_interesting_test_table(
        premium_data_fixture, user=user
    )
    kwargs = {
        "table": table,
        "name": premium_data_fixture.fake.name(),
        "order": 1,
    }

    specific_fields = [f.specific for f in table.field_set.all()]
    can_represent_date_fields = [
        f
        for f in specific_fields
        if field_type_registry.get_by_model(f).can_represent_date(f)
    ]

    for field in can_represent_date_fields:
        response = api_client.post(
            reverse("api:database:views:list", kwargs={"table_id": table.id}),
            {
                "name": "Test",
                "type": "calendar",
                "date_field": field.id,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    not_compatible_field_type = field_type_registry.get(TextFieldType.type)
    field = not_compatible_field_type.model_class.objects.create(**kwargs)
    premium_data_fixture.create_model_field(kwargs["table"], field)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "calendar",
            "date_field": field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_update_calendar_view(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, date_field=None
    )
    date_field = premium_data_fixture.create_date_field(table=table)
    date_field_not_in_table = premium_data_fixture.create_date_field()

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {
            "date_field": date_field_not_in_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_NOT_IN_TABLE"

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {
            "date_field": date_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["date_field"] == date_field.id

    calendar_view.refresh_from_db()
    assert calendar_view.date_field_id == date_field.id

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {
            "date_field": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["date_field"] is None

    calendar_view.refresh_from_db()
    assert calendar_view.date_field is None


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_all_rows_with_field_timezone_set_uses_field_timezone(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True, date_force_timezone="Australia/Melbourne"
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    melbourne_tz = ZoneInfo("Australia/Melbourne")
    datetime_from = datetime(2023, 1, 1, tzinfo=melbourne_tz)
    datetime_to = datetime(2023, 1, 2, tzinfo=melbourne_tz)
    queryparams_timestamps = {
        "from_timestamp": datetime_from.isoformat(),
        "to_timestamp": datetime_to.isoformat(),
    }
    outside_to_from_period = datetime_from - timedelta(hours=1)
    inside_to_from_period = datetime_from + timedelta(hours=1)
    model = table.get_model()

    row1 = model.objects.create(
        **{f"field_{date_field.id}": inside_to_from_period.astimezone(tz=timezone.utc)}
    )
    row2 = model.objects.create(
        **{f"field_{date_field.id}": outside_to_from_period.astimezone(tz=timezone.utc)}
    )

    url = (
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + "?"
        + urlencode(queryparams_timestamps)
    )
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    assert response_json["rows"] == {
        "2023-01-01": {
            "count": 1,
            "results": [
                {
                    f"field_{date_field.id}": "2022-12-31T14:00:00Z",
                    "id": row1.id,
                    "order": "1.00000000000000000000",
                }
            ],
        }
    }


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_all_rows_with_user_timezone_set_uses_user_timezone_when_no_field_tz(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    tz_name = "Australia/Melbourne"
    melbourne_tz = ZoneInfo(tz_name)
    datetime_from = datetime(2023, 1, 1, tzinfo=melbourne_tz)
    datetime_to = datetime(2023, 1, 2, tzinfo=melbourne_tz)
    queryparams_timestamps = {
        "from_timestamp": datetime_from.isoformat(),
        "to_timestamp": datetime_to.isoformat(),
        "user_timezone": tz_name,
    }
    outside_to_from_period = datetime_from - timedelta(hours=1)
    inside_to_from_period = datetime_from + timedelta(hours=1)
    model = table.get_model()

    row1 = model.objects.create(
        **{f"field_{date_field.id}": inside_to_from_period.astimezone(tz=timezone.utc)}
    )
    row2 = model.objects.create(
        **{f"field_{date_field.id}": outside_to_from_period.astimezone(tz=timezone.utc)}
    )

    url = (
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + "?"
        + urlencode(queryparams_timestamps)
    )
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    assert response_json["rows"] == {
        "2023-01-01": {
            "count": 1,
            "results": [
                {
                    f"field_{date_field.id}": "2022-12-31T14:00:00Z",
                    "id": row1.id,
                    "order": "1.00000000000000000000",
                }
            ],
        }
    }


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_invalid_user_timezone_returns_error(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=True,
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    response = api_client.get(
        get_list_url(calendar.id) + "&user_timezone=NONSENSE",
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json == {
        "detail": {
            "user_timezone": [
                {
                    "code": "invalid_choice",
                    "error": '"NONSENSE" is not a valid choice.',
                }
            ]
        },
        "error": "ERROR_QUERY_PARAMETER_VALIDATION",
    }


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_too_wide_timerange_returns_error(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=True,
    )
    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )
    datetime_from = datetime(2023, 1, 1)
    datetime_to = datetime_from + timedelta(days=settings.MAX_NUMBER_CALENDAR_DAYS + 1)
    queryparams_timestamps = {
        "from_timestamp": datetime_from.isoformat(),
        "to_timestamp": datetime_to.isoformat(),
    }

    response = api_client.get(
        reverse("api:database:views:calendar:list", kwargs={"view_id": calendar.id})
        + "?"
        + urlencode(queryparams_timestamps),
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json == {
        "detail": {
            "non_field_errors": [
                {
                    "code": "invalid",
                    "error": "the number of days between "
                    "from_timestamp and to_timestamp "
                    f"must be less than {settings.MAX_NUMBER_CALENDAR_DAYS} days",
                }
            ]
        },
        "error": "ERROR_QUERY_PARAMETER_VALIDATION",
    }


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_can_duplicate_calendar_view_with_date_field(
    api_client, data_fixture, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field = data_fixture.create_date_field(table=table)
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    assert View.objects.count() == 1

    response = api_client.post(
        reverse("api:database:views:duplicate", kwargs={"view_id": calendar_view.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] != calendar_view.id
    assert response_json["name"] == f"{calendar_view.name} 2"
    assert response_json["date_field"] == date_field.id
    assert View.objects.count() == 2


@pytest.mark.django_db
def test_get_public_calendar_view_with_single_select_and_cover(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(table=table, order=0)
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, user=user, public=True, date_field=date_field
    )
    date_field = calendar_view.date_field
    public_field = premium_data_fixture.create_text_field(
        table=table, name="public", order=1
    )
    hidden_field = premium_data_fixture.create_text_field(
        table=table, name="hidden", order=2
    )

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view, date_field, hidden=False, order=0
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view, public_field, hidden=False, order=1
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view, hidden_field, hidden=True, order=2
    )

    # Can access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": calendar_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert calendar_view.ical_public is False
    assert calendar_view.ical_slug is None
    assert calendar_view.ical_feed_url is None

    assert response_json == {
        "fields": [
            {
                "id": date_field.id,
                "name": date_field.name,
                "order": 0,
                "primary": date_field.primary,
                "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "type": "date",
                "read_only": False,
                "date_force_timezone": None,
                "date_format": "EU",
                "date_include_time": False,
                "date_show_tzinfo": False,
                "date_time_format": "24",
                "description": None,
                "immutable_properties": False,
                "immutable_type": False,
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "db_index": False,
                "field_constraints": [],
            },
            {
                "id": public_field.id,
                "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "name": "public",
                "order": 1,
                "primary": False,
                "text_default": "",
                "type": "text",
                "read_only": False,
                "description": None,
                "immutable_properties": False,
                "immutable_type": False,
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "db_index": False,
                "field_constraints": [],
            },
        ],
        "view": {
            "id": calendar_view.slug,
            "name": calendar_view.name,
            "order": 0,
            "public": True,
            "slug": calendar_view.slug,
            "sortings": [],
            "group_bys": [],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "type": "calendar",
            "date_field": date_field.id,
            "show_logo": True,
            "allow_public_export": False,
            "ical_public": False,
            "ical_feed_url": calendar_view.ical_feed_url,
        },
    }


@pytest.mark.django_db
def test_list_public_rows_without_date_field(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, user=user, public=True, date_field=None
    )

    # Get access as an anonymous user
    response = api_client.get(
        get_public_list_url(calendar_view.slug),
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD"


@pytest.mark.django_db
def test_list_public_rows_without_password(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    calendar_view = premium_data_fixture.create_calendar_view(
        table=table,
        user=user,
        public=True,
    )
    calendar_view.set_password("test")
    calendar_view.save()

    response = api_client.get(
        get_public_list_url(calendar_view.slug),
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_public_rows_with_valid_password(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    calendar_view = premium_data_fixture.create_calendar_view(
        table=table,
        user=user,
        public=True,
    )
    calendar_view.set_password("test")
    calendar_view.save()

    token = ViewHandler().encode_public_view_token(calendar_view)
    response = api_client.get(
        get_public_list_url(calendar_view.slug),
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_list_public_rows_password_protected_with_jwt_auth(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    calendar_view = premium_data_fixture.create_calendar_view(
        table=table,
        user=user,
        public=True,
    )
    calendar_view.set_password("test")
    calendar_view.save()

    response = api_client.get(
        get_public_list_url(calendar_view.slug),
        HTTP_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_list_public_rows_doesnt_show_hidden_columns(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    date_field = premium_data_fixture.create_date_field(table=table, name="date")
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, user=user, public=True, date_field=date_field
    )

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")

    date_field_options = CalendarViewFieldOptions.objects.get(
        field_id=calendar_view.date_field_id
    )
    public_field_option = premium_data_fixture.create_calendar_view_field_option(
        calendar_view, public_field, hidden=False
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view, hidden_field, hidden=True
    )

    with freeze_time("2023-01-10 12:00"):
        row = RowHandler().create_row(
            user, table, values={f"field_{date_field.id}": "2023-01-10 12:00"}
        )

        # Get access as an anonymous user
        response = api_client.get(
            get_public_list_url(calendar_view.slug) + "&include=field_options"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert response_json["field_options"] == {
            f"{public_field.id}": {
                "hidden": False,
                "order": public_field_option.order,
            },
            f"{calendar_view.date_field_id}": {
                "hidden": True,
                "order": date_field_options.order,
            },
        }
        day_with_row = response_json["rows"].pop("2023-01-10")
        assert day_with_row["count"] == 1
        assert day_with_row["results"] == [
            {
                f"field_{date_field.id}": "2023-01-10",
                f"field_{public_field.id}": None,
                "id": row.id,
                "order": str(row.order),
            }
        ]
        for other_day in response_json["rows"].values():
            assert other_day["count"] == 0


@pytest.mark.django_db
def test_list_public_rows_limit_offset(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    date_field = premium_data_fixture.create_date_field(
        table=table, name="date", date_include_time=True
    )
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table,
        user=user,
        public=True,
        date_field=date_field,
    )

    with freeze_time("2023-01-10 12:00"):
        for day in range(10):
            for hour in range(10):
                row = RowHandler().create_row(
                    user,
                    table,
                    values={f"field_{date_field.id}": f"2023-01-{day+10} {hour+10}:00"},
                )

        response = api_client.get(
            get_public_list_url(calendar_view.slug) + f"&limit=3&offset=5"
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        day_with_row = response_json["rows"].pop("2023-01-10")
        assert day_with_row["count"] == 10
        assert len(day_with_row["results"]) == 3
        assert [d[f"field_{date_field.id}"] for d in day_with_row["results"]] == [
            "2023-01-10T15:00:00Z",
            "2023-01-10T16:00:00Z",
            "2023-01-10T17:00:00Z",
        ]


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_search_calendar_rows(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)

    date_field = premium_data_fixture.create_date_field(table=table, name="date")
    description_field = premium_data_fixture.create_text_field(
        table=table, name="description"
    )

    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    rows_data = [
        ["2023-01-01", "Meeting with team"],
        ["2023-01-02", "Lunch with client"],
        ["2023-01-02", "Meeting with client"],
        ["2023-01-02", "Meeting with employees"],
        ["2023-01-12", "Team building activity"],
    ]
    premium_data_fixture.create_rows_in_table(
        table=table, rows=rows_data, fields=[date_field, description_field]
    )

    url = get_list_url(calendar.id) + "&search=client"
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    expected_data = {
        "2023-01-02": {
            "count": 2,
            "results": [
                {
                    "id": AnyInt(),
                    "order": AnyStr(),
                    description_field.db_column: "Lunch with client",
                    date_field.db_column: "2023-01-02",
                },
                {
                    "id": AnyInt(),
                    "order": AnyStr(),
                    description_field.db_column: "Meeting with client",
                    date_field.db_column: "2023-01-02",
                },
            ],
        }
    }

    results_for_searched_day = response_json["rows"].get("2023-01-02", {})
    assert results_for_searched_day == expected_data["2023-01-02"]


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_search_calendar_with_empty_term(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)

    date_field = premium_data_fixture.create_date_field(table=table, name="date")
    description_field = premium_data_fixture.create_text_field(
        table=table, name="description"
    )

    calendar = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    rows_data = [
        ["2023-01-01", "Meeting with team"],
        ["2023-01-02", "Lunch with client"],
        ["2023-01-02", "Meeting with client"],
        ["2023-01-02", "Meeting with employees"],
        ["2023-01-12", "Team building activity"],
    ]
    premium_data_fixture.create_rows_in_table(
        table=table, rows=rows_data, fields=[date_field, description_field]
    )

    url = get_list_url(calendar.id) + "&search="
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK

    total_results = sum(
        [date_data["count"] for date_data in response.json()["rows"].values()]
    )

    assert total_results == 5


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_feed_sharing(
    premium_data_fixture, api_client, data_fixture
):
    """
    Test ical feed sharing
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    regular_user = data_fixture.create_user()
    regular_token = data_fixture.generate_token(user=regular_user)
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(table=table)

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )

    assert not calendar_view.ical_public
    assert not calendar_view.ical_feed_url
    req_post = partial(
        api_client.post, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    # step 1: make ical feed public
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )

    assert resp.status_code == HTTP_200_OK

    calendar_view.refresh_from_db()
    assert calendar_view.ical_public
    assert calendar_view.ical_feed_url
    assert calendar_view.ical_slug
    assert resp.data.get("ical_feed_url") == calendar_view.ical_feed_url
    assert resp.data.get("ical_public")

    # step 2: disable the view
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": False},
    )

    assert resp.status_code == HTTP_200_OK

    calendar_view.refresh_from_db()
    # slug stays the same
    assert calendar_view.ical_slug
    assert calendar_view.ical_feed_url
    assert calendar_view.ical_public is False
    assert resp.data.get("ical_feed_url") == calendar_view.ical_feed_url
    assert resp.data.get("ical_public") is False

    # step 3: reenable ical feed
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )

    assert resp.status_code == HTTP_200_OK

    calendar_view.refresh_from_db()
    assert calendar_view.ical_public
    assert calendar_view.ical_feed_url
    feed_url = calendar_view.ical_feed_url

    # step 4: rotate ical slug
    resp: Response = req_post(
        reverse(
            "api:database:views:calendar:ical_slug_rotate",
            kwargs={"view_id": calendar_view.id},
        ),
        {},
    )

    calendar_view.refresh_from_db()
    assert calendar_view.ical_public
    assert calendar_view.ical_feed_url
    assert calendar_view.ical_feed_url != feed_url
    feed_url = calendar_view.ical_feed_url
    assert resp.data.get("ical_feed_url") == calendar_view.ical_feed_url


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_feed_contents(
    premium_data_fixture, api_client, data_fixture
):
    """
    Basic ical feed functionality test
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_text_field(table=table, user=user)
    field_extra = data_fixture.create_text_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)

    date_field = premium_data_fixture.create_date_field(table=table)

    all_fields = [field_title, field_description, field_extra, field_num, date_field]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()
    NUM_EVENTS = 20

    def make_values(num):
        curr = 0
        field_names = [f"field_{f.id}" for f in all_fields]
        start = datetime.now()
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
    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    # make ical feed public
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )

    assert resp.status_code == HTTP_200_OK

    calendar_view.refresh_from_db()
    assert calendar_view.ical_public
    assert calendar_view.ical_feed_url
    assert calendar_view.ical_slug
    assert resp.data.get("ical_feed_url") == calendar_view.ical_feed_url

    visible_a = {f.id: {"hidden": True} for f in all_fields}
    visible_a.update(
        {
            field_num.id: {"hidden": False, "order": 1},
            field_extra.id: {"hidden": False, "order": 2},
        }
    )
    resp = req_patch(
        reverse(
            "api:database:views:field_options", kwargs={"view_id": calendar_view.id}
        ),
        {"field_options": visible_a},
    )
    assert resp.status_code == HTTP_200_OK, resp.content

    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )
    assert resp.status_code == HTTP_200_OK
    assert resp.headers.get("content-type") == "text/calendar", resp.headers
    assert resp.content
    # parse generated feed
    feed = Calendar.from_ical(resp.content)
    assert feed
    assert feed.get("PRODID") == "Baserow / baserow.io"
    evsummary = [ev.get("description") for ev in feed.walk("VEVENT")]
    assert len(evsummary) == NUM_EVENTS
    assert evsummary[0] == "0 - extra 0"
    assert evsummary[1] == "1 - extra 1"

    visible_a.update(
        {
            field_num.id: {"hidden": False, "order": 2},
            field_extra.id: {"hidden": False, "order": 1},
        }
    )
    resp = req_patch(
        reverse(
            "api:database:views:field_options", kwargs={"view_id": calendar_view.id}
        ),
        {"field_options": visible_a},
    )
    assert resp.status_code == HTTP_200_OK, resp.content

    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.headers.get("content-type") == "text/calendar", resp.headers
    assert resp.content
    # parse generated feed
    feed = Calendar.from_ical(resp.content)
    assert feed
    assert feed.get("PRODID") == "Baserow / baserow.io"
    evsummary = [ev.get("description") for ev in feed.walk("VEVENT")]
    assert len(evsummary) == NUM_EVENTS
    assert evsummary[1] == "extra 1 - 1"

    with override_settings(BASEROW_ICAL_VIEW_MAX_EVENTS=5):
        resp = req_get(
            reverse(
                "api:database:views:calendar:calendar_ical_feed",
                kwargs={"ical_slug": calendar_view.ical_slug},
            )
        )
        assert resp.status_code == HTTP_200_OK
        assert resp.headers.get("content-type") == "text/calendar", resp.headers
        assert resp.content
        # parse generated feed
        feed = Calendar.from_ical(resp.content)
        assert feed
        assert feed.get("PRODID") == "Baserow / baserow.io"
        evsummary = [ev.get("description") for ev in feed.walk("VEVENT")]
        assert len(evsummary) == 5


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_feed_invalid_references(
    premium_data_fixture, api_client, data_fixture
):
    """
    Test if calendar is not accessible using invalid reference values
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    regular_user = data_fixture.create_user()
    regular_token = data_fixture.generate_token(regular_user)
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(table=table)

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
        ical_public=False,
        ical_slug=View.create_new_slug(),
    )

    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    req_post = partial(
        api_client.post, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )
    assert resp.status_code == HTTP_404_NOT_FOUND

    # make ical feed public
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.data["ical_feed_url"]
    assert resp.data["ical_public"]
    calendar_view.refresh_from_db()
    assert calendar_view.ical_public
    assert calendar_view.ical_feed_url
    assert calendar_view.ical_slug
    assert resp.data.get("ical_feed_url") == calendar_view.ical_feed_url
    feed_url = calendar_view.ical_feed_url

    # check feed url availability
    resp = req_get(feed_url)
    assert resp.status_code == HTTP_200_OK
    assert resp.headers["Content-Type"] == "text/calendar"

    # few possible invalid urls
    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": "phony"},
        )
    )
    assert resp.status_code == HTTP_404_NOT_FOUND
    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.id},
        )
    )
    assert resp.status_code == HTTP_404_NOT_FOUND
    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.slug},
        )
    )
    assert resp.status_code == HTTP_404_NOT_FOUND

    # rather won't happen, but a view can be non-shareable
    with mock.patch(
        "baserow_premium.views.view_types.CalendarViewType.can_share", False
    ):
        resp: Response = req_post(
            reverse(
                "api:database:views:calendar:ical_slug_rotate",
                kwargs={"view_id": calendar_view.id},
            ),
            {},
        )
        assert resp.status_code == HTTP_400_BAD_REQUEST
        assert resp.data["error"] == "ERROR_CANNOT_SHARE_VIEW_TYPE"

    # sanity check - the view should remain
    calendar_view.refresh_from_db()
    assert calendar_view.ical_public
    assert calendar_view.ical_feed_url
    assert calendar_view.ical_feed_url == feed_url

    # invalid user check
    resp: Response = req_post(
        reverse(
            "api:database:views:calendar:ical_slug_rotate",
            kwargs={"view_id": calendar_view.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {regular_token}",
    )

    assert resp.status_code == HTTP_400_BAD_REQUEST
    assert resp.data["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_no_date_field(
    premium_data_fixture, api_client, data_fixture
):
    """
    Test if calendar is not accessible using invalid reference values
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    regular_user = data_fixture.create_user()
    regular_token = data_fixture.generate_token(regular_user)
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(table=table)

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        ical_public=False,
        ical_slug=View.create_new_slug(),
    )
    assert not calendar_view.date_field

    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )
    assert resp.status_code == HTTP_404_NOT_FOUND

    # make ical feed public
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.data["ical_feed_url"]
    assert resp.data["ical_public"]
    calendar_view.refresh_from_db()
    assert calendar_view.ical_public
    assert calendar_view.ical_feed_url
    assert calendar_view.ical_slug
    assert resp.data.get("ical_feed_url") == calendar_view.ical_feed_url
    feed_url = calendar_view.ical_feed_url

    # check feed url availability
    resp = req_get(feed_url)
    assert resp.status_code == HTTP_400_BAD_REQUEST

    assert resp.data["error"] == "ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD"


def do_calendar_view_request(
    requester: typing.Callable,
    url_name: str,
    params: dict,
    view_id: str | int,
    expected_status: int,
    expected_payload: list[dict] | dict,
) -> dict:
    """
    Performs a request to a view with a specific url name. Checks for expected status
     and payload.

    If the status is HTTP_200_OK then the payload is a list of items from per-day items.

    If the status is not HTTP_200_OK, the `expected_payload` means the whole
     response payload.

    :param requester: requester callable
    :param url_name: full url name
    :param params: query params
    :param view_id: view identificator (id or slug)
    :param expected_status:
    :param expected_payload:
    :return:
    """

    resp = requester(reverse(url_name, args=(view_id,)), params)
    assert resp.status_code == expected_status, (
        resp.status_code,
        resp.json(),
    )
    rdata = resp.json()
    if expected_status == HTTP_200_OK:
        assert isinstance(rdata, dict)
        assert isinstance(rdata.get("rows"), dict)
        actual_events = []
        total_count = 0
        expected_count = len(expected_payload)
        for r_date, r_data in rdata["rows"].items():
            total_count += r_data["count"]
            actual_events.extend(r_data["results"])
        assert len(actual_events) == total_count, actual_events
        assert total_count == expected_count
        for expected_item, actual_item in zip(expected_payload, actual_events):
            assert is_dict_subset(expected_item, actual_item), (
                expected_item,
                actual_item,
            )
    else:
        assert rdata == expected_payload, rdata
    return rdata


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_persistent_filters(
    premium_data_fixture,
    api_client,
    data_fixture,
    alternative_per_workspace_license_service,
):
    """
    Test calendar view with persistent filters
    """

    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(name="Workspace 1", user=user)
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(user=user, database=database)

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [workspace.id]
    )
    field_title = data_fixture.create_text_field(table=table, user=user, name="title")
    field_description = data_fixture.create_text_field(
        table=table, user=user, name="description"
    )
    field_extra = data_fixture.create_text_field(table=table, user=user, name="extra")
    field_num = data_fixture.create_number_field(table=table, user=user, name="num")
    field_bool = data_fixture.create_boolean_field(table=table, user=user, name="bool")
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )
    all_fields = [
        field_title,
        field_description,
        field_extra,
        field_num,
        date_field,
        field_bool,
    ]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    NUM_EVENTS = 10

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
                start + timedelta(days=1 + curr),
                bool(curr % 2),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            RowHandler().create_row(user, table, values=row)

    make_values(NUM_EVENTS)

    vf_bool = view_handler.create_filter(
        user=user, view=calendar_view, field=field_bool, type_name="boolean", value="1"
    )

    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    params = {
        "from_timestamp": f"{start.isoformat()}",
        "to_timestamp": f"{(start + timedelta(days=2+NUM_EVENTS)).isoformat()}",
    }
    field_title_name = f"field_{field_title.id}"

    expected_payload = [
        {field_title_name: "title 1"},
        {field_title_name: "title 3"},
        {field_title_name: "title 5"},
        {field_title_name: "title 7"},
        {field_title_name: "title 9"},
    ]
    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:list",
        params,
        calendar_view.id,
        HTTP_200_OK,
        expected_payload,
    )

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:public_rows",
        params,
        calendar_view.slug,
        HTTP_200_OK,
        expected_payload,
    )

    vf_title = view_handler.create_filter(
        user=user,
        view=calendar_view,
        field=field_title,
        type_name="contains",
        value="title 3",
    )

    expected_payload = [
        {field_title_name: "title 3"},
    ]
    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:list",
        params,
        calendar_view.id,
        HTTP_200_OK,
        expected_payload,
    )

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:public_rows",
        params,
        calendar_view.slug,
        HTTP_200_OK,
        expected_payload,
    )

    vf_title.delete()
    vf_bool.delete()

    expected_payload = [
        {field_title_name: "title 0"},
        {field_title_name: "title 1"},
        {field_title_name: "title 2"},
        {field_title_name: "title 3"},
        {field_title_name: "title 4"},
        {field_title_name: "title 5"},
        {field_title_name: "title 6"},
        {field_title_name: "title 7"},
        {field_title_name: "title 8"},
        {field_title_name: "title 9"},
    ]
    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:list",
        params,
        calendar_view.id,
        HTTP_200_OK,
        expected_payload,
    )

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:public_rows",
        params,
        calendar_view.slug,
        HTTP_200_OK,
        expected_payload,
    )


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_adhoc_filters_invalid(
    premium_data_fixture,
    api_client,
    data_fixture,
    alternative_per_workspace_license_service,
):
    """
    Test calendar view with invalid filters
    """

    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(name="Workspace 1", user=user)
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(user=user, database=database)

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [workspace.id]
    )
    field_title = data_fixture.create_text_field(table=table, user=user, name="title")
    field_description = data_fixture.create_text_field(
        table=table, user=user, name="description"
    )
    field_extra = data_fixture.create_text_field(table=table, user=user, name="extra")
    field_num = data_fixture.create_number_field(table=table, user=user, name="num")
    field_bool = data_fixture.create_boolean_field(table=table, user=user, name="bool")
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )
    all_fields = [
        field_title,
        field_description,
        field_extra,
        field_num,
        date_field,
        field_bool,
    ]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    NUM_EVENTS = 10

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
                start + timedelta(days=1 + curr),
                bool(curr % 2),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            RowHandler().create_row(user, table, values=row)

    make_values(NUM_EVENTS)

    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    params = {
        "from_timestamp": f"{start.isoformat()}",
        "to_timestamp": f"{(start + timedelta(days=2+NUM_EVENTS)).isoformat()}",
    }

    params_filter_invalid = {
        **params,
        **{"filters": json.dumps({"filter_type": "invalid", "filters": []})},
    }

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:list",
        params_filter_invalid,
        calendar_view.id,
        HTTP_400_BAD_REQUEST,
        {
            "detail": {
                "filter_type": [
                    {
                        "code": "invalid_choice",
                        "error": '"invalid" is not a valid choice.',
                    }
                ]
            },
            "error": "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
        },
    )

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:public_rows",
        params_filter_invalid,
        calendar_view.slug,
        HTTP_400_BAD_REQUEST,
        {
            "detail": {
                "filter_type": [
                    {
                        "code": "invalid_choice",
                        "error": '"invalid" is not a valid choice.',
                    }
                ]
            },
            "error": "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
        },
    )


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_adhoc_filters(
    premium_data_fixture,
    api_client,
    data_fixture,
    alternative_per_workspace_license_service,
):
    """
    Test calendar view with adhoc filters
    """

    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(name="Workspace 1", user=user)
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(user=user, database=database)

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [workspace.id]
    )
    field_title = data_fixture.create_text_field(table=table, user=user, name="title")
    field_description = data_fixture.create_text_field(
        table=table, user=user, name="description"
    )
    field_extra = data_fixture.create_text_field(table=table, user=user, name="extra")
    field_num = data_fixture.create_number_field(table=table, user=user, name="num")
    field_bool = data_fixture.create_boolean_field(table=table, user=user, name="bool")
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )
    all_fields = [
        field_title,
        field_description,
        field_extra,
        field_num,
        date_field,
        field_bool,
    ]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )

    NUM_EVENTS = 10

    start = date.today()

    view_handler.update_field_options(
        view=calendar_view,
        field_options={
            field_title.id: {"hidden": False},
            field_num.id: {"hidden": False},
            field_extra.id: {"hidden": False},
            field_description.id: {"hidden": False},
        },
    )

    def make_values(num):
        curr = 0
        field_names = [f"field_{f.id}" for f in all_fields]

        while curr < num:
            values = [
                f"title {curr}",
                f"description {curr}",
                f"extra {curr}",
                curr,
                start + timedelta(days=1 + curr),
                bool(curr % 2),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            RowHandler().create_row(user, table, values=row)

    make_values(NUM_EVENTS)

    vf_bool = view_handler.create_filter(
        user=user, view=calendar_view, field=field_bool, type_name="boolean", value="1"
    )

    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    params = {
        "from_timestamp": f"{start.isoformat()}",
        "to_timestamp": f"{(start + timedelta(days=2+NUM_EVENTS)).isoformat()}",
    }
    field_title_name = f"field_{field_title.id}"
    field_description_name = f"field_{field_description.id}"

    params_filter_simple = {
        **params,
        **{f"filter__field_{field_title.id}__contains": "title 4"},
    }

    # adhoc should should replace view filters in internal view
    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:list",
        params_filter_simple,
        calendar_view.id,
        HTTP_200_OK,
        [{f"field_{field_title.id}": "title 4"}],
    )

    # here adhoc should be applied on top of view filters, so no result
    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:public_rows",
        params_filter_simple,
        calendar_view.slug,
        HTTP_200_OK,
        [],
    )

    # remove internal filter, so title 4 may be returned
    vf_bool.delete()

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:list",
        params_filter_simple,
        calendar_view.id,
        HTTP_200_OK,
        [{field_title_name: "title 4"}],
    )

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:public_rows",
        params_filter_simple,
        calendar_view.slug,
        HTTP_200_OK,
        [{field_title_name: "title 4"}],
    )

    filter_group = {
        "filter_type": "OR",
        "filters": [
            {
                "field": field_description.id,
                "type": "contains",
                "value": "description 3",
            },
            {"field": field_title.id, "type": "contains", "value": "title 4"},
        ],
    }
    params_filter_fgroup = {**params, **{"filters": json.dumps(filter_group)}}

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:public_rows",
        params_filter_fgroup,
        calendar_view.slug,
        HTTP_200_OK,
        [{field_description_name: "description 3"}, {field_title_name: "title 4"}],
    )

    do_calendar_view_request(
        req_get,
        "api:database:views:calendar:list",
        params_filter_fgroup,
        calendar_view.id,
        HTTP_200_OK,
        [{field_description_name: "description 3"}, {field_title_name: "title 4"}],
    )


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_filters(premium_data_fixture, api_client, data_fixture):
    """
    Test ical feed with calendar with view filters
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_text_field(table=table, user=user)
    field_extra = data_fixture.create_text_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)
    field_bool = data_fixture.create_boolean_field(table=table, user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )
    all_fields = [
        field_title,
        field_description,
        field_extra,
        field_num,
        date_field,
        field_bool,
    ]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()
    NUM_EVENTS = 6

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
                start + timedelta(days=1 + curr),
                bool(curr % 2),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            tmodel.objects.create(**row)

    view_handler.update_field_options(
        view=calendar_view,
        field_options={
            field_title.id: {"hidden": False},
            field_num.id: {"hidden": False},
            field_extra.id: {"hidden": False},
            field_description.id: {"hidden": False},
        },
    )

    make_values(NUM_EVENTS)

    vf_bool = view_handler.create_filter(
        user=user, view=calendar_view, field=field_bool, type_name="boolean", value="1"
    )

    assert not calendar_view.ical_public
    assert not calendar_view.ical_feed_url
    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    # make ical feed public
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )
    assert resp.status_code == HTTP_200_OK
    assert resp.data["ical_feed_url"]
    calendar_view.refresh_from_db()
    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.headers.get("content-type") == "text/calendar", resp.headers
    assert resp.content

    feed = Calendar.from_ical(resp.content)
    assert feed
    assert feed.get("PRODID") == "Baserow / baserow.io"
    evsummary = [ev.get("SUMMARY") for ev in feed.walk("VEVENT")]

    assert len(evsummary) == 3  # NUM_EVENTS/ 2
    titles = ["title 1 - ", "title 3 - ", "title 5 -"]
    for tstart, summary in zip(titles, evsummary):
        assert summary.startswith(tstart), (
            summary,
            tstart,
        )

    view_handler.create_filter(
        user=user,
        view=calendar_view,
        field=field_title,
        type_name="equal",
        value="title 4",
    )

    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.headers.get("content-type") == "text/calendar", resp.headers
    assert resp.content

    feed = Calendar.from_ical(resp.content)
    assert feed
    evsummary = [ev.get("SUMMARY") for ev in feed.walk("VEVENT")]

    assert len(evsummary) == 0  # both filters in effect, they exclude any row

    vf_bool.delete()

    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.headers.get("content-type") == "text/calendar", resp.headers
    assert resp.content

    feed = Calendar.from_ical(resp.content)
    assert feed
    evsummary = [ev.get("SUMMARY") for ev in feed.walk("VEVENT")]

    assert len(evsummary) == 1  # just one title
    titles = ["title 4 - "]
    for tstart, summary in zip(titles, evsummary):
        assert summary.startswith(tstart)


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_feed_with_date_and_select_related_field_in_queryset(
    premium_data_fixture, api_client, data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table, _, _, _, context = setup_interesting_test_table(
        premium_data_fixture, user=user
    )
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=True,
    )
    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )

    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )
    assert resp.status_code == HTTP_200_OK
    assert resp.data["ical_feed_url"]

    calendar_view.refresh_from_db()
    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )
    assert resp.status_code == HTTP_200_OK
