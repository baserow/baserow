import json

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from baserow_premium.views.models import KanbanView, KanbanViewFieldOptions
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.action.scopes import ViewActionScopeType
from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.actions import UpdateViewActionType
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_without_valid_premium_license(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=False
    )
    kanban = premium_data_fixture.create_kanban_view(user=user)
    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"

    # The kanban view should work if it's a template.
    premium_data_fixture.create_template(workspace=kanban.table.database.workspace)
    kanban.table.database.workspace.has_template.cache_clear()
    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_without_valid_premium_license_for_workspace(
    api_client, premium_data_fixture, alternative_per_workspace_license_service
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    kanban = premium_data_fixture.create_kanban_view(user=user)

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [kanban.table.database.workspace.id]
    )
    premium_data_fixture.create_template(workspace=kanban.table.database.workspace)
    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_rows_invalid_parameters(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    kanban = premium_data_fixture.create_kanban_view(
        user=user, single_select_field=None
    )
    kanban_2 = premium_data_fixture.create_kanban_view()

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": 0})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_KANBAN_DOES_NOT_EXIST"

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_2.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_KANBAN_VIEW_HAS_NO_SINGLE_SELECT_FIELD"


@pytest.mark.django_db
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
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?include=field_options", **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert len(response_json["field_options"]) == 2
    assert response_json["field_options"][str(text_field.id)]["hidden"] is True
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    assert response_json["field_options"][str(single_select_field.id)]["hidden"] is True
    assert response_json["field_options"][str(single_select_field.id)]["order"] == 32767


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_all_rows(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, primary=True)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="red"
    )
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )

    model = table.get_model()
    row_none = model.objects.create(
        **{
            f"field_{text_field.id}": "Row None",
            f"field_{single_select_field.id}_id": None,
        }
    )
    row_a1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row A1",
            f"field_{single_select_field.id}_id": option_a.id,
        }
    )
    row_a2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row A2",
            f"field_{single_select_field.id}_id": option_a.id,
        }
    )
    row_b1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row B1",
            f"field_{single_select_field.id}_id": option_b.id,
        }
    )
    row_b2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Row B2",
            f"field_{single_select_field.id}_id": option_b.id,
        }
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 3

    assert response_json["rows"]["null"]["count"] == 1
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0] == {
        "id": row_none.id,
        "order": "1.00000000000000000000",
        f"field_{text_field.id}": "Row None",
        f"field_{single_select_field.id}": None,
    }

    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 2
    assert response_json["rows"][str(option_a.id)]["results"][0] == {
        "id": row_a1.id,
        "order": "1.00000000000000000000",
        f"field_{text_field.id}": "Row A1",
        f"field_{single_select_field.id}": {
            "id": option_a.id,
            "value": "A",
            "color": "blue",
        },
    }
    assert response_json["rows"][str(option_a.id)]["results"][1] == {
        "id": row_a2.id,
        "order": "1.00000000000000000000",
        f"field_{text_field.id}": "Row A2",
        f"field_{single_select_field.id}": {
            "id": option_a.id,
            "value": "A",
            "color": "blue",
        },
    }

    assert response_json["rows"][str(option_b.id)]["count"] == 2
    assert len(response_json["rows"][str(option_b.id)]["results"]) == 2
    assert response_json["rows"][str(option_b.id)]["results"][0] == {
        "id": row_b1.id,
        "order": "1.00000000000000000000",
        f"field_{text_field.id}": "Row B1",
        f"field_{single_select_field.id}": {
            "id": option_b.id,
            "value": "B",
            "color": "red",
        },
    }
    assert response_json["rows"][str(option_b.id)]["results"][1] == {
        "id": row_b2.id,
        "order": "1.00000000000000000000",
        f"field_{text_field.id}": "Row B2",
        f"field_{single_select_field.id}": {
            "id": option_b.id,
            "value": "B",
            "color": "red",
        },
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_with_specific_select_options(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option={option_a.id}",
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json["rows"][str(option_a.id)]["count"] == 0
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 0

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option=null",
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json["rows"]["null"]["count"] == 0
    assert len(response_json["rows"]["null"]["results"]) == 0

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option={option_a.id}&select_option=null",
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 2
    assert response_json["rows"]["null"]["count"] == 0
    assert len(response_json["rows"]["null"]["results"]) == 0
    assert response_json["rows"][str(option_a.id)]["count"] == 0
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_all_rows_with_limit_and_offset(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )

    model = table.get_model()
    row_none1 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
        }
    )
    row_none2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
        }
    )
    row_a1 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
        }
    )
    row_a2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
        }
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?limit=1&offset=1", **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 2
    assert response_json["rows"]["null"]["count"] == 2
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == row_none2.id
    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 1
    assert response_json["rows"][str(option_a.id)]["results"][0]["id"] == row_a2.id

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option=null,1,1", **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json["rows"]["null"]["count"] == 2
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == row_none2.id

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option={option_a.id},1,1",
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 1
    assert response_json["rows"][str(option_a.id)]["results"][0]["id"] == row_a2.id

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option={option_a.id},1,1&select_option=null,2,0",
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 2
    assert response_json["rows"]["null"]["count"] == 2
    assert len(response_json["rows"]["null"]["results"]) == 2
    assert response_json["rows"]["null"]["results"][0]["id"] == row_none1.id
    assert response_json["rows"]["null"]["results"][1]["id"] == row_none2.id
    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 1
    assert response_json["rows"][str(option_a.id)]["results"][0]["id"] == row_a2.id

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option={option_a.id},2,0&select_option=null&limit=1&offset=1",
        **{"HTTP_AUTHORIZATION": f"JWT" f" {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 2
    assert response_json["rows"]["null"]["count"] == 2
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == row_none2.id
    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 2
    assert response_json["rows"][str(option_a.id)]["results"][0]["id"] == row_a1.id
    assert response_json["rows"][str(option_a.id)]["results"][1]["id"] == row_a2.id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_kanban_filter(api_client, data_fixture, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    number_field = data_fixture.create_number_field(
        table=table, name="FilterNumberField"
    )
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )
    threshold = 20
    lower_than_threshold = threshold - 1
    higher_than_threshold = threshold + 1
    ViewHandler().create_filter(
        user=user,
        view=kanban,
        type_name="lower_than",
        value=threshold,
        field=number_field,
    )
    model = table.get_model()
    row_null_lower = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_null_lower2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_null_higher = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": higher_than_threshold,
        }
    )
    row_a_lower = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_a_lower2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_a_higher = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": higher_than_threshold,
        }
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(f"{url}", **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 2
    assert response_json["rows"]["null"]["count"] == 2
    assert len(response_json["rows"]["null"]["results"]) == 2
    assert response_json["rows"]["null"]["results"][0]["id"] == row_null_lower.id
    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 2
    assert response_json["rows"][str(option_a.id)]["results"][0]["id"] == row_a_lower.id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_kanban_filter_limit_offset(api_client, data_fixture, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    number_field = data_fixture.create_number_field(
        table=table, name="FilterNumberField"
    )
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )
    threshold = 20
    lower_than_threshold = threshold - 1
    higher_than_threshold = threshold + 1
    ViewHandler().create_filter(
        user=user,
        view=kanban,
        type_name="lower_than",
        value=threshold,
        field=number_field,
    )
    model = table.get_model()
    row_null_lower = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_null_lower2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_null_higher = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": higher_than_threshold,
        }
    )
    row_a_lower = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_a_lower2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_a_higher = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": higher_than_threshold,
        }
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?filter=1&offset=1", **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 2
    assert response_json["rows"]["null"]["count"] == 2
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == row_null_lower2.id
    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 1
    assert (
        response_json["rows"][str(option_a.id)]["results"][0]["id"] == row_a_lower2.id
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_kanban_filter_specific_options_limit_offset(
    api_client, data_fixture, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="green"
    )
    number_field = data_fixture.create_number_field(
        table=table, name="FilterNumberField"
    )
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )
    threshold = 20
    lower_than_threshold = threshold - 1
    higher_than_threshold = threshold + 1
    ViewHandler().create_filter(
        user=user,
        view=kanban,
        type_name="lower_than",
        value=threshold,
        field=number_field,
    )
    model = table.get_model()
    row_null_lower = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_null_lower2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_null_higher = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": None,
            f"field_{number_field.id}": higher_than_threshold,
        }
    )
    row_a_lower = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_a_lower2 = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )
    row_a_higher = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_a.id,
            f"field_{number_field.id}": higher_than_threshold,
        }
    )
    row_b_lower = model.objects.create(
        **{
            f"field_{single_select_field.id}_id": option_b.id,
            f"field_{number_field.id}": lower_than_threshold,
        }
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option=null,1,1&select_option={option_a.id},2,0",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]) == 2
    assert response_json["rows"]["null"]["count"] == 2
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == row_null_lower2.id
    assert response_json["rows"][str(option_a.id)]["count"] == 2
    assert len(response_json["rows"][str(option_a.id)]["results"]) == 2
    assert response_json["rows"][str(option_a.id)]["results"][0]["id"] == row_a_lower.id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_kanban_rows_adhoc_filtering_query_param_filter(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="normal")
    # hidden field should behave the same as normal one
    text_field_hidden = premium_data_fixture.create_text_field(
        table=table, name="hidden"
    )
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="green"
    )
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, single_select_field=single_select_field
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, text_field, hidden=False
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, text_field_hidden, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"normal": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"normal": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    get_params = [f"filter__field_{text_field.id}__contains=a"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == first_row.id

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    get_params = [
        f"filter__field_{text_field.id}__contains=a",
        f"filter__field_{text_field.id}__contains=b",
        f"filter_type=OR",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 2

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    get_params = [f"filter__field_{text_field_hidden.id}__contains=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 1

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    get_params = [f"filter__field_{text_field.id}__random=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    get_params = [f"filter__field_{text_field.id}__higher_than=1"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
def test_list_kanban_rows_adhoc_filtering_invalid_advanced_filters(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="text_field")
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="green"
    )
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, text_field, hidden=False
    )

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})

    expected_errors = [
        (
            "invalid_json",
            {
                "error": "The provided filters are not valid JSON.",
                "code": "invalid_json",
            },
        ),
        (
            json.dumps({"filter_type": "invalid"}),
            {
                "filter_type": [
                    {
                        "error": '"invalid" is not a valid choice.',
                        "code": "invalid_choice",
                    }
                ]
            },
        ),
        (
            json.dumps(
                {"filter_type": "OR", "filters": "invalid", "groups": "invalid"}
            ),
            {
                "filters": [
                    {
                        "error": 'Expected a list of items but got type "str".',
                        "code": "not_a_list",
                    }
                ],
                "groups": {
                    "non_field_errors": [
                        {
                            "error": 'Expected a list of items but got type "str".',
                            "code": "not_a_list",
                        }
                    ],
                },
            },
        ),
    ]

    for filters, error_detail in expected_errors:
        get_params = [f"filters={filters}"]
        response = api_client.get(
            f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"
        assert response_json["detail"] == error_detail


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_kanban_rows_adhoc_filtering_advanced_filters_are_preferred_to_other_filter_query_params(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="text_field")
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="green"
    )
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, single_select_field=single_select_field
    )
    premium_data_fixture.create_kanban_view_field_option(kanban_view, text_field)

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }
    get_params = [
        "filters=" + json.dumps(advanced_filters),
        f"filter__field_{text_field.id}__equal=z",
        f"filter_type=AND",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_kanban_rows_adhoc_filtering_overrides_existing_filters(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="text_field")
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="green"
    )
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, single_select_field=single_select_field
    )
    # in usual scenario this filter would filtered out all rows
    equal_filter = premium_data_fixture.create_view_filter(
        view=kanban_view, field=text_field, type="equal", value="y"
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }

    get_params = [
        "filters=" + json.dumps(advanced_filters),
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_kanban_rows_adhoc_filtering_advanced_filters(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    # hidden fields should behave like normal ones
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    option_a = premium_data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select_field, value="B", color="green"
    )
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, single_select_field=single_select_field
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban_view.id})
    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "contains",
                "value": "a",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == first_row.id

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "OR",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "b",
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 2

    # groups can be arbitrarily nested
    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "",
                    },
                ],
                "groups": [
                    {
                        "filter_type": "OR",
                        "filters": [
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "a",
                            },
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "b",
                            },
                        ],
                    },
                ],
            },
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 2

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": hidden_field.id,
                "type": "contains",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["rows"]["null"]["results"]) == 1

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "random",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "higher_than",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"

    for filters in [
        "invalid_json",
        json.dumps({"filter_type": "invalid"}),
        json.dumps({"filter_type": "OR", "filters": "invalid"}),
    ]:
        get_params = [f"filters={filters}"]
        response = api_client.get(
            f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_all_invalid_select_option_parameter(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )

    url = reverse("api:database:views:kanban:list", kwargs={"view_id": kanban.id})
    response = api_client.get(
        f"{url}?select_option=null,a",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_SELECT_OPTION_PARAMETER"

    response = api_client.get(
        f"{url}?select_option=null,1,1&select_option=1,1,a",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_SELECT_OPTION_PARAMETER"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_patch_kanban_view_field_options(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": kanban.id})
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
    options = kanban.get_field_options()
    assert len(options) == 1
    assert options[0].field_id == text_field.id
    assert options[0].hidden is False
    assert options[0].order == 32767


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_kanban_view(api_client, data_fixture, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    single_select_field_2 = premium_data_fixture.create_single_select_field()
    cover_image_file_field = data_fixture.create_file_field(table=table)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "kanban",
            "filter_type": "OR",
            "filters_disabled": True,
            "single_select_field": single_select_field_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response_json["error"]
        == "ERROR_KANBAN_VIEW_FIELD_DOES_NOT_BELONG_TO_SAME_TABLE"
    )

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "kanban",
            "filter_type": "OR",
            "filters_disabled": True,
            "single_select_field": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 1"
    assert response_json["type"] == "kanban"
    assert response_json["filter_type"] == "OR"
    assert response_json["filters_disabled"] is True
    assert response_json["single_select_field"] is None

    kanban_view = KanbanView.objects.all().last()
    assert kanban_view.id == response_json["id"]
    assert kanban_view.single_select_field is None

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "kanban",
            "filter_type": "AND",
            "filters_disabled": False,
            "single_select_field": single_select_field.id,
            "card_cover_image_field": cover_image_file_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 2"
    assert response_json["type"] == "kanban"
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is False
    assert response_json["single_select_field"] == single_select_field.id
    assert response_json["card_cover_image_field"] == cover_image_file_field.id

    kanban_view = KanbanView.objects.all().last()
    assert kanban_view.id == response_json["id"]
    assert kanban_view.single_select_field_id == single_select_field.id


@pytest.mark.django_db
def test_create_kanban_view_invalid_card_cover_image_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text = data_fixture.create_text_field(table=table)
    file_field = data_fixture.create_file_field()

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 2", "type": "kanban", "card_cover_image_field": text.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["card_cover_image_field"][0]["code"] == "does_not_exist"
    )

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 2", "type": "kanban", "card_cover_image_field": file_field.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_NOT_IN_TABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_kanban_view(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None
    )
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    single_select_field_2 = premium_data_fixture.create_single_select_field()

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": kanban_view.id}),
        {
            "single_select_field": single_select_field_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response_json["error"]
        == "ERROR_KANBAN_VIEW_FIELD_DOES_NOT_BELONG_TO_SAME_TABLE"
    )

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": kanban_view.id}),
        {
            "single_select_field": single_select_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["single_select_field"] == single_select_field.id

    kanban_view.refresh_from_db()
    assert kanban_view.single_select_field_id == single_select_field.id

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": kanban_view.id}),
        {
            "single_select_field": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["single_select_field"] is None

    kanban_view.refresh_from_db()
    assert kanban_view.single_select_field is None


@pytest.mark.django_db
def test_update_kanban_view_card_cover_image_field(
    api_client, data_fixture, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    cover_image_file_field = data_fixture.create_file_field(table=table)
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, card_cover_image_field=None
    )

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": kanban_view.id}),
        {
            "card_cover_image_field": cover_image_file_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["card_cover_image_field"] == cover_image_file_field.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_kanban_view(data_fixture, premium_data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field_1 = premium_data_fixture.create_single_select_field(table=table)
    single_select_field_2 = premium_data_fixture.create_single_select_field(table=table)
    cover_image_file_field_1 = data_fixture.create_file_field(table=table)
    cover_image_file_field_2 = data_fixture.create_file_field(table=table)
    kanban_view = premium_data_fixture.create_kanban_view(table=table)

    original_kanban_data = {
        "name": "Test Original",
        "filter_type": "AND",
        "filters_disabled": False,
        "single_select_field": single_select_field_1,
        "card_cover_image_field": cover_image_file_field_1,
    }

    kanban_view_with_changes = ViewHandler().update_view(
        user, kanban_view, **original_kanban_data
    )
    kanban_view = kanban_view_with_changes.updated_view_instance

    assert kanban_view.name == original_kanban_data["name"]
    assert kanban_view.filter_type == original_kanban_data["filter_type"]
    assert kanban_view.filters_disabled == original_kanban_data["filters_disabled"]
    assert (
        kanban_view.single_select_field_id
        == original_kanban_data["single_select_field"].id
    )
    assert (
        kanban_view.card_cover_image_field_id
        == original_kanban_data["card_cover_image_field"].id
    )

    new_kanban_data = {
        "name": "Test New",
        "filter_type": "OR",
        "filters_disabled": True,
        "single_select_field": single_select_field_2,
        "card_cover_image_field": cover_image_file_field_2,
    }

    kanban_view = action_type_registry.get_by_type(UpdateViewActionType).do(
        user, kanban_view, **new_kanban_data
    )

    assert kanban_view.name == new_kanban_data["name"]
    assert kanban_view.filter_type == new_kanban_data["filter_type"]
    assert kanban_view.filters_disabled == new_kanban_data["filters_disabled"]
    assert (
        kanban_view.single_select_field_id == new_kanban_data["single_select_field"].id
    )
    assert (
        kanban_view.card_cover_image_field_id
        == new_kanban_data["card_cover_image_field"].id
    )

    action_undone = ActionHandler.undo(
        user, [ViewActionScopeType.value(kanban_view.id)], session_id
    )

    kanban_view.refresh_from_db()
    assert_undo_redo_actions_are_valid(action_undone, [UpdateViewActionType])

    assert kanban_view.name == original_kanban_data["name"]
    assert kanban_view.filter_type == original_kanban_data["filter_type"]
    assert kanban_view.filters_disabled == original_kanban_data["filters_disabled"]
    assert (
        kanban_view.single_select_field_id
        == original_kanban_data["single_select_field"].id
    )
    assert (
        kanban_view.card_cover_image_field_id
        == original_kanban_data["card_cover_image_field"].id
    )

    action_redone = ActionHandler.redo(
        user, [ViewActionScopeType.value(kanban_view.id)], session_id
    )

    kanban_view.refresh_from_db()
    assert_undo_redo_actions_are_valid(action_redone, [UpdateViewActionType])

    assert kanban_view.name == new_kanban_data["name"]
    assert kanban_view.filter_type == new_kanban_data["filter_type"]
    assert kanban_view.filters_disabled == new_kanban_data["filters_disabled"]
    assert (
        kanban_view.single_select_field_id == new_kanban_data["single_select_field"].id
    )
    assert (
        kanban_view.card_cover_image_field_id
        == new_kanban_data["card_cover_image_field"].id
    )


@pytest.mark.django_db
def test_can_duplicate_kanban_view_with_cover_image(
    api_client, data_fixture, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    cover_image_file_field = data_fixture.create_file_field(table=table)
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, card_cover_image_field=cover_image_file_field
    )

    assert View.objects.count() == 1

    response = api_client.post(
        reverse("api:database:views:duplicate", kwargs={"view_id": kanban_view.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] != kanban_view.id
    assert response_json["name"] == f"{kanban_view.name} 2"
    assert response_json["card_cover_image_field"] == cover_image_file_field.id

    assert View.objects.count() == 2


@pytest.mark.django_db
def test_get_public_kanban_without_with_single_select_and_cover(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, public=True, single_select_field=None
    )

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, hidden_field, hidden=True
    )

    # Can access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": kanban_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "fields": [
            {
                "id": public_field.id,
                "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "name": "public",
                "order": 0,
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
            "id": kanban_view.slug,
            "name": kanban_view.name,
            "order": 0,
            "public": True,
            "slug": kanban_view.slug,
            "sortings": [],
            "group_bys": [],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "type": "kanban",
            "card_cover_image_field": None,
            "single_select_field": None,
            "show_logo": True,
            "allow_public_export": False,
        },
    }


@pytest.mark.django_db
def test_get_public_kanban_view_with_single_select_and_cover(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(
        table=table, order=0
    )
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, public=True, single_select_field=single_select_field
    )
    single_select_field = kanban_view.single_select_field

    # Only information related the public field should be returned
    cover_field = premium_data_fixture.create_file_field(
        table=table, name="cover", order=1
    )
    public_field = premium_data_fixture.create_text_field(
        table=table, name="public", order=2
    )
    hidden_field = premium_data_fixture.create_text_field(
        table=table, name="hidden", order=3
    )

    kanban_view.card_cover_image_field = cover_field
    kanban_view.save()

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, single_select_field, hidden=False, order=0
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, cover_field, hidden=True, order=1
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False, order=2
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, hidden_field, hidden=True, order=3
    )

    # Can access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": kanban_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "fields": [
            {
                "id": single_select_field.id,
                "name": single_select_field.name,
                "order": 0,
                "primary": single_select_field.primary,
                "select_options": [],
                "single_select_default": None,
                "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "type": "single_select",
                "read_only": False,
                "description": None,
                "immutable_properties": False,
                "immutable_type": False,
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "db_index": False,
                "field_constraints": [],
            },
            {
                "id": cover_field.id,
                "name": cover_field.name,
                "order": 1,
                "primary": cover_field.primary,
                "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "type": "file",
                "read_only": False,
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
                "order": 2,
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
            "id": kanban_view.slug,
            "name": kanban_view.name,
            "order": 0,
            "public": True,
            "slug": kanban_view.slug,
            "sortings": [],
            "group_bys": [],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "type": "kanban",
            "card_cover_image_field": cover_field.id,
            "single_select_field": single_select_field.id,
            "show_logo": True,
            "allow_public_export": False,
        },
    }


@pytest.mark.django_db
def test_list_public_rows_without_single_select_field(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, public=True, single_select_field=None
    )

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_KANBAN_VIEW_HAS_NO_SINGLE_SELECT_FIELD"


@pytest.mark.django_db
def test_list_public_rows_without_password(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )
    kanban_view.set_password("test")
    kanban_view.save()

    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        ),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_public_rows_with_valid_password(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )
    kanban_view.set_password("test")
    kanban_view.save()

    token = ViewHandler().encode_public_view_token(kanban_view)
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        ),
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

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )
    kanban_view.set_password("test")
    kanban_view.save()

    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
        format="json",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_list_public_rows_doesnt_show_hidden_columns(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")

    single_select_field_options = KanbanViewFieldOptions.objects.get(
        field_id=kanban_view.single_select_field_id
    )
    public_field_option = premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, hidden_field, hidden=True
    )

    RowHandler().create_row(user, table, values={})

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
        + "?include=field_options"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "rows": {
            "null": {
                "count": 1,
                "results": [
                    {
                        "id": 1,
                        "order": "1.00000000000000000000",
                        f"field_{public_field.id}": None,
                        f"field_{kanban_view.single_select_field_id}": None,
                    }
                ],
            }
        },
        "field_options": {
            f"{public_field.id}": {
                "hidden": False,
                "order": public_field_option.order,
            },
            f"{kanban_view.single_select_field_id}": {
                "hidden": True,
                "order": single_select_field_options.order,
            },
        },
    }


