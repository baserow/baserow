from unittest.mock import patch

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
import responses
from freezegun import freeze_time
from PIL import Image
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
)

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.models import (
    FormView,
    FormViewFieldOptions,
    FormViewFieldOptionsCondition,
    FormViewFieldOptionsConditionGroup,
)
from baserow.core.user_files.models import UserFile
from baserow.test_utils.helpers import (
    AnyInt,
    is_dict_subset,
    setup_interesting_test_table,
)

ICAL_FEED_WITH_ONE_ITEMS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ical.marudot.com//iCal Event Maker
X-WR-CALNAME:Test feed
NAME:Test feed
CALSCALE:GREGORIAN
BEGIN:VTIMEZONE
TZID:Europe/Berlin
LAST-MODIFIED:20231222T233358Z
TZURL:https://www.tzurl.org/zoneinfo-outlook/Europe/Berlin
X-LIC-LOCATION:Europe/Berlin
BEGIN:DAYLIGHT
TZNAME:CEST
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZNAME:CET
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
DTSTAMP:20240901T195538Z
UID:1725220374375-34056@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240901T100000
DTEND;TZID=Europe/Berlin:20240901T110000
SUMMARY:Test event 0
URL:https://baserow.io
DESCRIPTION:Test description 1
LOCATION:Amsterdam
END:VEVENT
END:VCALENDAR"""


@pytest.mark.django_db
def test_create_form_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    user_file_1 = data_fixture.create_user_file()
    user_file_2 = data_fixture.create_user_file()

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test Form",
            "type": "form",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["slug"]) == 43
    assert response_json["type"] == "form"
    assert response_json["name"] == "Test Form"
    assert response_json["mode"] == "form"
    assert response_json["table_id"] == table.id
    assert response_json["public"] is False
    assert response_json["title"] == ""
    assert response_json["description"] == ""
    assert response_json["cover_image"] is None
    assert response_json["logo_image"] is None
    assert response_json["submit_text"] == "Submit"
    assert response_json["submit_action"] == "MESSAGE"
    assert response_json["submit_action_redirect_url"] == ""

    form = FormView.objects.all()[0]
    assert response_json["id"] == form.id
    assert response_json["name"] == form.name
    assert response_json["order"] == form.order
    assert response_json["slug"] == str(form.slug)
    assert form.table_id == table.id
    assert form.public is False
    assert form.title == ""
    assert form.description == ""
    assert form.cover_image is None
    assert form.logo_image is None
    assert form.submit_text == "Submit"
    assert form.submit_action == "MESSAGE"
    assert form.submit_action_redirect_url == ""
    assert "filters" not in response_json
    assert "sortings" not in response_json
    assert "group_bys" not in response_json
    assert "decorations" not in response_json

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "slug": "Test",
            "name": "Test Form 2",
            "type": "form",
            "public": True,
            "title": "Title",
            "description": "Description",
            "cover_image": {"name": user_file_1.name},
            "logo_image": {"name": user_file_2.name},
            "submit_text": "NEW SUBMIT",
            "submit_action": "REDIRECT",
            "submit_action_redirect_url": "https://localhost",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["slug"] != "Test"
    assert response_json["name"] == "Test Form 2"
    assert response_json["type"] == "form"
    assert response_json["mode"] == "form"
    assert response_json["public"] is True
    assert response_json["title"] == "Title"
    assert response_json["description"] == "Description"
    assert response_json["cover_image"]["name"] == user_file_1.name
    assert response_json["logo_image"]["name"] == user_file_2.name
    assert response_json["submit_text"] == "NEW SUBMIT"
    assert response_json["submit_action"] == "REDIRECT"
    assert response_json["submit_action_redirect_url"] == "https://localhost"

    form = FormView.objects.all()[1]
    assert form.name == "Test Form 2"
    assert form.order == 2
    assert form.table == table
    assert form.public is True
    assert form.title == "Title"
    assert form.description == "Description"
    assert form.cover_image_id == user_file_1.id
    assert form.logo_image_id == user_file_2.id
    assert form.submit_text == "NEW SUBMIT"
    assert form.submit_action == "REDIRECT"
    assert form.submit_action_redirect_url == "https://localhost"

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "type": "form",
            "mode": "form",
            "name": "Test",
            "cover_image": None,
            "logo_image": {"name": user_file_2.name},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["mode"] == "form"
    assert response_json["cover_image"] is None
    assert response_json["logo_image"]["name"] == user_file_2.name


@pytest.mark.django_db(transaction=True)
def test_create_form_view_with_webhooks(api_client, data_fixture):
    """
    Test create form handling with webhooks attached to check if the payload is
    rendered correctly.

    In case of regression, this is a test for a fix for an error:

    File "/baserow/backend/src/baserow/contrib/database/api/views/form/serializers.py",
        line 175, in get_receive_notification_on_submit

        logged_user_id = self.context["user"].id
                     ~~~~~~~~~~~~^^^^^^^^
    KeyError: 'user'
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    data_fixture.create_table_webhook(
        table=table,
        user=user,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
        events=["view.created", "view.updated", "view.deleted"],
    )

    # a transaction should be commited and webhooks after_commit hook should be called
    # here.
    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.post(
            reverse("api:database:views:list", kwargs={"table_id": table.id}),
            {
                "name": "Test Form",
                "type": "form",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert m.called

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["slug"]) == 43
    assert response_json["type"] == "form"
    assert response_json["name"] == "Test Form"
    assert response_json["mode"] == "form"
    assert response_json["table_id"] == table.id
    call_args = m.call_args.kwargs
    assert call_args.get("event_type") == "view.created"
    assert is_dict_subset(
        {
            "event_type": "view.created",
            "payload": {
                "view": {
                    "table_id": table.id,
                    "type": "form",
                    "name": "Test Form",
                    "id": response_json["id"],
                }
            },
        },
        call_args,
    ), call_args

    assert "receive_notification_on_submit" in call_args["payload"]["view"], call_args[
        "payload"
    ]["view"]


@pytest.mark.django_db
def test_update_form_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_form_view(table=table)
    user_file_1 = data_fixture.create_user_file()
    user_file_2 = data_fixture.create_user_file()

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        url,
        {
            "slug": "test",
            "name": "Test Form 2",
            "type": "form",
            "public": True,
            "title": "Title",
            "submit_text": "Patched Submit",
            "description": "Description",
            "cover_image": {"name": user_file_1.name},
            "logo_image": {"name": user_file_2.name},
            "submit_action": "REDIRECT",
            "submit_action_redirect_url": "https://localhost",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["slug"] != "test"
    assert response_json["slug"] == str(view.slug)
    assert response_json["name"] == "Test Form 2"
    assert response_json["type"] == "form"
    assert response_json["mode"] == "form"
    assert response_json["title"] == "Title"
    assert response_json["description"] == "Description"
    assert response_json["cover_image"]["name"] == user_file_1.name
    assert response_json["logo_image"]["name"] == user_file_2.name
    assert response_json["submit_text"] == "Patched Submit"
    assert response_json["submit_action"] == "REDIRECT"
    assert response_json["submit_action_redirect_url"] == "https://localhost"

    form = FormView.objects.all()[0]
    assert form.name == "Test Form 2"
    assert form.table == table
    assert form.public is True
    assert form.title == "Title"
    assert form.description == "Description"
    assert form.mode == "form"
    assert form.cover_image_id == user_file_1.id
    assert form.logo_image_id == user_file_2.id
    assert form.submit_text == "Patched Submit"
    assert form.submit_action == "REDIRECT"
    assert form.submit_action_redirect_url == "https://localhost"

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        url,
        {
            "cover_image": {"name": user_file_2.name},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["cover_image"]["name"] == user_file_2.name
    assert response_json["logo_image"]["name"] == user_file_2.name

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        url,
        {
            "cover_image": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["cover_image"] is None
    assert response_json["mode"] == "form"
    assert response_json["logo_image"]["name"] == user_file_2.name


@pytest.mark.django_db
def test_update_form_view_invalid_mode(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_form_view(table=table)

    url = reverse("api:database:views:item", kwargs={"view_id": view.id})
    response = api_client.patch(
        url,
        {"mode": "not_existing"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["mode"][0]["code"] == "invalid_choice"


@pytest.mark.django_db
def test_meta_submit_form_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    user_file_1 = data_fixture.create_user_file()
    user_file_2 = data_fixture.create_user_file()
    form = data_fixture.create_form_view(
        table=table,
        title="Title",
        description="Description",
        cover_image=user_file_1,
        logo_image=user_file_2,
    )
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    disabled_field = data_fixture.create_text_field(table=table)
    read_only_field = data_fixture.create_text_field(table=table, read_only=True)
    data_fixture.create_form_view_field_option(
        form,
        text_field,
        name="Text field title",
        description="Text field description",
        required=True,
        enabled=True,
        order=1,
    )
    data_fixture.create_form_view_field_option(
        form, number_field, required=False, enabled=True, order=2
    )
    data_fixture.create_form_view_field_option(
        form, disabled_field, required=False, enabled=False, order=3
    )
    # This one should be ignored because the field is read_only
    data_fixture.create_form_view_field_option(
        form, read_only_field, required=False, enabled=True, order=4
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": "NOT_EXISTING"})
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FORM_DOES_NOT_EXIST"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FORM_DOES_NOT_EXIST"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token_2}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FORM_DOES_NOT_EXIST"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK

    form.public = True
    form.save()

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json["title"] == "Title"
    assert response_json["description"] == "Description"
    assert response_json["cover_image"]["name"] == user_file_1.name
    assert response_json["logo_image"]["name"] == user_file_2.name
    assert response_json["mode"] == "form"
    assert len(response_json["fields"]) == 2
    assert response_json["fields"][0] == {
        "name": "Text field title",
        "description": "Text field description",
        "required": True,
        "order": 1,
        "condition_type": "AND",
        "conditions": [],
        "condition_groups": [],
        "show_when_matching_conditions": False,
        "field": {
            "id": text_field.id,
            "name": text_field.name,
            "type": "text",
            "text_default": "",
        },
        "field_component": "default",
    }
    assert response_json["fields"][1] == {
        "name": number_field.name,
        "description": "",
        "required": False,
        "order": 2,
        "condition_type": "AND",
        "conditions": [],
        "condition_groups": [],
        "show_when_matching_conditions": False,
        "field": {
            "id": number_field.id,
            "name": number_field.name,
            "type": "number",
            "number_decimal_places": 0,
            "number_default": None,
            "number_negative": False,
            "number_prefix": "",
            "number_separator": "",
            "number_suffix": "",
        },
        "field_component": "default",
    }


@pytest.mark.django_db
def test_meta_submit_form_view_allowed_select_options_override(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form = data_fixture.create_form_view(table=table, public=True)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(
        field=single_select_field,
        value="Option 1",
        color="1",
    )
    option_2 = data_fixture.create_select_option(
        field=single_select_field,
        value="Option 2",
        color="1",
    )
    single_select_field_2 = data_fixture.create_single_select_field(table=table)
    option_3 = data_fixture.create_select_option(
        field=single_select_field_2,
        value="Option 3",
        color="1",
    )
    option_4 = data_fixture.create_select_option(
        field=single_select_field_2,
        value="Option 4",
        color="1",
    )
    option_5 = data_fixture.create_select_option(
        field=single_select_field_2,
        value="Option 5",
        color="1",
    )
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_6 = data_fixture.create_select_option(
        field=multiple_select_field,
        value="Option 6",
        color="1",
    )
    option_7 = data_fixture.create_select_option(
        field=multiple_select_field,
        value="Option 7",
        color="1",
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form.id})
    api_client.patch(
        url,
        {
            "field_options": {
                str(single_select_field.id): {
                    "enabled": True,
                    "include_all_select_options": True,
                    "allowed_select_options": [],
                },
                str(single_select_field_2.id): {
                    "enabled": True,
                    "include_all_select_options": False,
                    "allowed_select_options": [option_3.id, option_4.id],
                },
                str(multiple_select_field.id): {
                    "enabled": True,
                    "include_all_select_options": False,
                    "allowed_select_options": [option_6.id],
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    # Expect all options to be included because `include_all_select_options=True`
    assert response_json["fields"][0]["field"]["select_options"] == [
        {"id": option_1.id, "value": "Option 1", "color": "1"},
        {"id": option_2.id, "value": "Option 2", "color": "1"},
    ]
    # Expect only the `allowed_select_options` to be included because
    # `include_all_select_options=False`.
    assert response_json["fields"][1]["field"]["select_options"] == [
        {"id": option_3.id, "value": "Option 3", "color": "1"},
        {"id": option_4.id, "value": "Option 4", "color": "1"},
    ]
    # Expect only the `allowed_select_options` to be included because
    # `include_all_select_options=False`.
    assert response_json["fields"][2]["field"]["select_options"] == [
        {"id": option_6.id, "value": "Option 6", "color": "1"}
    ]


@pytest.mark.django_db
def test_submit_form_view_with_allowed_select_options_override_single_select(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form = data_fixture.create_form_view(table=table, public=True)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(
        field=single_select_field,
        value="Option 1",
        color="1",
    )
    option_2 = data_fixture.create_select_option(
        field=single_select_field,
        value="Option 2",
        color="1",
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form.id})
    api_client.patch(
        url,
        {
            "field_options": {
                str(single_select_field.id): {
                    "enabled": True,
                    "include_all_select_options": False,
                    "allowed_select_options": [option_1.id],
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{single_select_field.id}": option_1.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_200_OK

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{single_select_field.id}": option_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    response_json = response.json()
    assert response_json == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            f"field_{single_select_field.id}": [
                {
                    "error": f"The provided select option {option_2.id} is not "
                    f"allowed.",
                    "code": "invalid",
                }
            ]
        },
    }


@pytest.mark.django_db
def test_submit_form_view_with_allowed_select_options_override_multiple_select(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form = data_fixture.create_form_view(table=table, public=True)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_1 = data_fixture.create_select_option(
        field=multiple_select_field,
        value="Option 1",
        color="1",
    )
    option_2 = data_fixture.create_select_option(
        field=multiple_select_field,
        value="Option 2",
        color="1",
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form.id})
    api_client.patch(
        url,
        {
            "field_options": {
                str(multiple_select_field.id): {
                    "enabled": True,
                    "include_all_select_options": False,
                    "allowed_select_options": [option_1.id],
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{multiple_select_field.id}": [option_1.id],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_200_OK

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{multiple_select_field.id}": [option_2.id],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    response_json = response.json()
    assert response_json == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            f"field_{multiple_select_field.id}": {
                "0": [
                    {
                        "error": f"The provided select option {option_2.id} is not "
                        f"allowed.",
                        "code": "invalid",
                    }
                ]
            }
        },
    }


@pytest.mark.django_db
def test_submit_form_with_link_row_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    table_2 = data_fixture.create_database_table(user=user, database=table.database)
    primary_t2 = data_fixture.create_text_field(table=table_2, primary=True)

    t2_model = table_2.get_model()
    r1 = t2_model.objects.create(**{f"field_{primary_t2.id}": "a"})

    form = data_fixture.create_form_view(
        table=table,
        public=True,
        submit_action_message="Test",
        submit_action_redirect_url="https://baserow.io",
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=table_2
    )

    data_fixture.create_form_view_field_option(
        form, link_row_field, required=True, enabled=True, order=1
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(url, {}, format="json")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 1
    assert (
        response_json["detail"][f"field_{link_row_field.id}"][0]["code"] == "required"
    )

    response = api_client.post(url, {link_row_field.db_column: [r1.id]}, format="json")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "row_id": AnyInt(),
        "submit_action": "MESSAGE",
        "submit_action_message": "Test",
        "submit_action_redirect_url": "https://baserow.io",
    }


@pytest.mark.django_db
@responses.activate
def test_submit_form_with_data_sync(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    handler = DataSyncHandler()

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )

    form = data_fixture.create_form_view(
        table=data_sync.table,
        public=True,
        submit_action_message="Test",
        submit_action_redirect_url="https://baserow.io",
    )

    FormViewFieldOptions.objects.all().update(required=True, enabled=True)

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(url, {"summary": "Test"}, format="json")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_CANNOT_CREATE_ROWS_IN_TABLE"


@pytest.mark.django_db
def test_submit_form_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form = data_fixture.create_form_view(
        table=table,
        submit_action_message="Test",
        submit_action_redirect_url="https://baserow.io",
    )
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    disabled_field = data_fixture.create_text_field(table=table)
    read_only_field = data_fixture.create_text_field(table=table, read_only=True)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form, number_field, required=False, enabled=True, order=2
    )
    data_fixture.create_form_view_field_option(
        form, disabled_field, required=False, enabled=False, order=3
    )
    data_fixture.create_form_view_field_option(
        form, read_only_field, required=True, enabled=True, order=4
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": "NOT_EXISTING"})
    response = api_client.post(url, {}, format="json")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FORM_DOES_NOT_EXIST"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(url, {}, format="json")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FORM_DOES_NOT_EXIST"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT" f" {token_2}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FORM_DOES_NOT_EXIST"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            # We do not provide the text field value, but that one is required and we
            # provide a wrong value for the number field, so we expect two errors.
            f"field_{number_field.id}": {},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 2
    assert response_json["detail"][f"field_{text_field.id}"][0]["code"] == "required"
    assert response_json["detail"][f"field_{number_field.id}"][0]["code"] == "invalid"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "Valid",
            f"field_{number_field.id}": 0,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "row_id": 1,
        "submit_action": "MESSAGE",
        "submit_action_message": "Test",
        "submit_action_redirect_url": "https://baserow.io",
    }

    model = table.get_model()
    all = model.objects.all()
    assert len(all) == 1
    assert getattr(all[0], f"field_{text_field.id}") == "Valid"
    assert getattr(all[0], f"field_{number_field.id}") == 0

    form.public = True
    form.save()

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {},
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 1
    assert response_json["detail"][f"field_{text_field.id}"][0]["code"] == "required"

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "A value",
            f"field_{disabled_field.id}": "Value",
        },
        format="json",
    )
    assert response.status_code == HTTP_200_OK

    model = table.get_model()
    all = model.objects.all()
    assert len(all) == 2
    assert getattr(all[1], f"field_{text_field.id}") == "A value"
    assert getattr(all[1], f"field_{number_field.id}") is None
    assert getattr(all[1], f"field_{disabled_field.id}") is None

    date_field = data_fixture.create_date_field(table=table)
    file_field = data_fixture.create_file_field(table=table)
    url_field = data_fixture.create_url_field(table=table)
    single_select_field = data_fixture.create_single_select_field(table=table)
    boolean_field = data_fixture.create_boolean_field(table=table)
    phone_field = data_fixture.create_phone_number_field(table=table)
    data_fixture.create_form_view_field_option(
        form, file_field, required=True, enabled=True
    )
    data_fixture.create_form_view_field_option(
        form, url_field, required=True, enabled=True
    )
    data_fixture.create_form_view_field_option(
        form, single_select_field, required=True, enabled=True
    )
    data_fixture.create_form_view_field_option(
        form, boolean_field, required=True, enabled=True
    )
    data_fixture.create_form_view_field_option(
        form, date_field, required=True, enabled=True
    )
    data_fixture.create_form_view_field_option(
        form, phone_field, required=True, enabled=True
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "",
            f"field_{date_field.id}": None,
            f"field_{file_field.id}": [],
            f"field_{url_field.id}": "",
            f"field_{single_select_field.id}": "",
            f"field_{boolean_field.id}": False,
            f"field_{phone_field.id}": "",
        },
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 7

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {},
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 7


@pytest.mark.django_db
def test_submit_form_view_skip_required_with_conditions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True
    )
    number_option = data_fixture.create_form_view_field_option(
        form, number_field, required=True, enabled=True
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 1

    number_option.show_when_matching_conditions = True
    number_option.save()

    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 1

    # When there is a condition and `show_when_matching_conditions` is `True`,
    # the backend can't validate whether the values match the filter, we we don't do
    # a required validation at all.
    data_fixture.create_form_view_field_options_condition(
        field_option=number_option, field=text_field
    )
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_form_view_link_row_lookup_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    lookup_table = data_fixture.create_database_table(database=database)
    form = data_fixture.create_form_view(table=table)
    form_2 = data_fixture.create_form_view()
    text_field = data_fixture.create_text_field(table=table)
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=lookup_table
    )
    disabled_link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=lookup_table
    )
    unrelated_link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=lookup_table
    )
    primary_related_field = data_fixture.create_text_field(
        table=lookup_table, primary=True
    )
    data_fixture.create_text_field(table=lookup_table)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form, link_row_field, required=True, enabled=True, order=2
    )
    data_fixture.create_form_view_field_option(
        form, disabled_link_row_field, required=True, enabled=False, order=3
    )
    data_fixture.create_form_view_field_option(
        form_2, unrelated_link_row_field, required=True, enabled=True, order=1
    )

    lookup_model = lookup_table.get_model()
    i1 = lookup_model.objects.create(**{f"field_{primary_related_field.id}": "Test 1"})
    i2 = lookup_model.objects.create(**{f"field_{primary_related_field.id}": "Test 2"})
    i3 = lookup_model.objects.create(**{f"field_{primary_related_field.id}": "Test 3"})

    # Anonymous, not existing slug.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": "NOT_EXISTING", "field_id": link_row_field.id},
    )
    response = api_client.get(url, {})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # Anonymous, existing slug, but form is not public.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # user that doesn't have access to the workspace, existing slug,
    # but form is not public.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token_2}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # valid user, existing slug, but invalid wrong field type.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": text_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # valid user, existing slug, but invalid wrong field type.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": 0},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # valid user, existing slug, but disabled link row field.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": disabled_link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # valid user, existing slug, but unrelated link row field.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": unrelated_link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    form.public = True
    form.save()

    # anonymous, existing slug, public form, correct link row field.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 3
    assert len(response_json["results"]) == 3
    assert response_json["results"][0]["id"] == i1.id
    assert response_json["results"][0]["value"] == "Test 1"
    assert response_json["results"][1]["id"] == i2.id
    assert response_json["results"][2]["id"] == i3.id

    # same as before only now with search.
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        f"{url}?search=Test 2",
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == i2.id
    assert response_json["results"][0]["value"] == "Test 2"

    # same as before only now with pagination
    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        f"{url}?size=1&page=2",
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 3
    assert response_json["next"] is not None
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == i2.id
    assert response_json["results"][0]["value"] == "Test 2"


@pytest.mark.django_db
def test_form_view_link_row_lookup_view_with_link_row_limit_selection_view(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    lookup_table = data_fixture.create_database_table(database=database)
    form = data_fixture.create_form_view(table=table, public=True)
    text_field = data_fixture.create_text_field(table=table)
    primary_related_field = data_fixture.create_text_field(
        table=lookup_table, primary=True
    )
    secondary_related_field = data_fixture.create_text_field(
        table=lookup_table, primary=False
    )
    lookup_table_view = data_fixture.create_grid_view(
        table=lookup_table, name="Filtered"
    )
    data_fixture.create_view_filter(
        user,
        field=primary_related_field,
        view=lookup_table_view,
        type="contains",
        value="1",
    )
    data_fixture.create_view_filter(
        user,
        field=secondary_related_field,
        view=lookup_table_view,
        type="contains",
        value="1",
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table,
        link_row_table=lookup_table,
        link_row_limit_selection_view=lookup_table_view,
    )
    data_fixture.create_text_field(table=lookup_table)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form, link_row_field, required=True, enabled=True, order=2
    )

    lookup_model = lookup_table.get_model()
    i1 = lookup_model.objects.create(
        **{
            f"field_{primary_related_field.id}": "Test 1",
            f"field_{secondary_related_field.id}": "Test 1",
        }
    )
    i2 = lookup_model.objects.create(
        **{
            f"field_{primary_related_field.id}": "Test 2",
            f"field_{secondary_related_field.id}": "Test 2",
        }
    )
    i3 = lookup_model.objects.create(
        **{
            f"field_{primary_related_field.id}": "Test 3",
            f"field_{secondary_related_field.id}": "Test 3",
        }
    )

    url = reverse(
        "api:database:views:link_row_field_lookup",
        kwargs={"slug": form.slug, "field_id": link_row_field.id},
    )
    response = api_client.get(
        url,
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == i1.id
    assert response_json["results"][0]["value"] == "Test 1"


@pytest.mark.django_db
def test_test_enable_form_view_file_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    created_on_field = data_fixture.create_created_on_field(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {"field_options": {created_on_field.id: {"enabled": True}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FORM_VIEW_FIELD_TYPE_IS_NOT_SUPPORTED"
    assert (
        response_json["detail"]
        == "The created_on field type is not compatible with the form view."
    )


@pytest.mark.django_db
def test_cannot_enable_read_only_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, read_only=True)
    form_view = data_fixture.create_form_view(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {"field_options": {field.id: {"enabled": True}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FORM_VIEW_READ_ONLY_FIELD_IS_NOT_SUPPORTED"


@pytest.mark.django_db
def test_form_view_multiple_collaborators_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        table=table
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {"field_options": {multiple_collaborators_field.id: {"enabled": True}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "field_options": {
            str(multiple_collaborators_field.id): {
                "name": "",
                "description": "",
                "enabled": True,
                "required": True,
                "order": 32767,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            }
        }
    }


@pytest.mark.django_db
def test_get_form_view_field_options(
    api_client, data_fixture, django_assert_max_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=True,
    )
    text_field_option_2 = data_fixture.create_form_view_field_option(
        form_view=form_view, field=text_field_2
    )
    condition_group_1 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option
    )
    condition_1 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field_2, group=condition_group_1
    )

    with CaptureQueriesContext(connection) as captured:
        url = reverse(
            "api:database:views:field_options", kwargs={"view_id": form_view.id}
        )
        response = api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()

    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "order": 32767,
                "show_when_matching_conditions": True,
                "condition_type": "AND",
                "condition_groups": [
                    {
                        "id": condition_group_1.id,
                        "filter_type": "AND",
                        "parent_group": None,
                    },
                ],
                "conditions": [
                    {
                        "id": condition_1.id,
                        "field": text_field_2.id,
                        "type": "equal",
                        "value": condition_1.value,
                        "group": condition_group_1.id,
                    }
                ],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "order": 32767,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "conditions": [],
                "condition_groups": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }

    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option_3 = data_fixture.create_form_view_field_option(
        form_view=form_view, field=text_field_3
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field_2
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_2, field=text_field_3
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_3, field=text_field
    )

    with django_assert_max_num_queries(len(captured.captured_queries)):
        api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_create(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "condition_type": "OR",
                    "condition_groups": [],
                    "conditions": [
                        {
                            "id": 0,
                            "field": text_field_2.id,
                            "type": "equal",
                            "value": "test",
                            "group": None,
                        }
                    ],
                    "field_component": "test",
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    condition = FormViewFieldOptionsCondition.objects.all().first()
    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": True,
                "condition_type": "OR",
                "order": 32767,
                "condition_groups": [],
                "conditions": [
                    {
                        "id": condition.id,
                        "field": text_field_2.id,
                        "type": "equal",
                        "value": "test",
                        "group": None,
                    }
                ],
                "field_component": "test",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }


@pytest.mark.django_db
def test_patch_form_view_field_options_condition_groups_create(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "condition_type": "OR",
                    "condition_groups": [
                        {
                            "id": 0,
                            "filter_type": "OR",
                        },
                        {
                            "id": -1,
                            "filter_type": "OR",
                        },
                    ],
                    "conditions": [
                        {
                            "id": 0,
                            "field": text_field_2.id,
                            "type": "equal",
                            "value": "test",
                            "group": 0,
                        },
                        {
                            "id": -1,
                            "field": text_field_2.id,
                            "type": "equal",
                            "value": "test",
                            "group": -1,
                        },
                    ],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    conditions = FormViewFieldOptionsCondition.objects.all().values("id", "group_id")
    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": True,
                "condition_type": "OR",
                "order": 32767,
                "condition_groups": [
                    {
                        "id": conditions[0]["group_id"],
                        "filter_type": "OR",
                        "parent_group": None,
                    },
                    {
                        "id": conditions[1]["group_id"],
                        "filter_type": "OR",
                        "parent_group": None,
                    },
                ],
                "conditions": [
                    {
                        "id": conditions[0]["id"],
                        "field": text_field_2.id,
                        "type": "equal",
                        "value": "test",
                        "group": conditions[0]["group_id"],
                    },
                    {
                        "id": conditions[1]["id"],
                        "field": text_field_2.id,
                        "type": "equal",
                        "value": "test",
                        "group": conditions[1]["group_id"],
                    },
                ],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_update(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    condition_1 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field_2
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "condition_groups": [],
                    "conditions": [
                        {
                            "id": condition_1.id,
                            "field": text_field_3.id,
                            "type": "not_equal",
                            "value": "test",
                            "group": None,
                        }
                    ],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": True,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [
                    {
                        "id": condition_1.id,
                        "field": text_field_3.id,
                        "type": "not_equal",
                        "value": "test",
                        "group": None,
                    }
                ],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_3.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }


@pytest.mark.django_db
def test_patch_form_view_field_options_condition_groups_update(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    condition_group_1 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option, filter_type="AND"
    )
    condition_1 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field_2, group=condition_group_1
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "condition_groups": [],
                    "conditions": [
                        {
                            "id": condition_1.id,
                            "field": text_field_3.id,
                            "type": "not_equal",
                            "value": "test",
                            "group": condition_group_1.id,
                        }
                    ],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response_json["error"]
        == "ERROR_FORM_VIEW_FIELD_OPTIONS_CONDITION_GROUP_DOES_NOT_EXIST"
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "condition_groups": [
                        {"id": condition_group_1.id, "filter_type": "OR"}
                    ],
                    "conditions": [
                        {
                            "id": condition_1.id,
                            "field": text_field_3.id,
                            "type": "not_equal",
                            "value": "test",
                            "group": condition_group_1.id,
                        }
                    ],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": True,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [
                    {
                        "id": condition_group_1.id,
                        "filter_type": "OR",
                        "parent_group": None,
                    }
                ],
                "conditions": [
                    {
                        "id": condition_1.id,
                        "field": text_field_3.id,
                        "type": "not_equal",
                        "value": "test",
                        "group": condition_group_1.id,
                    }
                ],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_3.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_update_position(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    text_field_option_2 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_2,
        show_when_matching_conditions=False,
    )
    text_field_option_3 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_3,
        show_when_matching_conditions=True,
    )
    condition = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_3, field=text_field_2
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "order": 1,
                    "show_when_matching_conditions": False,
                    "condition_groups": [],
                    "conditions": [],
                },
                str(text_field_3.id): {
                    "order": 2,
                    "show_when_matching_conditions": True,
                },
                str(text_field_2.id): {
                    "order": 3,
                    "show_when_matching_conditions": False,
                    "condition_groups": [],
                    "conditions": [],
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 1,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_3.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": True,
                "condition_type": "AND",
                "order": 2,
                "condition_groups": [],
                "conditions": [
                    {
                        "id": condition.id,
                        "field": text_field_2.id,
                        "type": condition.type,
                        "value": condition.value,
                        "group": None,
                    }
                ],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 3,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_delete(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field_2
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "conditions": [],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": True,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_3.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }


@pytest.mark.django_db
def test_patch_form_view_field_options_condition_groups_delete(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    condition_group_1 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field_2, group=condition_group_1
    )

    assert FormViewFieldOptionsConditionGroup.objects.count() == 1

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "conditions": [],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json == {
        "field_options": {
            str(text_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": True,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_2.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
            str(text_field_3.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "condition_groups": [],
                "conditions": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            },
        }
    }


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_create_invalid_field(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    field_in_another_table = data_fixture.create_text_field()
    data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
        show_when_matching_conditions=False,
    )
    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "show_when_matching_conditions": True,
                    "condition_type": "OR",
                    "condition_groups": [],
                    "conditions": [
                        {
                            "id": 0,
                            "field": field_in_another_table.id,
                            "type": "equal",
                            "value": "test",
                            "group": None,
                        }
                    ],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_FIELD_NOT_IN_TABLE"


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_can_be_nested(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    form_view = data_fixture.create_form_view(table=table)
    data_fixture.warm_cache_before_counting_queries()

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})

    # Nested groups cannot be created in a single request.
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "condition_groups": [
                        {
                            "id": 0,
                            "filter_type": "AND",
                        },
                        {
                            "id": -1,
                            "filter_type": "AND",
                            "parent_group": 0,
                        },
                    ],
                    "conditions": [
                        {
                            "id": 0,
                            "field": text_field_2.id,
                            "type": "equal",
                            "value": "test",
                            "group": -1,
                        }
                    ],
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST

    # Create the root group first.
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "condition_groups": [
                        {
                            "id": 0,
                            "filter_type": "AND",
                        }
                    ],
                    "conditions": [
                        {
                            "id": 0,
                            "field": text_field_2.id,
                            "type": "equal",
                            "value": "test",
                            "group": 0,
                        }
                    ],
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    root_group = response_json["field_options"][str(text_field.id)]["condition_groups"][
        0
    ]

    # And then create the nested group with filters.
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field.id): {
                    "condition_groups": [
                        root_group,
                        {
                            "id": 0,
                            "filter_type": "AND",
                            "parent_group": root_group["id"],
                        },
                    ],
                    "conditions": [
                        {
                            "id": 0,
                            "field": text_field_2.id,
                            "type": "equal",
                            "value": "test",
                            "group": 0,
                        }
                    ],
                },
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    parent_group, child_group_1 = response_json["field_options"][str(text_field.id)][
        "condition_groups"
    ]
    assert child_group_1["parent_group"] == parent_group["id"]
    assert len(response_json["field_options"][str(text_field.id)]["conditions"]) == 1
    condition = response_json["field_options"][str(text_field.id)]["conditions"][0]
    assert condition["group"] == child_group_1["id"]


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_create_num_queries(
    api_client, data_fixture, django_assert_max_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    form_view = data_fixture.create_form_view(table=table)
    data_fixture.warm_cache_before_counting_queries()

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})

    with CaptureQueriesContext(connection) as captured:
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field.id): {
                        "condition_groups": [
                            {
                                "id": 0,
                                "filter_type": "AND",
                            }
                        ],
                        "conditions": [
                            {
                                "id": 0,
                                "field": text_field_2.id,
                                "type": "equal",
                                "value": "test",
                                "group": 0,
                            }
                        ],
                    },
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    # Delete newly created form condition because we want to do the same below with
    # the same amount of queries.
    FormViewFieldOptionsCondition.objects.all().delete()
    FormViewFieldOptionsConditionGroup.objects.all().delete()

    # Even though we're adding more conditions, we expect to execute the sam amount
    # of queries.
    with django_assert_max_num_queries(len(captured.captured_queries)):
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field.id): {
                        "condition_groups": [
                            {
                                "id": 0,
                                "filter_type": "AND",
                            },
                            {
                                "id": -1,
                                "filter_type": "AND",
                            },
                        ],
                        "conditions": [
                            {
                                "id": 0,
                                "field": text_field.id,
                                "type": "equal",
                                "value": "test",
                                "group": 0,
                            },
                            {
                                "id": 0,
                                "field": text_field_2.id,
                                "type": "equal",
                                "value": "test",
                                "group": -1,
                            },
                        ],
                    },
                    str(text_field_2.id): {
                        "condition_groups": [
                            {
                                "id": -2,
                                "filter_type": "AND",
                            }
                        ],
                        "conditions": [
                            {
                                "id": 0,
                                "field": text_field.id,
                                "type": "equal",
                                "value": "test",
                                "group": -2,
                            }
                        ],
                    },
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_update_num_queries(
    api_client, data_fixture, django_assert_num_queries, bypass_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
    )
    text_field_option_2 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_2,
    )
    text_field_option_3 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_3,
    )
    condition_group_1 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option, filter_type="AND"
    )
    condition_1 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option,
        field=text_field,
        group=condition_group_1,
        value="a",
    )
    condition_1_2 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option,
        field=text_field,
        group=condition_group_1,
        value="a",
    )
    condition_group_2 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option_2, filter_type="AND"
    )
    condition_2 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_2,
        field=text_field,
        group=condition_group_2,
        value="a",
    )
    condition_group_3 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option_3, filter_type="AND"
    )
    condition_3 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_3,
        field=text_field,
        group=condition_group_3,
        value="a",
    )
    data_fixture.warm_cache_before_counting_queries()

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})

    with CaptureQueriesContext(connection) as captured:
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field_3.id): {
                        "condition_groups": [
                            {
                                "id": condition_3.group_id,
                                "filter_type": "OR",
                            }
                        ],
                        "conditions": [
                            {
                                "id": condition_3.id,
                                "field": condition_3.field_id,
                                "type": condition_3.type,
                                "value": "b",
                                "group": condition_3.group_id,
                            }
                        ],
                    }
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    # Even though we're update more conditions, we expect to execute the same amount
    # of queries.
    with django_assert_num_queries(len(captured.captured_queries)):
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field.id): {
                        "condition_groups": [
                            {
                                "id": condition_group_1.id,
                                "filter_type": "OR",
                            }
                        ],
                        "conditions": [
                            {
                                "id": condition_1.id,
                                "field": condition_1.field_id,
                                "type": condition_1.type,
                                "value": "b",
                                "group": condition_group_1.id,
                            },
                            {
                                "id": condition_1_2.id,
                                "field": condition_1_2.field_id,
                                "type": condition_1_2.type,
                                "value": "b",
                                "group": condition_group_1.id,
                            },
                        ],
                    },
                    str(text_field_2.id): {
                        "condition_groups": [
                            {
                                "id": condition_group_2.id,
                                "filter_type": "OR",
                            }
                        ],
                        "conditions": [
                            {
                                "id": condition_2.id,
                                "field": condition_2.field_id,
                                "type": condition_2.type,
                                "value": "b",
                                "group": condition_group_2.id,
                            }
                        ],
                    },
                    str(text_field_3.id): {
                        "condition_groups": [
                            {
                                "id": condition_group_3.id,
                                "filter_type": "AND",
                            }
                        ],
                        "conditions": [
                            {
                                "id": condition_3.id,
                                "field": condition_3.field_id,
                                "type": condition_3.type,
                                "value": "b",
                                "group": condition_group_3.id,
                            },
                        ],
                    },
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )


