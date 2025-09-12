from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_409_CONFLICT,
)

from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
def test_create_field_rule(data_fixture, api_client, fake_field_rule_registry):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user)

    url = reverse("api:database:field_rules:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == []

    rule_payload = {"type": "dummy", "is_active": True}
    response = api_client.post(
        url,
        data=rule_payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    expected = {
        "id": AnyInt(),
        "table_id": AnyInt(),
        "error_text": None,
        "is_valid": True,
        "is_active": True,
        "type": "dummy",
    }
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == expected

    # add another
    response = api_client.post(
        url,
        data=rule_payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == expected

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == [expected, expected]
    assert response_json[0]["id"] < response_json[1]["id"]
    assert response_json[0]["table_id"] == response_json[1]["table_id"]


@pytest.mark.django_db
def test_create_field_rule_uniq(data_fixture, api_client, fake_field_rule_registry):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user)

    url = reverse("api:database:field_rules:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == []

    rule_payload = {"type": "dummy_uniq", "is_active": True}
    response = api_client.post(
        url,
        data=rule_payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    expected = {
        "id": AnyInt(),
        "table_id": AnyInt(),
        "error_text": None,
        "is_valid": True,
        "is_active": True,
        "type": "dummy",
    }
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == expected

    # add another, but fail because the type doesn't allow more than one
    response = api_client.post(
        url,
        data=rule_payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response_json == {
        "error": "ERROR_RULE_ALREADY_EXISTS",
        "detail": "The requested rule already exists.",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"invalid": "field"},
        {"type": "invalid"},
    ],
)
@pytest.mark.django_db
def test_create_rule_invalid_payloads(
    data_fixture, api_client, payload, fake_field_rule_registry
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user)

    url = reverse("api:database:field_rules:list", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        data=payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    response_json == {
        "error": "ERROR_RULE_TYPE_DOES_NOT_EXIST",
        "detail": "The requested rule type does not exist.",
    }
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_field_rule_update(data_fixture, api_client, fake_field_rule_registry):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user)

    url = reverse("api:database:field_rules:list", kwargs={"table_id": table.id})

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == []

    rule_payload = {"type": "dummy", "is_active": True}
    response = api_client.post(
        url,
        data=rule_payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    expected = {
        "id": AnyInt(),
        "table_id": AnyInt(),
        "error_text": None,
        "is_valid": True,
        "is_active": True,
        "type": "dummy",
    }
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == expected

    # Update item. Here we can just update is_active
    item_url = reverse(
        "api:database:field_rules:item",
        kwargs={"table_id": table.id, "rule_id": response_json["id"]},
    )
    rule_payload["is_active"] = False
    response = api_client.put(
        item_url,
        data=rule_payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    expected["is_active"] = False
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == expected


@pytest.mark.django_db
def test_field_rule_delete(data_fixture, api_client, fake_field_rule_registry):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user)

    url = reverse("api:database:field_rules:list", kwargs={"table_id": table.id})

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == []
    assert table.field_rules.all().count() == 0

    rule_payload = {"type": "dummy", "is_active": True}
    response = api_client.post(
        url,
        data=rule_payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    expected = {
        "id": AnyInt(),
        "table_id": AnyInt(),
        "error_text": None,
        "is_valid": True,
        "is_active": True,
        "type": "dummy",
    }
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == expected

    assert table.field_rules.all().count() == 1

    # Update item. Here we can just update is_active
    item_url = reverse(
        "api:database:field_rules:item",
        kwargs={"table_id": table.id, "rule_id": response_json["id"]},
    )
    rule_payload["is_active"] = False
    response = api_client.delete(
        item_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert table.field_rules.all().count() == 0