@pytest.mark.django_db
def test_list_public_rows_with_view_filters(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")

    KanbanViewFieldOptions.objects.get(field_id=kanban_view.single_select_field_id)
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )

    row_1 = RowHandler().create_row(
        user, table, values={f"field_{public_field.id}": "test1"}
    )
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "test2"})
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "test3"})

    premium_data_fixture.create_view_filter(
        view=kanban_view, field=public_field, value="test1"
    )

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "rows": {
            "null": {
                "count": 1,
                "results": [
                    {
                        "id": row_1.id,
                        "order": "1.00000000000000000000",
                        f"field_{public_field.id}": "test1",
                        f"field_{kanban_view.single_select_field_id}": None,
                    },
                ],
            }
        },
    }


@pytest.mark.django_db
def test_list_public_rows_with_query_param_filters(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")

    KanbanViewFieldOptions.objects.get(field_id=kanban_view.single_select_field_id)
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )

    row_1 = RowHandler().create_row(
        user, table, values={f"field_{public_field.id}": "test1"}
    )
    row_2 = RowHandler().create_row(
        user, table, values={f"field_{public_field.id}": "test2"}
    )
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "test3"})

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
        + f"?filter__field_{public_field.id}__equal=test1"
        f"&filter__field_{public_field.id}__equal=test2"
        f"&filter_type=OR"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "rows": {
            "null": {
                "count": 2,
                "results": [
                    {
                        "id": row_1.id,
                        "order": "1.00000000000000000000",
                        f"field_{public_field.id}": "test1",
                        f"field_{kanban_view.single_select_field_id}": None,
                    },
                    {
                        "id": row_2.id,
                        "order": "2.00000000000000000000",
                        f"field_{public_field.id}": "test2",
                        f"field_{kanban_view.single_select_field_id}": None,
                    },
                ],
            }
        },
    }