@pytest.mark.django_db
def test_patch_form_view_field_options_conditions_delete_num_queries(
    api_client, data_fixture, django_assert_max_num_queries, bypass_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
    )
    text_field_option_2 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_2,
    )
    text_field_option_3 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_3,
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_2, field=text_field
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_3, field=text_field
    )
    data_fixture.warm_cache_before_counting_queries()

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})

    with CaptureQueriesContext(connection) as captured:
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field_3.id): {
                        "condition_groups": [],
                        "conditions": [],
                    }
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    # Even though we're deleting more conditions, we expect to execute the same amount
    # of queries.
    with django_assert_max_num_queries(len(captured.captured_queries)):
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field.id): {
                        "condition_groups": [],
                        "conditions": [],
                    },
                    str(text_field_2.id): {
                        "condition_groups": [],
                        "conditions": [],
                    },
                    str(text_field_3.id): {
                        "condition_groups": [],
                        "conditions": [],
                    },
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )


@pytest.mark.django_db
def test_patch_form_view_field_options_condition_groups_delete_num_queries(
    api_client, data_fixture, django_assert_max_num_queries, bypass_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)
    text_field_option = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field,
    )
    text_field_option_2 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_2,
    )
    text_field_option_3 = data_fixture.create_form_view_field_option(
        form_view=form_view,
        field=text_field_3,
    )
    condition_group_1 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field, group=condition_group_1
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option, field=text_field, group=condition_group_1
    )
    condition_group_2 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option_2
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_2, field=text_field, group=condition_group_2
    )
    condition_group_3 = data_fixture.create_form_view_field_options_condition_group(
        field_option=text_field_option_3
    )
    data_fixture.create_form_view_field_options_condition(
        field_option=text_field_option_3, field=text_field, group=condition_group_3
    )
    data_fixture.warm_cache_before_counting_queries()

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})

    with CaptureQueriesContext(connection) as captured:
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field_3.id): {
                        "condition_groups": [],
                        "conditions": [],
                    }
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    # Even though we're deleting more conditions, we expect to execute the same amount
    # of queries.
    with django_assert_max_num_queries(len(captured.captured_queries)):
        api_client.patch(
            url,
            {
                "field_options": {
                    str(text_field.id): {
                        "condition_groups": [],
                        "conditions": [],
                    },
                    str(text_field_2.id): {
                        "condition_groups": [],
                        "conditions": [],
                    },
                    str(text_field_3.id): {
                        "condition_groups": [],
                        "conditions": [],
                    },
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )


@pytest.mark.django_db
def test_submit_password_protected_form_view_requires_authorization(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    password = "87654321"
    form_view = data_fixture.create_public_password_protected_form_view(
        table=table,
        password=password,
        submit_action_message="Test",
        submit_action_redirect_url="https://baserow.io",
    )
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    data_fixture.create_form_view_field_option(
        form_view, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form_view, number_field, required=False, enabled=True, order=2
    )

    # without a valid token it is not possible to submit form data
    url = reverse("api:database:views:form:submit", kwargs={"slug": form_view.slug})
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:database:views:form:submit", kwargs={"slug": form_view.slug}),
        {
            f"field_{text_field.id}": "Valid",
            f"field_{number_field.id}": 0,
        },
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # Get the authorization token
    response = api_client.post(
        reverse("api:database:views:public_auth", kwargs={"slug": form_view.slug}),
        {"password": password},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    public_view_token = response_json.get("access_token", None)
    assert public_view_token is not None

    # Add the token in the header
    url = reverse("api:database:views:form:submit", kwargs={"slug": form_view.slug})
    response = api_client.get(
        url, format="json", HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}"
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "Valid",
            f"field_{number_field.id}": 0,
        },
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "row_id": 1,
        "submit_action": "MESSAGE",
        "submit_action_message": "Test",
        "submit_action_redirect_url": "https://baserow.io",
    }

    # The original user can always submit forms, even if password protected
    url = reverse("api:database:views:form:submit", kwargs={"slug": form_view.slug})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "More Valid",
            f"field_{number_field.id}": 1,
        },
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "row_id": 2,
        "submit_action": "MESSAGE",
        "submit_action_message": "Test",
        "submit_action_redirect_url": "https://baserow.io",
    }


