import datetime

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
)

from baserow.contrib.database.fields.field_types import DurationFieldType
from baserow.contrib.database.views.models import ViewDefaultValue


@pytest.mark.django_db
def test_get_default_values_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, _ = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user_2)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_patch_default_values_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, _ = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user_2)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_patch_default_values_remove_values(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    long_text_field = data_fixture.create_long_text_field(table=table, name="LongText")
    url_field = data_fixture.create_url_field(table=table, name="URL")
    email_field = data_fixture.create_email_field(table=table, name="Email")
    phone_field = data_fixture.create_phone_number_field(table=table, name="Phone")
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )
    rating_field = data_fixture.create_rating_field(table=table, name="Rating")
    duration_field = data_fixture.create_duration_field(
        table=table, name="Duration", duration_format="h:mm"
    )
    single_select_field = data_fixture.create_single_select_field(
        table=table, name="SingleSelect"
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="Option A", color="blue"
    )
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="MultipleSelect"
    )
    option_multi_a = data_fixture.create_select_option(
        field=multiple_select_field, value="Option A", color="blue"
    )
    option_multi_b = data_fixture.create_select_option(
        field=multiple_select_field, value="Option B", color="red"
    )
    linked_table = data_fixture.create_database_table(user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table, name="LinkRow", link_row_table=linked_table
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    api_client.patch(
        url,
        {
            text_field.id: {"enabled": True, "value": "Multi Test"},
            long_text_field.id: {
                "enabled": True,
                "value": "This is a long text value\nwith multiple lines.",
            },
            url_field.id: {
                "enabled": True,
                "value": "https://example.com",
            },
            email_field.id: {
                "enabled": True,
                "value": "test@example.com",
            },
            phone_field.id: {
                "enabled": True,
                "value": "+1234567890",
            },
            boolean_field.id: {"enabled": True, "value": True},
            number_field.id: {"enabled": True, "value": "999.99"},
            rating_field.id: {"enabled": True, "value": 3},
            duration_field.id: {
                "enabled": True,
                "value": 3600,  # 1 hour in seconds
            },
            single_select_field.id: {
                "enabled": True,
                "value": option_a.id,
            },
            multiple_select_field.id: {
                "enabled": True,
                "value": [option_multi_a.id, option_multi_b.id],
            },
            link_row_field.id: {
                "enabled": True,
                "value": [1, 2, 3],
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert ViewDefaultValue.objects.filter(view=grid).count() == 12

    # Now remove all default values
    response = api_client.patch(
        url,
        {
            text_field.id: {"enabled": False},
            long_text_field.id: {"enabled": False},
            url_field.id: {"enabled": False},
            email_field.id: {"enabled": False},
            phone_field.id: {"enabled": False},
            boolean_field.id: {"enabled": False},
            number_field.id: {"enabled": False},
            rating_field.id: {"enabled": False},
            duration_field.id: {
                "enabled": False,
            },
            single_select_field.id: {
                "enabled": False,
            },
            multiple_select_field.id: {
                "enabled": False,
            },
            link_row_field.id: {
                "enabled": False,
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json == {}

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json == {}

    assert ViewDefaultValue.objects.filter(view=grid).count() == 0


@pytest.mark.django_db
def test_get_default_values(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    long_text_field = data_fixture.create_long_text_field(table=table, name="LongText")
    url_field = data_fixture.create_url_field(table=table, name="URL")
    email_field = data_fixture.create_email_field(table=table, name="Email")
    phone_field = data_fixture.create_phone_number_field(table=table, name="Phone")
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )
    rating_field = data_fixture.create_rating_field(table=table, name="Rating")
    duration_field = data_fixture.create_duration_field(
        table=table, name="Duration", duration_format="h:mm"
    )
    single_select_field = data_fixture.create_single_select_field(
        table=table, name="SingleSelect"
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="Option A", color="blue"
    )
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="MultipleSelect"
    )
    option_multi_a = data_fixture.create_select_option(
        field=multiple_select_field, value="Option A", color="blue"
    )
    option_multi_b = data_fixture.create_select_option(
        field=multiple_select_field, value="Option B", color="red"
    )
    linked_table = data_fixture.create_database_table(user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table, name="LinkRow", link_row_table=linked_table
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    api_client.patch(
        url,
        {
            text_field.id: {"enabled": True, "value": "Multi Test"},
            long_text_field.id: {
                "enabled": True,
                "value": "This is a long text value\nwith multiple lines.",
            },
            url_field.id: {
                "enabled": True,
                "value": "https://example.com",
            },
            email_field.id: {
                "enabled": True,
                "value": "test@example.com",
            },
            phone_field.id: {
                "enabled": True,
                "value": "+1234567890",
            },
            boolean_field.id: {"enabled": True, "value": True},
            number_field.id: {"enabled": True, "value": "999.99"},
            rating_field.id: {"enabled": True, "value": 3},
            duration_field.id: {
                "enabled": True,
                "value": 3600,  # 1 hour in seconds
            },
            single_select_field.id: {
                "enabled": True,
                "value": option_a.id,
            },
            multiple_select_field.id: {
                "enabled": True,
                "value": [option_multi_a.id, option_multi_b.id],
            },
            link_row_field.id: {
                "enabled": True,
                "value": [1, 2, 3],
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json == {
        f"{text_field.id}": {"field_type": "text", "value": "Multi Test"},
        f"{single_select_field.id}": {
            "field_type": "single_select",
            "value": option_a.id,
        },
        f"{multiple_select_field.id}": {
            "field_type": "multiple_select",
            "value": [option_multi_a.id, option_multi_b.id],
        },
        # FIXME: link row ids
        f"{link_row_field.id}": {"field_type": "link_row", "value": [1, 2, 3]},
        f"{long_text_field.id}": {
            "field_type": "long_text",
            "value": "This is a long text value\nwith multiple lines.",
        },
        f"{url_field.id}": {"field_type": "url", "value": "https://example.com"},
        f"{email_field.id}": {"field_type": "email", "value": "test@example.com"},
        f"{phone_field.id}": {"field_type": "phone_number", "value": "+1234567890"},
        f"{boolean_field.id}": {"field_type": "boolean", "value": True},
        f"{number_field.id}": {"field_type": "number", "value": "999.99"},
        f"{rating_field.id}": {"field_type": "rating", "value": 3},
        f"{duration_field.id}": {"field_type": "duration", "value": 3600},
    }


@pytest.mark.django_db
def test_patch_default_values_invalid_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(table=table, name="File")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {file_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(file_field.id)] == "Unsupported field type"


@pytest.mark.django_db
def test_patch_default_values_field_not_in_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table_2, name="Text")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": "Test"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json == {
        "detail": "The field is not related to the provided view.",
        "error": "ERROR_UNRELATED_FIELD",
    }


@pytest.mark.django_db
def test_patch_default_values_text_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": "Hello World"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(text_field.id)] == {
        "field_type": "text",
        "value": "Hello World",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=text_field)
    assert default_value.field_type == "text"
    assert default_value.value == "Hello World"


@pytest.mark.django_db
def test_patch_default_values_text_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": [1, 2, 3]}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(text_field.id)] == ["Not a valid string."]


@pytest.mark.django_db
def test_patch_default_values_text_field_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": ""}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(text_field.id)] == {
        "field_type": "text",
        "value": "",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=text_field)
    assert default_value.field_type == "text"
    assert default_value.value == ""


@pytest.mark.django_db
def test_patch_default_values_text_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=text_field)
    assert default_value.field_type == "text"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(text_field.id)] == {
        "field_type": "text",
        "value": None,
    }


@pytest.mark.django_db
def test_patch_default_values_long_text_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(table=table, name="LongText")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            long_text_field.id: {
                "enabled": True,
                "value": "This is a long text value\nwith multiple lines.",
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(long_text_field.id)] == {
        "field_type": "long_text",
        "value": "This is a long text value\nwith multiple lines.",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=long_text_field)
    assert default_value.field_type == "long_text"
    assert default_value.value == "This is a long text value\nwith multiple lines."


@pytest.mark.django_db
def test_patch_default_values_long_text_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(table=table, name="LongText")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {long_text_field.id: {"enabled": True, "value": [1, 2, 3]}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(long_text_field.id)] == ["Not a valid string."]


@pytest.mark.django_db
def test_patch_default_values_long_text_field_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(table=table, name="LongText")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {long_text_field.id: {"enabled": True, "value": ""}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(long_text_field.id)] == {
        "field_type": "long_text",
        "value": "",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=long_text_field)
    assert default_value.field_type == "long_text"
    assert default_value.value == ""


@pytest.mark.django_db
def test_patch_default_values_long_text_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(table=table, name="LongText")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {long_text_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=long_text_field)
    assert default_value.field_type == "long_text"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(long_text_field.id)] == {
        "field_type": "long_text",
        "value": None,
    }


@pytest.mark.django_db
def test_patch_default_values_url_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    url_field = data_fixture.create_url_field(table=table, name="URL")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            url_field.id: {
                "enabled": True,
                "value": "https://example.com",
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(url_field.id)] == {
        "field_type": "url",
        "value": "https://example.com",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=url_field)
    assert default_value.field_type == "url"
    assert default_value.value == "https://example.com"


@pytest.mark.django_db
def test_patch_default_values_url_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    url_field = data_fixture.create_url_field(table=table, name="URL")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {url_field.id: {"enabled": True, "value": "not_a_url"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(url_field.id)] == ["Enter a valid value."]


@pytest.mark.django_db
def test_patch_default_values_url_field_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    url_field = data_fixture.create_url_field(table=table, name="URL")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {url_field.id: {"enabled": True, "value": ""}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(url_field.id)] == {
        "field_type": "url",
        "value": "",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=url_field)
    assert default_value.field_type == "url"
    assert default_value.value == ""


@pytest.mark.django_db
def test_patch_default_values_url_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    url_field = data_fixture.create_url_field(table=table, name="URL")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {url_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=url_field)
    assert default_value.field_type == "url"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(url_field.id)] == {
        "field_type": "url",
        "value": None,
    }


@pytest.mark.django_db
def test_patch_default_values_email_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    email_field = data_fixture.create_email_field(table=table, name="Email")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            email_field.id: {
                "enabled": True,
                "value": "test@example.com",
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(email_field.id)] == {
        "field_type": "email",
        "value": "test@example.com",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=email_field)
    assert default_value.field_type == "email"
    assert default_value.value == "test@example.com"


@pytest.mark.django_db
def test_patch_default_values_email_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    email_field = data_fixture.create_email_field(table=table, name="Email")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {email_field.id: {"enabled": True, "value": "not_an_email"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(email_field.id)] == ["Enter a valid value."]


@pytest.mark.django_db
def test_patch_default_values_email_field_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    email_field = data_fixture.create_email_field(table=table, name="Email")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {email_field.id: {"enabled": True, "value": ""}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(email_field.id)] == {
        "field_type": "email",
        "value": "",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=email_field)
    assert default_value.field_type == "email"
    assert default_value.value == ""


@pytest.mark.django_db
def test_patch_default_values_email_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    email_field = data_fixture.create_email_field(table=table, name="Email")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {email_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=email_field)
    assert default_value.field_type == "email"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(email_field.id)] == {
        "field_type": "email",
        "value": None,
    }


@pytest.mark.django_db
def test_patch_default_values_phone_number_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    phone_field = data_fixture.create_phone_number_field(table=table, name="Phone")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            phone_field.id: {
                "enabled": True,
                "value": "+1234567890",
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(phone_field.id)] == {
        "field_type": "phone_number",
        "value": "+1234567890",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=phone_field)
    assert default_value.field_type == "phone_number"
    assert default_value.value == "+1234567890"


@pytest.mark.django_db
def test_patch_default_values_phone_number_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    phone_field = data_fixture.create_phone_number_field(table=table, name="Phone")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {phone_field.id: {"enabled": True, "value": "abc!"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(phone_field.id)] == ["Enter a valid value."]


@pytest.mark.django_db
def test_patch_default_values_phone_number_field_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    phone_field = data_fixture.create_phone_number_field(table=table, name="Phone")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {phone_field.id: {"enabled": True, "value": ""}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(phone_field.id)] == {
        "field_type": "phone_number",
        "value": "",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=phone_field)
    assert default_value.field_type == "phone_number"
    assert default_value.value == ""


@pytest.mark.django_db
def test_patch_default_values_phone_number_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    phone_field = data_fixture.create_phone_number_field(table=table, name="Phone")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {phone_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=phone_field)
    assert default_value.field_type == "phone_number"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(phone_field.id)] == {
        "field_type": "phone_number",
        "value": None,
    }


@pytest.mark.django_db
def test_patch_default_values_boolean_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {boolean_field.id: {"enabled": True, "value": True}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(boolean_field.id)] == {
        "field_type": "boolean",
        "value": True,
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=boolean_field)
    assert default_value.field_type == "boolean"
    assert default_value.value is True


@pytest.mark.django_db
def test_patch_default_values_boolean_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {boolean_field.id: {"enabled": True, "value": "invalid"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(boolean_field.id)] == ["Must be a valid boolean."]


@pytest.mark.django_db
def test_patch_default_values_boolean_field_false(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {boolean_field.id: {"enabled": True, "value": False}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(boolean_field.id)] == {
        "field_type": "boolean",
        "value": False,
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=boolean_field)
    assert default_value.field_type == "boolean"
    assert default_value.value is False


@pytest.mark.django_db
def test_patch_default_values_boolean_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {boolean_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(boolean_field.id)] == ["This field may not be null."]


@pytest.mark.django_db
def test_patch_default_values_number_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {number_field.id: {"enabled": True, "value": "123.45"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(number_field.id)] == {
        "field_type": "number",
        "value": "123.45",
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=number_field)
    assert default_value.field_type == "number"
    assert default_value.value == "123.45"


@pytest.mark.django_db
def test_patch_default_values_number_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {number_field.id: {"enabled": True, "value": "not_a_number"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(number_field.id)] == ["A valid number is required."]


@pytest.mark.django_db
def test_patch_default_values_number_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {number_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=number_field)
    assert default_value.field_type == "number"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(number_field.id)] == {
        "field_type": "number",
        "value": "",  # FIXME:
    }


@pytest.mark.django_db
def test_patch_default_values_rating_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    rating_field = data_fixture.create_rating_field(table=table, name="Rating")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {rating_field.id: {"enabled": True, "value": 3}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(rating_field.id)] == {
        "field_type": "rating",
        "value": 3,
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=rating_field)
    assert default_value.field_type == "rating"
    assert default_value.value == 3


@pytest.mark.django_db
def test_patch_default_values_rating_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    rating_field = data_fixture.create_rating_field(table=table, name="Rating")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {rating_field.id: {"enabled": True, "value": 6}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(rating_field.id)] == [
        "Ensure this value is less than or equal to 5."
    ]


@pytest.mark.django_db
def test_patch_default_values_rating_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    rating_field = data_fixture.create_rating_field(table=table, name="Rating")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {rating_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(rating_field.id)] == ["This field may not be null."]


@pytest.mark.django_db
def test_patch_default_values_duration_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    duration_field = data_fixture.create_duration_field(
        table=table, name="Duration", duration_format="h:mm"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            duration_field.id: {
                "enabled": True,
                "value": 3600,  # 1 hour in seconds
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(duration_field.id)] == {
        "field_type": "duration",
        "value": 3600,
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=duration_field)
    assert default_value.field_type == "duration"

    value_from_json = DurationFieldType().deserialize_json_value(default_value.value)
    assert value_from_json == datetime.timedelta(seconds=3600)


@pytest.mark.django_db
def test_patch_default_values_duration_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    duration_field = data_fixture.create_duration_field(
        table=table, name="Duration", duration_format="h:mm"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {duration_field.id: {"enabled": True, "value": "not_a_duration"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(duration_field.id)] == [
        "The value not_a_duration is not a valid duration."
    ]


@pytest.mark.django_db
def test_patch_default_values_duration_field_zero(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    duration_field = data_fixture.create_duration_field(
        table=table, name="Duration", duration_format="h:mm"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {duration_field.id: {"enabled": True, "value": 0}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(duration_field.id)] == {
        "field_type": "duration",
        "value": 0,
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=duration_field)
    assert default_value.field_type == "duration"

    value_from_json = DurationFieldType().deserialize_json_value(default_value.value)
    assert value_from_json == datetime.timedelta(seconds=0)


@pytest.mark.django_db
def test_patch_default_values_duration_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    duration_field = data_fixture.create_duration_field(
        table=table, name="Duration", duration_format="h:mm"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {duration_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=duration_field)
    assert default_value.field_type == "duration"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(duration_field.id)] == {
        "field_type": "duration",
        "value": None,
    }


@pytest.mark.django_db
def test_patch_default_values_single_select_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(
        table=table, name="SingleSelect"
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="Option A", color="blue"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            single_select_field.id: {
                "enabled": True,
                "value": option_a.id,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(single_select_field.id)] == {
        "field_type": "single_select",
        "value": option_a.id,
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=single_select_field)
    assert default_value.field_type == "single_select"
    assert default_value.value == option_a.id


@pytest.mark.django_db
def test_patch_default_values_single_select_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(
        table=table, name="SingleSelect"
    )
    data_fixture.create_select_option(
        field=single_select_field, value="Option A", color="blue"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {single_select_field.id: {"enabled": True, "value": [1, 2]}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(single_select_field.id)] == [
        "The provided value should be a valid integer or string"
    ]


@pytest.mark.django_db
def test_patch_default_values_single_select_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(
        table=table, name="SingleSelect"
    )
    data_fixture.create_select_option(
        field=single_select_field, value="Option A", color="blue"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {single_select_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    default_value = ViewDefaultValue.objects.get(view=grid, field=single_select_field)
    assert default_value.field_type == "single_select"
    assert default_value.value is None

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(single_select_field.id)] == {
        "field_type": "single_select",
        "value": None,
    }


@pytest.mark.django_db
def test_patch_default_values_multiple_select_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="MultipleSelect"
    )
    option_a = data_fixture.create_select_option(
        field=multiple_select_field, value="Option A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=multiple_select_field, value="Option B", color="red"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            multiple_select_field.id: {
                "enabled": True,
                "value": [option_a.id, option_b.id],
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(multiple_select_field.id)] == {
        "field_type": "multiple_select",
        "value": [option_a.id, option_b.id],
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=multiple_select_field)
    assert default_value.field_type == "multiple_select"
    assert default_value.value == [option_a.id, option_b.id]


@pytest.mark.django_db
def test_patch_default_values_multiple_select_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="MultipleSelect"
    )
    data_fixture.create_select_option(
        field=multiple_select_field, value="Option A", color="blue"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {multiple_select_field.id: {"enabled": True, "value": {"key": "value"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(multiple_select_field.id)] == [
        'Expected a list of items but got type "dict".'
    ]


@pytest.mark.django_db
def test_patch_default_values_multiple_select_field_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="MultipleSelect"
    )
    data_fixture.create_select_option(
        field=multiple_select_field, value="Option A", color="blue"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {multiple_select_field.id: {"enabled": True, "value": []}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(multiple_select_field.id)] == {
        "field_type": "multiple_select",
        "value": [],
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=multiple_select_field)
    assert default_value.field_type == "multiple_select"
    assert default_value.value == []


@pytest.mark.django_db
def test_patch_default_values_multiple_select_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="MultipleSelect"
    )
    data_fixture.create_select_option(
        field=multiple_select_field, value="Option A", color="blue"
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {multiple_select_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(multiple_select_field.id)] == [
        "This field may not be null."
    ]


@pytest.mark.django_db
def test_patch_default_values_link_row_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table, name="LinkRow", link_row_table=linked_table
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            link_row_field.id: {
                "enabled": True,
                "value": [1, 2, 3],
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(link_row_field.id)] == {
        "field_type": "link_row",
        "value": [1, 2, 3],
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=link_row_field)
    assert default_value.field_type == "link_row"
    assert default_value.value == [1, 2, 3]


@pytest.mark.django_db
def test_patch_default_values_link_row_field_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table, name="LinkRow", link_row_table=linked_table
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {link_row_field.id: {"enabled": True, "value": {"key": "value"}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(link_row_field.id)] == [
        "This provided value must be a list, an integer or a string."
    ]


@pytest.mark.django_db
def test_patch_default_values_link_row_field_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table, name="LinkRow", link_row_table=linked_table
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {link_row_field.id: {"enabled": True, "value": []}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(link_row_field.id)] == {
        "field_type": "link_row",
        "value": [],
    }

    default_value = ViewDefaultValue.objects.get(view=grid, field=link_row_field)
    assert default_value.field_type == "link_row"
    assert default_value.value == []


@pytest.mark.django_db
def test_patch_default_values_link_row_field_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table, name="LinkRow", link_row_table=linked_table
    )
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {link_row_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()
    response_json = response.json()
    assert response_json[str(link_row_field.id)] == ["This field may not be null."]


@pytest.mark.django_db
def test_patch_default_values_multiple_fields(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Text")
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    grid = data_fixture.create_grid_view(table=table)

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {
            text_field.id: {"enabled": True, "value": "Multi Test"},
            number_field.id: {"enabled": True, "value": "999.99"},
            boolean_field.id: {"enabled": True, "value": False},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json[str(text_field.id)] == {
        "field_type": "text",
        "value": "Multi Test",
    }
    assert response_json[str(number_field.id)] == {
        "field_type": "number",
        "value": "999.99",
    }
    assert response_json[str(boolean_field.id)] == {
        "field_type": "boolean",
        "value": False,
    }

    default_value_text = ViewDefaultValue.objects.get(view=grid, field=text_field)
    assert default_value_text.field_type == "text"
    assert default_value_text.value == "Multi Test"

    default_value_number = ViewDefaultValue.objects.get(view=grid, field=number_field)
    assert default_value_number.field_type == "number"
    assert default_value_number.value == "999.99"

    default_value_boolean = ViewDefaultValue.objects.get(view=grid, field=boolean_field)
    assert default_value_boolean.field_type == "boolean"
    assert default_value_boolean.value is False