@pytest.mark.django_db
def test_list_public_rows_with_query_param_filters_with_zero_results(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")

    KanbanViewFieldOptions.objects.get(field_id=kanban_view.single_select_field_id)
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )

    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "test1"})
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "test2"})
    RowHandler().create_row(user, table, values={f"field_{public_field.id}": "test3"})

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
        + f"?filter__field_{public_field.id}__equal=NOT_EXISTING"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "rows": {
            "null": {
                "count": 0,
                "results": [],
            }
        },
    }


@pytest.mark.django_db
def test_list_public_rows_invalid_select_option_parameter(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )

    url = reverse(
        "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
    )
    response = api_client.get(
        f"{url}?select_option=null,a",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_SELECT_OPTION_PARAMETER"

    response = api_client.get(
        f"{url}?select_option=null,1,1&select_option=1,1,a",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_SELECT_OPTION_PARAMETER"


@pytest.mark.django_db
def test_list_public_rows_valid_select_option_parameter(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )
    single_select = kanban_view.single_select_field
    option_a = premium_data_fixture.create_select_option(
        field=single_select, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select, value="B", color="red"
    )

    row_1 = RowHandler().create_row(
        user, table, values={f"field_{single_select.id}": option_a.id}
    )
    row_2 = RowHandler().create_row(
        user, table, values={f"field_{single_select.id}": option_b.id}
    )
    row_3 = RowHandler().create_row(user, table)

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "rows": {
            "null": {
                "count": 1,
                "results": [
                    {
                        "id": row_3.id,
                        "order": "3.00000000000000000000",
                        f"field_{single_select.id}": None,
                    },
                ],
            },
            str(option_a.id): {
                "count": 1,
                "results": [
                    {
                        "id": row_1.id,
                        "order": "1.00000000000000000000",
                        f"field_{single_select.id}": {
                            "color": "blue",
                            "id": option_a.id,
                            "value": option_a.value,
                        },
                    },
                ],
            },
            str(option_b.id): {
                "count": 1,
                "results": [
                    {
                        "id": row_2.id,
                        "order": "2.00000000000000000000",
                        f"field_{single_select.id}": {
                            "color": "red",
                            "id": option_b.id,
                            "value": option_b.value,
                        },
                    },
                ],
            },
        },
    }


@pytest.mark.django_db
def test_list_public_rows_valid_select_option_query_parameter(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )
    single_select = kanban_view.single_select_field
    option_a = premium_data_fixture.create_select_option(
        field=single_select, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=single_select, value="B", color="red"
    )

    row_1 = RowHandler().create_row(
        user, table, values={f"field_{single_select.id}": option_a.id}
    )
    RowHandler().create_row(
        user, table, values={f"field_{single_select.id}": option_b.id}
    )
    RowHandler().create_row(user, table)

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
        + f"?select_option={option_a.id}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "rows": {
            str(option_a.id): {
                "count": 1,
                "results": [
                    {
                        "id": row_1.id,
                        "order": "1.00000000000000000000",
                        f"field_{single_select.id}": {
                            "color": "blue",
                            "id": option_a.id,
                            "value": option_a.value,
                        },
                    },
                ],
            }
        },
    }


