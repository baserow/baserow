from unittest import mock

from django.db.models import QuerySet
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.field_rules.models import FieldRule
from baserow.contrib.database.field_rules.registries import (
    FieldRulesTypeRegistry,
    FieldRuleType,
    FieldRuleValidity,
    RowRuleValidity,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.test_utils.helpers import AnyInt


class DummyFieldRuleType(FieldRuleType):
    type = "dummy"
    model_class = FieldRule

    def validate_row(
        self, row: GeneratedTableModel, rule: FieldRule
    ) -> RowRuleValidity:
        return RowRuleValidity(row_id=row.id, rule_id=rule.id, is_valid=True)

    def validate_rows(
        self, table: Table, rule: FieldRule, queryset: QuerySet | None = None
    ):
        return

    def validate_rule(self, rule: FieldRule) -> FieldRuleValidity:
        return FieldRuleValidity(
            table_id=rule.table_id,
            rule_id=rule.id,
            # one can inject rule validity by setting rule.set_is_valid
            is_valid=getattr(rule, "set_is_valid", True),
            error_text="",
        )


# field_rules_type_registry.register(DummyFieldRuleType())

local_field_rules_registry = FieldRulesTypeRegistry()
local_field_rules_registry.register(DummyFieldRuleType())


@mock.patch(
    "baserow.contrib.database.field_rules.handlers.FieldRuleHandler.registry",
    new=local_field_rules_registry,
)
@mock.patch(
    "baserow.contrib.database.field_rules.registries.field_rules_type_registry",
    new=local_field_rules_registry,
)
@pytest.mark.django_db
def test_create_field_rule(data_fixture, api_client):
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


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"invalid": "field"},
        {"type": "invalid"},
    ],
)
@mock.patch(
    "baserow.contrib.database.field_rules.handlers.FieldRuleHandler.registry",
    new=local_field_rules_registry,
)
@mock.patch(
    "baserow.contrib.database.field_rules.registries.field_rules_type_registry",
    new=local_field_rules_registry,
)
@pytest.mark.django_db
def test_create_rule_invalid_payloads(data_fixture, api_client, payload):
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
    assert response.status_code == HTTP_404_NOT_FOUND


@mock.patch(
    "baserow.contrib.database.field_rules.handlers.FieldRuleHandler.registry",
    new=local_field_rules_registry,
)
@mock.patch(
    "baserow.contrib.database.field_rules.registries.field_rules_type_registry",
    new=local_field_rules_registry,
)
@pytest.mark.django_db
def test_field_rule_update(data_fixture, api_client):
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


@mock.patch(
    "baserow.contrib.database.field_rules.handlers.FieldRuleHandler.registry",
    new=local_field_rules_registry,
)
@mock.patch(
    "baserow.contrib.database.field_rules.registries.field_rules_type_registry",
    new=local_field_rules_registry,
)
@pytest.mark.django_db
def test_field_rule_delete(data_fixture, api_client):
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
    assert response.status_code == HTTP_200_OK
    assert table.field_rules.all().count() == 0


@mock.patch(
    "baserow.contrib.database.field_rules.handlers.FieldRuleHandler.registry",
    new=local_field_rules_registry,
)
@mock.patch(
    "baserow.contrib.database.field_rules.registries.field_rules_type_registry",
    new=local_field_rules_registry,
)
@pytest.mark.django_db
def test_field_rule_list_invalid(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user)
    text_field = data_fixture.create_text_field(user, table=table)

    model = table.get_model()
    fid = text_field.db_column
    fh = FieldRuleHandler(table, user)
    rule = fh.create_rule("dummy", {"is_active": True})

    insert_rows = [
        {fid: "a"},
        {fid: "b"},
        {fid: "c"},
        {fid: "d"},
        {fid: "e"},
        {fid: "f"},
    ]
    # rows = data_fixture.create_rows_in_table(table, insert_rows)

    rows = (
        RowHandler()
        .create_rows(
            user=user,
            table=table,
            rows_values=insert_rows,
            send_realtime_update=False,
            send_webhook_events=False,
        )
        .created_rows
    )

    assert len(rows) == model.objects.all().count() == len(insert_rows)
    updated_rows = list(model.objects.filter(**{f"{fid}__in": ["a", "b", "c"]}))
    assert len(updated_rows) == 3

    model.objects.filter(**{f"{fid}__in": ["a", "b", "c"]}).update(
        field_rules_are_valid=False
    )

    url = reverse(
        "api:database:field_rules:invalid_rows", kwargs={"table_id": table.id}
    )
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["results"] == [{"id": r.id} for r in updated_rows]