@pytest.mark.django_db
def test_changing_password_of_a_public_password_protected_form_view_invalidate_previous_tokens(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    password = "12345678"
    form_view = data_fixture.create_public_password_protected_form_view(
        user=user, password=password
    )

    # Get the authorization token
    response = api_client.post(
        reverse("api:database:views:public_auth", kwargs={"slug": form_view.slug}),
        {"password": password},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    public_view_token = response_json.get("access_token", None)
    assert public_view_token is not None

    # Get access using the token
    response = api_client.get(
        reverse("api:database:views:form:submit", kwargs={"slug": form_view.slug}),
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()

    # Changing password invalidate tokens
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": form_view.id}),
        {"public_view_password": "Just another original password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # Previous tokens are now invalid
    response = api_client.get(
        reverse("api:database:views:form:submit", kwargs={"slug": form_view.slug}),
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_submit_form_view_for_required_number_field_with_0(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    form = data_fixture.create_form_view(
        table=table,
        submit_action_message="Test",
        submit_action_redirect_url="https://baserow.io",
    )
    number_field = data_fixture.create_number_field(
        table=table, number_negative=False, number_decimal_places=0
    )
    data_fixture.create_form_view_field_option(
        form, number_field, required=True, enabled=True, order=2
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {
            f"field_{number_field.id}": "0",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT" f" {token}",
    )
    assert response.status_code == HTTP_200_OK, (
        "Got an error response "
        "instead of the expected "
        "200 OK with body: " + str(response.json())
    )
    response_json = response.json()
    assert response_json == {
        "row_id": 1,
        "submit_action": "MESSAGE",
        "submit_action_message": "Test",
        "submit_action_redirect_url": "https://baserow.io",
    }


@pytest.mark.django_db
def test_upload_file_view(api_client, data_fixture, tmpdir):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    view = data_fixture.create_form_view(public=True)
    file_field = data_fixture.create_file_field()
    data_fixture.create_form_view_field_option(view, field=file_field, enabled=True)

    response = api_client.post(
        reverse(
            "api:database:views:form:upload_file",
            kwargs={"slug": view.slug},
        ),
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_FILE"

    response = api_client.post(
        reverse(
            "api:database:views:form:upload_file",
            kwargs={"slug": view.slug},
        ),
        data={"file": ""},
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_FILE"

    old_limit = settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB
    settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = 6
    response = api_client.post(
        reverse(
            "api:database:views:form:upload_file",
            kwargs={"slug": view.slug},
        ),
        data={"file": SimpleUploadedFile("test.txt", b"Hello World")},
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = old_limit
    assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert response.json()["error"] == "ERROR_FILE_SIZE_TOO_LARGE"
    assert response.json()["detail"] == (
        "The provided file is too large. Max 0MB is allowed."
    )

    response = api_client.post(
        reverse(
            "api:database:views:form:upload_file",
            kwargs={"slug": view.slug},
        ),
        data={"file": "not a file"},
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_FILE"

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    with patch(
        "baserow.core.user_files.handler.get_default_storage"
    ) as get_storage_mock:
        get_storage_mock.return_value = storage

        with freeze_time("2020-01-01 12:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            token = data_fixture.generate_token(user)
            response = api_client.post(
                reverse(
                    "api:database:views:form:upload_file",
                    kwargs={"slug": view.slug},
                ),
                data={"file": file},
                format="multipart",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["size"] == 11
    assert response_json["mime_type"] == "text/plain"
    assert response_json["is_image"] is False
    assert response_json["image_width"] is None
    assert response_json["image_height"] is None
    assert response_json["uploaded_at"] == "2020-01-01T12:00:00Z"
    assert response_json["thumbnails"] is None
    assert response_json["original_name"] == "test.txt"
    assert "localhost:8000" in response_json["url"]

    user_file = UserFile.objects.all().last()
    assert user_file.name == response_json["name"]
    assert response_json["url"].endswith(response_json["name"])
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()

    with patch(
        "baserow.core.user_files.handler.get_default_storage"
    ) as get_storage_mock:
        get_storage_mock.return_value = storage

        token = data_fixture.generate_token(user)
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response_2 = api_client.post(
            reverse(
                "api:database:views:form:upload_file",
                kwargs={"slug": view.slug},
            ),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    # The old file should be provided.
    assert response_2.status_code == HTTP_200_OK
    assert response_2.json()["name"] == response_json["name"]
    assert response_json["original_name"] == "test.txt"

    image = Image.new("RGB", (100, 140), color="red")
    file = SimpleUploadedFile("test.png", b"")
    image.save(file, format="PNG")
    file.seek(0)

    with patch(
        "baserow.core.user_files.handler.get_default_storage"
    ) as get_storage_mock:
        get_storage_mock.return_value = storage

        response = api_client.post(
            reverse(
                "api:database:views:form:upload_file",
                kwargs={"slug": view.slug},
            ),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["mime_type"] == "image/png"
    assert response_json["is_image"] is True
    assert response_json["image_width"] == 100
    assert response_json["image_height"] == 140
    assert len(response_json["thumbnails"]) == 1
    assert "localhost:8000" in response_json["thumbnails"]["tiny"]["url"]
    assert "tiny" in response_json["thumbnails"]["tiny"]["url"]
    assert response_json["thumbnails"]["tiny"]["width"] == 21
    assert response_json["thumbnails"]["tiny"]["height"] == 21
    assert response_json["original_name"] == "test.png"

    user_file = UserFile.objects.all().last()
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()
    file_path = tmpdir.join("thumbnails", "tiny", user_file.name)
    assert file_path.isfile()
    thumbnail = Image.open(file_path.open("rb"))
    assert thumbnail.height == 21
    assert thumbnail.width == 21


@pytest.mark.django_db
def test_upload_file_view_with_no_public_file_field(api_client, data_fixture, tmpdir):
    view = data_fixture.create_form_view(public=True)
    file_field = data_fixture.create_file_field()
    data_fixture.create_form_view_field_option(view, field=file_field, enabled=False)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    with patch("baserow.core.storage.get_default_storage", new=storage):
        with freeze_time("2020-01-01 12:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            response = api_client.post(
                reverse(
                    "api:database:views:form:upload_file",
                    kwargs={"slug": view.slug},
                ),
                data={"file": file},
                format="multipart",
            )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_VIEW_HAS_NO_PUBLIC_FILE_FIELD"


@pytest.mark.django_db
def test_upload_file_view_with_a_rich_text_field_is_possible(
    api_client, data_fixture, tmpdir
):
    view = data_fixture.create_form_view(public=True)
    rich_text_field = data_fixture.create_long_text_field(
        long_text_enable_rich_text=True
    )
    data_fixture.create_form_view_field_option(
        view, field=rich_text_field, enabled=True
    )

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    with patch("baserow.core.storage.get_default_storage", new=storage):
        with freeze_time("2020-01-01 12:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            response = api_client.post(
                reverse(
                    "api:database:views:form:upload_file",
                    kwargs={"slug": view.slug},
                ),
                data={"file": file},
                format="multipart",
            )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_upload_file_form_view_does_not_exist(api_client, data_fixture, tmpdir):
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    with patch("baserow.core.storage.get_default_storage", new=storage):
        with freeze_time("2020-01-01 12:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            response = api_client.post(
                reverse(
                    "api:database:views:form:upload_file",
                    kwargs={"slug": 99999999},
                ),
                data={"file": file},
                format="multipart",
            )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_upload_file_view_form_is_password_protected(api_client, data_fixture, tmpdir):
    password = "password"
    view = data_fixture.create_public_password_protected_form_view(password=password)
    file_field = data_fixture.create_file_field()
    data_fixture.create_form_view_field_option(view, field=file_field, enabled=True)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    with patch("baserow.core.storage.get_default_storage", new=storage):
        with freeze_time("2020-01-01 12:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            response = api_client.post(
                reverse(
                    "api:database:views:form:upload_file",
                    kwargs={"slug": view.slug},
                ),
                data={"file": file},
                format="multipart",
            )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"

    response = api_client.post(
        reverse("api:database:views:public_auth", kwargs={"slug": view.slug}),
        {"password": password},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    public_view_token = response_json.get("access_token", None)
    assert public_view_token is not None

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    with patch("baserow.core.storage.get_default_storage", new=storage):
        with freeze_time("2020-01-01 12:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            response = api_client.post(
                reverse(
                    "api:database:views:form:upload_file",
                    kwargs={"slug": view.slug},
                ),
                data={"file": file},
                format="multipart",
                HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
            )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_patch_multiple_form_view_field_options_conditions_update(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)

    form_view = data_fixture.create_form_view(table=table)
    text_field_2_field_options = FormViewFieldOptions.objects.get(
        form_view=form_view, field=text_field_2
    )

    condition = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_2_field_options, field=text_field
    )

    form_view_2 = data_fixture.create_form_view(table=table)
    text_field_2_field_options_2 = FormViewFieldOptions.objects.get(
        form_view=form_view_2, field=text_field_2
    )
    condition_2 = data_fixture.create_form_view_field_options_condition(
        field_option=text_field_2_field_options_2, field=text_field
    )

    assert FormViewFieldOptions.objects.count() == 4
    assert FormViewFieldOptionsCondition.objects.count() == 2
    assert list(
        FormViewFieldOptionsCondition.objects.order_by("id").values(
            "field_option_id", "field_id", "type"
        )
    ) == [
        {
            "field_option_id": text_field_2_field_options.id,
            "field_id": text_field.id,
            "type": "equal",
        },
        {
            "field_option_id": text_field_2_field_options_2.id,
            "field_id": text_field.id,
            "type": "equal",
        },
    ]

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(text_field_2.id): {
                    "show_when_matching_conditions": True,
                    "condition_groups": [],
                    "conditions": [
                        {
                            "id": condition.id,
                            "field": text_field.id,
                            "type": "not_equal",
                            "value": "test",
                            "group": None,
                        }
                    ],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    assert FormViewFieldOptionsCondition.objects.count() == 2, list(
        FormViewFieldOptionsCondition.objects.values()
    )

    assert list(
        FormViewFieldOptionsCondition.objects.order_by("id").values(
            "field_option_id", "field_id", "type"
        )
    ) == [
        {
            "field_option_id": text_field_2_field_options.id,
            "field_id": text_field.id,
            "type": "not_equal",
        },
        {
            "field_option_id": text_field_2_field_options_2.id,
            "field_id": text_field.id,
            "type": "equal",
        },
    ]


@pytest.mark.django_db
def test_get_select_options_in_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(
        field=single_select_field, value="Option 1"
    )
    option_2 = data_fixture.create_select_option(
        field=single_select_field, value="Option 2"
    )
    option_3 = data_fixture.create_select_option(
        field=single_select_field, value="Option 3"
    )

    form_view = data_fixture.create_form_view(table=table)
    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    # Make one request to allow the system to cache things.
    api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    with CaptureQueriesContext(connection) as captured_1:
        response = api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.json() == {
        "field_options": {
            str(single_select_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "conditions": [],
                "condition_groups": [],
                "field_component": "default",
                "include_all_select_options": True,
                "allowed_select_options": [],
            }
        }
    }

    field_options = FormViewFieldOptions.objects.all().first()
    field_options.include_all_select_options = False
    field_options.allowed_select_options.set([option_1.id, option_2.id])
    field_options.save()

    with CaptureQueriesContext(connection) as captured_2:
        response = api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.json() == {
        "field_options": {
            str(single_select_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "conditions": [],
                "condition_groups": [],
                "field_component": "default",
                "include_all_select_options": False,
                "allowed_select_options": [option_1.id, option_2.id],
            }
        }
    }
    assert len(captured_1) == len(captured_2)


@pytest.mark.django_db
def test_patch_select_options_in_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(
        field=single_select_field, value="Option 1"
    )
    option_2 = data_fixture.create_select_option(
        field=single_select_field, value="Option 2"
    )
    option_3 = data_fixture.create_select_option(
        field=single_select_field, value="Option 3"
    )

    form_view = data_fixture.create_form_view(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(single_select_field.id): {
                    "include_all_select_options": False,
                    "allowed_select_options": [option_1.id, option_2.id],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "field_options": {
            str(single_select_field.id): {
                "name": "",
                "description": "",
                "enabled": False,
                "required": True,
                "show_when_matching_conditions": False,
                "condition_type": "AND",
                "order": 32767,
                "conditions": [],
                "condition_groups": [],
                "field_component": "default",
                "include_all_select_options": False,
                "allowed_select_options": [option_1.id, option_2.id],
            }
        }
    }

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(single_select_field.id): {
                    "allowed_select_options": [option_2.id, option_3.id],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["field_options"][str(single_select_field.id)][
        "allowed_select_options"
    ] == [option_2.id, option_3.id]


@pytest.mark.django_db
def test_patch_select_options_in_field_options_num_queries(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(
        field=single_select_field, value="Option 1"
    )
    option_2 = data_fixture.create_select_option(
        field=single_select_field, value="Option 2"
    )
    single_select_field_2 = data_fixture.create_single_select_field(table=table)
    option_3 = data_fixture.create_select_option(
        field=single_select_field_2, value="Option 1"
    )
    option_4 = data_fixture.create_select_option(
        field=single_select_field_2, value="Option 2"
    )

    form_view = data_fixture.create_form_view(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    # Make one request to allow the system to cache things.
    api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    with CaptureQueriesContext(connection) as captured_1:
        response = api_client.patch(
            url,
            {
                "field_options": {
                    str(single_select_field.id): {
                        "allowed_select_options": [option_1.id],
                    }
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    with CaptureQueriesContext(connection) as captured_2:
        response = api_client.patch(
            url,
            {
                "field_options": {
                    str(single_select_field.id): {
                        "allowed_select_options": [option_1.id, option_2.id],
                    },
                    str(single_select_field_2.id): {
                        "allowed_select_options": [option_3.id, option_4.id],
                    },
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    assert len(captured_1) == len(captured_2)


@pytest.mark.django_db
def test_prevent_patch_select_options_in_field_options_of_unrelated_field(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(value="Option 1")

    form_view = data_fixture.create_form_view(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(single_select_field.id): {
                    "include_all_select_options": False,
                    "allowed_select_options": [option_1.id],
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD"


@pytest.mark.django_db
def test_submit_empty_form_view_for_interesting_test_table(api_client, data_fixture):
    table, user, row, _, context = setup_interesting_test_table(data_fixture)
    token = data_fixture.generate_token(user)
    form = data_fixture.create_form_view(
        table=table,
        submit_action_message="Test",
        submit_action_redirect_url="https://baserow.io",
    )

    FormViewFieldOptions.objects.filter(form_view=form).update(
        enabled=True, required=False
    )

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json["submit_action"] == "MESSAGE"

    # enabling and requiring one field at the time, the form should fail with a 400 if
    # the value is not provided, or success with a 200 if it is provided
    for field_option in FormViewFieldOptions.objects.filter(form_view=form):
        FormViewFieldOptions.objects.filter(form_view=form).update(
            enabled=False, required=False
        )

        field_option.enabled = True
        field_option.required = True
        field_option.save(update_fields=["enabled", "required"])

        response = api_client.post(
            url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

        field = field_option.field
        field_type = field.get_type()
        row_values = {
            field.db_column: field_type.serialize_to_input_value(
                field, getattr(row, field.db_column)
            )
        }
        response = api_client.post(
            url,
            row_values,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK, response.json()
        response_json = response.json()
        assert response_json["submit_action"] == "MESSAGE"

    # Now make all the fields required
    FormViewFieldOptions.objects.filter(form_view=form).update(
        enabled=True, required=True
    )

    row_values = {}
    for field_option in FormViewFieldOptions.objects.filter(form_view=form):
        field = field_option.field
        field_type = field.get_type()
        row_values[field.db_column] = field_type.serialize_to_input_value(
            field, getattr(row, field.db_column)
        )

    response = api_client.post(
        url,
        row_values,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json["submit_action"] == "MESSAGE"


@pytest.mark.django_db
def test_user_can_update_form_to_receive_notification(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(users=[user_1, user_2])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user_1, database=database)
    form = data_fixture.create_form_view(table=table, public=True)

    url = reverse("api:database:views:item", kwargs={"view_id": form.id})

    # users_to_notify cannot be set directly
    api_client.patch(
        url,
        {"users_to_notify_on_submit": [user_1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert form.users_to_notify_on_submit.count() == 0

    # The only way is via receive_notification_on_submit for the requesting user
    response = api_client.patch(
        url,
        {"receive_notification_on_submit": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["receive_notification_on_submit"] is True
    assert form.users_to_notify_on_submit.count() == 1

    response = api_client.get(
        reverse("api:database:tables:item", kwargs={"table_id": form.table_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK

    # another user sees the notification setting as false
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token_2}")
    assert response.status_code == HTTP_200_OK
    assert response.json()["receive_notification_on_submit"] is False


@pytest.mark.django_db()
def test_loading_form_views_does_not_increase_the_number_of_queries(
    api_client, data_fixture, bypass_check_permissions
):
    user, token = data_fixture.create_user_and_token()

    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    data_fixture.create_form_view(table=table, public=True)

    with CaptureQueriesContext(connection) as captured_1:
        api_client.get(
            reverse("api:database:views:list", kwargs={"table_id": table.id}),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view(table=table, public=True)

    with CaptureQueriesContext(connection) as captured_2:
        api_client.get(
            reverse("api:database:views:list", kwargs={"table_id": table.id}),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert len(captured_1) == len(captured_2)


@pytest.mark.django_db
def test_can_use_link_row_field_to_table_with_formula_as_primary_key_in_form_view(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    linked_table = data_fixture.create_database_table(database=database)
    data_fixture.create_formula_field(
        table=linked_table, primary=True, name="formula_field", formula="row_id()"
    )
    linked_row = RowHandler().force_create_row(user, linked_table, {})

    table = data_fixture.create_database_table(database=database)
    text_field = data_fixture.create_text_field(table=table, primary=True)
    linked_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )

    form_view = data_fixture.create_form_view(table=table, public=True)
    url = reverse("api:database:views:field_options", kwargs={"view_id": form_view.id})
    response = api_client.patch(
        url,
        {
            "field_options": {
                str(linked_row_field.id): {"enabled": True, "required": True}
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    url = reverse("api:database:views:form:submit", kwargs={"slug": form_view.slug})
    response = api_client.post(
        url,
        {
            text_field.db_column: "Test",
            linked_row_field.db_column: [linked_row.id],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["row_id"] == 1
    assert response.json()["submit_action"] == "MESSAGE"
    assert response.json()["submit_action_message"] == ""