@pytest.mark.django_db
def test_list_public_rows_limit_offset(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )

    KanbanViewFieldOptions.objects.get(field_id=kanban_view.single_select_field_id)

    RowHandler().create_row(user, table)
    row_2 = RowHandler().create_row(user, table)
    RowHandler().create_row(user, table)

    response = api_client.get(
        reverse(
            "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
        )
        + f"?limit=1&offset=1"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "rows": {
            "null": {
                "count": 3,
                "results": [
                    {
                        "id": row_2.id,
                        "order": "2.00000000000000000000",
                        f"field_{kanban_view.single_select_field_id}": None,
                    },
                ],
            }
        },
    }


@pytest.mark.django_db
def test_kanban_view_hierarchy(api_client, premium_data_fixture):
    user = premium_data_fixture.create_user()
    workspace = premium_data_fixture.create_workspace(user=user)
    app = premium_data_fixture.create_database_application(
        workspace=workspace, name="Test 1"
    )
    table = premium_data_fixture.create_database_table(database=app)
    premium_data_fixture.create_text_field(table=table)

    kanban_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
        public=True,
    )
    assert kanban_view.get_parent() == table
    assert kanban_view.get_root() == workspace

    kanban_view_field_options = kanban_view.get_field_options()[0]
    assert kanban_view_field_options.get_parent() == kanban_view
    assert kanban_view_field_options.get_root() == workspace


@pytest.mark.django_db
def test_list_rows_public_with_query_param_filter(api_client, premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, public=True
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__contains=a"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["rows"]["null"]["count"] == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == first_row.id

    url = reverse(
        "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
    )
    get_params = [
        f"filter__field_{public_field.id}__contains=a",
        f"filter__field_{public_field.id}__contains=b",
        f"filter_type=OR",
    ]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["rows"]["null"]["count"] == 2

    get_params = [f"filter__field_{hidden_field.id}__contains=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    get_params = [f"filter__field_{public_field.id}__random=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    get_params = [f"filter__field_{public_field.id}__higher_than=1"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
def test_list_rows_public_with_query_param_advanced_filters(
    api_client, premium_data_fixture
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, user=user, public=True
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, public_field, hidden=False
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:kanban:public_rows", kwargs={"slug": kanban_view.slug}
    )
    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "contains",
                "value": "a",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["rows"]["null"]["count"] == 1
    assert response_json["rows"]["null"]["results"][0]["id"] == first_row.id

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "OR",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "b",
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["rows"]["null"]["count"] == 2

    # groups can be arbitrarily nested
    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "",
                    },
                ],
                "groups": [
                    {
                        "filter_type": "OR",
                        "filters": [
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "a",
                            },
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "b",
                            },
                        ],
                    },
                ],
            },
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["rows"]["null"]["count"] == 2

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": hidden_field.id,
                "type": "contains",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "random",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "higher_than",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"

    for filters in [
        "invalid_json",
        json.dumps({"filter_type": "invalid"}),
        json.dumps({"filter_type": "OR", "filters": "invalid"}),
    ]:
        get_params = [f"filters={filters}"]
        response = api_client.get(f'{url}?{"&".join(get_params)}')
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"


@pytest.mark.django_db
def test_reference_to_single_select_field_is_removed_after_trashing(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=single_select_field
    )
    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.get(f"{url}", **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    json_response = response.json()

    assert len(json_response) == 1
    assert json_response[0]["id"] == single_select_field.id

    field_handler = FieldHandler()
    field_handler.delete_field(user, single_select_field)
    kanban.refresh_from_db()

    assert kanban.single_select_field is None
    assert kanban.single_select_field_id is None

    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.get(f"{url}", **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    json_response = response.json()

    assert len(json_response) == 0
