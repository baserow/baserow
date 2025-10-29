import json
from unittest.mock import patch

from django.db import transaction
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    CreateRowWorkflowActionType,
    DeleteRowWorkflowActionType,
    NotificationWorkflowActionType,
    UpdateRowWorkflowActionType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE, BaserowFormulaObject


@pytest.mark.django_db
def test_create_notification_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action_type = NotificationWorkflowActionType.type

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": workflow_action_type, "event": "click", "element_id": element.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == workflow_action_type
    assert response_json["element_id"] == element.id


@pytest.mark.django_db
def test_create_workflow_action_page_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow_action_type = NotificationWorkflowActionType.type

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": 99999})
    response = api_client.post(
        url,
        {"type": workflow_action_type, "event": "click"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db(transaction=True)
def test_create_workflow_action_element_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    workflow_action_type = NotificationWorkflowActionType.type

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": workflow_action_type, "event": "click", "element_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db(transaction=True)
def test_create_workflow_action_event_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    workflow_action_type = NotificationWorkflowActionType.type

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {"type": workflow_action_type, "event": "invalid"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # NOTE: Event names are no longer bound to a list of choices, so
    #       the API will not raise a 400 Bad Request error
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_get_workflow_actions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    workflow_action_one = data_fixture.create_notification_workflow_action(page=page)
    workflow_action_two = data_fixture.create_notification_workflow_action(page=page)

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json[0]["id"] == workflow_action_one.id
    assert response_json[1]["id"] == workflow_action_two.id


@pytest.mark.django_db
def test_delete_workflow_actions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    workflow_action = data_fixture.create_notification_workflow_action(page=page)

    url = reverse(
        "api:builder:workflow_action:item",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_patch_workflow_actions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    workflow_action = data_fixture.create_notification_workflow_action(page=page)

    url = reverse(
        "api:builder:workflow_action:item",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    response = api_client.patch(
        url,
        {"description": "'hello'"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["description"]["formula"] == "'hello'"


class PublicTestWorkflowActionType(NotificationWorkflowActionType):
    type = "test_workflow_action"

    public_serializer_field_names = ["test"]
    public_serializer_field_overrides = {
        "test": FormulaSerializerField(
            required=False,
        ),
    }


@pytest.mark.django_db
def test_public_workflow_actions_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    BuilderWorkflowActionHandler().create_workflow_action(
        NotificationWorkflowActionType(), page=page
    )

    published_builder = data_fixture.create_builder_application(workspace=None)
    published_page = data_fixture.create_builder_page(builder=published_builder)
    BuilderWorkflowActionHandler().create_workflow_action(
        NotificationWorkflowActionType(), page=published_page
    )

    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )

    url = reverse(
        "api:builder:domains:list_workflow_actions",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["type"] == NotificationWorkflowActionType.type

    url = reverse(
        "api:builder:domains:list_workflow_actions",
        kwargs={"page_id": published_page.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["type"] == NotificationWorkflowActionType.type


@pytest.mark.django_db
def test_order_workflow_actions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, order=1
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, element=element, order=2
    )

    order = [workflow_action_two.id, workflow_action_one.id]

    url = reverse(
        "api:builder:workflow_action:order",
        kwargs={"page_id": page.id},
    )
    response = api_client.post(
        url,
        {"workflow_action_ids": order, "element_id": element.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT

    workflow_action_one.refresh_from_db()
    workflow_action_two.refresh_from_db()

    assert workflow_action_one.order > workflow_action_two.order


@pytest.mark.django_db
def test_order_workflow_actions_page_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse(
        "api:builder:workflow_action:order",
        kwargs={"page_id": 99999},
    )
    response = api_client.post(
        url,
        {"workflow_action_ids": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_order_workflow_actions_workflow_action_does_not_exist(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse(
        "api:builder:workflow_action:order",
        kwargs={"page_id": page.id},
    )
    response = api_client.post(
        url,
        {"workflow_action_ids": [9999]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_order_workflow_actions_workflow_action_not_in_element(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, order=1
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, order=2
    )

    order = [workflow_action_two.id, workflow_action_one.id]

    url = reverse(
        "api:builder:workflow_action:order",
        kwargs={"page_id": page.id},
    )
    response = api_client.post(
        url,
        {"workflow_action_ids": order, "element_id": element.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_create_create_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action_type = CreateRowWorkflowActionType.type

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": workflow_action_type,
            "event": "click",
            "element_id": element.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == workflow_action_type
    assert response_json["element_id"] == element.id

    workflow_action = CreateRowWorkflowActionType.model_class.objects.get(
        pk=response_json["id"]
    )
    assert response_json["service"] == {
        "id": workflow_action.service_id,
        "integration_id": None,
        "row_id": BaserowFormulaObject(
            formula="",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "type": LocalBaserowUpsertRowServiceType.type,
        "schema": None,
        "table_id": None,
        "field_mappings": [],
        "context_data": None,
        "context_data_schema": None,
        "sample_data": None,
    }


@pytest.mark.django_db
def test_update_create_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Animal", "text"),
        ],
        rows=[],
    )
    field = table.field_set.get(name="Animal")
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK, user=user
    )
    service = workflow_action.service
    service_type = service.get_type()

    url = reverse(
        "api:builder:workflow_action:item",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    response = api_client.patch(
        url,
        {
            "service": {
                "table_id": table.id,
                "type": service_type.type,
                "integration_id": workflow_action.service.integration_id,
                "field_mappings": [
                    {"field_id": field.id, "value": "'Pony'", "enabled": True}
                ],
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    service.refresh_from_db()

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == workflow_action.id
    assert response_json["element_id"] == workflow_action.element_id
    assert response_json["service"]["table_id"] == service.table_id
    assert response_json["service"]["integration_id"] == service.integration_id
    assert response_json["service"]["field_mappings"] == [
        {
            "field_id": field.id,
            "value": BaserowFormulaObject(
                formula="'Pony'",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "enabled": True,
        }
    ]


@pytest.mark.django_db
def test_create_update_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action_type = UpdateRowWorkflowActionType.type

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": workflow_action_type,
            "event": "click",
            "element_id": element.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == workflow_action_type
    assert response_json["element_id"] == element.id

    workflow_action = UpdateRowWorkflowActionType.model_class.objects.get(
        pk=response_json["id"]
    )
    assert response_json["service"] == {
        "id": workflow_action.service_id,
        "integration_id": None,
        "type": LocalBaserowUpsertRowServiceType.type,
        "schema": None,
        "row_id": BaserowFormulaObject(
            formula="",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "table_id": None,
        "field_mappings": [],
        "context_data": None,
        "context_data_schema": None,
        "sample_data": None,
    }


@pytest.mark.django_db
def test_update_update_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Animal", "text"),
        ],
        rows=[
            ["Badger"],
        ],
    )
    model = table.get_model()
    first_row = model.objects.get()
    field = table.field_set.get(name="Animal")
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK, user=user
    )
    service = workflow_action.service
    service_type = service.get_type()

    url = reverse(
        "api:builder:workflow_action:item",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    response = api_client.patch(
        url,
        {
            "service": {
                "id": workflow_action.service_id,
                "table_id": table.id,
                "row_id": first_row.id,
                "type": service_type.type,
                "integration_id": workflow_action.service.integration_id,
                "field_mappings": [
                    {"field_id": field.id, "value": "'Pony'", "enabled": True}
                ],
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    service.refresh_from_db()

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == workflow_action.id
    assert response_json["element_id"] == workflow_action.element_id

    assert response_json["service"]["table_id"] == table.id
    assert response_json["service"]["row_id"]["formula"] == str(first_row.id)
    assert (
        response_json["service"]["integration_id"]
        == workflow_action.service.integration_id
    )
    assert response_json["service"]["field_mappings"] == [
        {
            "field_id": field.id,
            "value": BaserowFormulaObject(
                formula="'Pony'",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "enabled": True,
        }
    ]


@pytest.mark.django_db
def test_dispatch_local_baserow_create_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Animal", "text"),
            ("Color", "text"),
        ],
        rows=[],
    )
    color_field = table.field_set.get(name="Color")
    animal_field = table.field_set.get(name="Animal")
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK, user=user
    )
    service = workflow_action.service.specific
    service.table = table
    service.field_mappings.create(field=color_field, value="'Brown'")
    service.field_mappings.create(field=animal_field, value="'Horse'")
    service.save()

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )

    with patch(
        "baserow.contrib.builder.handler.get_builder_used_property_names"
    ) as used_properties_mock:
        used_properties_mock.return_value = {
            "all": {workflow_action.service.id: ["id", color_field.db_column]},
            "external": {workflow_action.service.id: ["id", color_field.db_column]},
        }
        response = api_client.post(
            url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert "id" in response_json
    assert response_json[color_field.name] == "Brown"
    assert animal_field.name not in response_json


@pytest.mark.django_db
def test_dispatch_local_baserow_update_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Animal", "text"),
            ("Color", "text"),
        ],
        rows=[["Horse", "Brown"]],
    )
    model = table.get_model()
    first_row = model.objects.all()[0]
    color_field = table.field_set.get(name="Color")
    animal_field = table.field_set.get(name="Animal")
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        page=page,
        element=element,
        event=EventTypes.CLICK,
        user=user,
    )
    service = workflow_action.service.specific
    service.table = table
    service.row_id = f"'{first_row.id}'"
    service.field_mappings.create(field=color_field, value="'Blue'")
    service.field_mappings.create(field=animal_field, value="'Horse'")
    service.save()

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )

    with patch(
        "baserow.contrib.builder.handler.get_builder_used_property_names"
    ) as used_properties_mock:
        used_properties_mock.return_value = {
            "all": {workflow_action.service.id: ["id", color_field.db_column]},
            "external": {workflow_action.service.id: ["id", color_field.db_column]},
        }
        response = api_client.post(
            url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == first_row.id

    assert response_json[color_field.name] == "Blue"
    assert animal_field.name not in response_json


@pytest.mark.django_db
def test_dispatch_local_baserow_upsert_row_workflow_action_with_current_record(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Index", "text", {}),
        ],
    )
    index = table.field_set.get(name="Index")
    page = data_fixture.create_builder_page(builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user, authorized_user=user
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    service.field_mappings.create(
        field=index, value='concat("Index ", get("current_record.__idx__"))'
    )
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, service=service, element=element, event=EventTypes.CLICK
    )

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    with patch(
        "baserow.contrib.builder.handler.get_builder_used_property_names"
    ) as used_properties_mock:
        used_properties_mock.return_value = {
            "all": {workflow_action.service.id: [index.db_column]},
            "external": {workflow_action.service.id: [index.db_column]},
        }
        payload = {
            "metadata": json.dumps({"current_record": {"index": 123, "record_id": 123}})
        }
        response = api_client.post(
            url,
            payload,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "id" not in response_json
    assert response_json[index.name] == "Index 123"


@pytest.mark.django_db(transaction=True)
def test_dispatch_local_baserow_upsert_row_workflow_action_with_unmatching_index_and_record_id(
    api_client, data_fixture
):
    with transaction.atomic():
        user, token = data_fixture.create_user_and_token()
        workspace = data_fixture.create_workspace(user=user)
        database = data_fixture.create_database_application(workspace=workspace)
        table = TableHandler().create_table_and_fields(
            user=user,
            database=database,
            name=data_fixture.fake.name(),
            fields=[
                ("Category", "text", {}),
            ],
        )
        field = table.field_set.get()
        rows = (
            RowHandler()
            .create_rows(
                user,
                table,
                rows_values=[
                    {f"field_{field.id}": "Community Engagement"},
                    {f"field_{field.id}": "Construction"},
                    {f"field_{field.id}": "Complex Construction Design"},
                    {f"field_{field.id}": "Simple Construction Design"},
                    {f"field_{field.id}": "Landscape Design"},
                    {f"field_{field.id}": "Infrastructure Design"},
                ],
            )
            .created_rows
        )

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user, authorized_user=user
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Button",
                "type": "button",
                "config": {"value": f"'Click me'"},
            },
        ],
    )
    table_element.property_options.create(
        schema_property=field.db_column,
        sortable=True,
        filterable=True,
        searchable=True,
    )

    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        page=page,
        element=table_element,
        event=EventTypes.CLICK,
        user=user,
    )
    service = workflow_action.service.specific
    service.table = table
    service.row_id = "get('current_record.id')"
    service.save()
    service.field_mappings.create(
        field=field, value=f"concat('Updated row ', get('current_record.id'))"
    )

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )

    with patch(
        "baserow.contrib.builder.handler.get_builder_used_property_names"
    ) as used_properties_mock:
        used_properties_mock.return_value = {
            "all": {workflow_action.service.id: ["id", field.db_column]},
            "external": {workflow_action.service.id: ["id", field.db_column]},
        }
        model = table.get_model()

        payload = {
            "metadata": json.dumps(
                {
                    "current_record": {"index": 0, "record_id": rows[2].id},
                    "data_source": {"element": table_element.id},
                }
            )
        }

        # Dispatch at index=0 but row 3 id, this will be "Complex Construction Design".
        response = api_client.post(
            url,
            payload,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        assert response.status_code == HTTP_200_OK
        row3 = model.objects.get(pk=rows[2].id)
        assert getattr(row3, field.db_column) == f"Updated row {rows[2].id}"

        payload = {
            "metadata": json.dumps(
                {
                    "current_record": {"index": 0, "record_id": rows[3].id},
                    "data_source": {"element": table_element.id},
                }
            )
        }

        # Dispatch at index=0 but row 4 id,
        # this will now be "Simple Construction Design".
        response = api_client.post(
            url,
            payload,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        row4 = model.objects.get(pk=rows[3].id)
        assert getattr(row4, field.db_column) == f"Updated row {rows[3].id}"


@pytest.mark.django_db
def test_dispatch_local_baserow_update_row_workflow_action_using_formula_with_data_source(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    wa_table, wa_fields, wa_rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Animal", "text"),
            ("Color", "text"),
        ],
        rows=[["Horse", "Brown"]],
    )
    first_row = wa_rows[0]
    color_field = wa_table.field_set.get(name="Color")
    animal_field = wa_table.field_set.get(name="Animal")

    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = data_fixture.create_builder_button_element(page=page)

    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        page=page,
        element=element,
        event=EventTypes.CLICK,
        user=user,
    )

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["42"],
            [f"{rows[1].id}"],
            ["44"],
            ["45"],
        ],
    )
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    shared_page = builder.shared_page

    shared_data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=shared_page,
        integration=integration,
        table=table2,
        row_id=f"'{rows2[1].id}'",
        name="Id source",
    )

    # This data source use the shared data source
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
        row_id=f"get('data_source.{shared_data_source.id}.{fields2[0].db_column}')",
        name="Item",
    )

    service = workflow_action.service.specific
    service.table = wa_table
    service.row_id = f"'{first_row.id}'"
    # from the local data source
    service.field_mappings.create(
        field=color_field,
        value=f"get('data_source.{data_source.id}.{fields[1].db_column}')",
    )
    # From the shared data source
    service.field_mappings.create(
        field=animal_field,
        value=f"get('data_source.{shared_data_source.id}.{fields2[0].db_column}')",
    )
    service.save()

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )

    with patch(
        "baserow.contrib.builder.handler.get_builder_used_property_names"
    ) as used_properties_mock:
        used_properties_mock.return_value = {
            "all": {
                data_source.service.id: [fields[1].db_column],
                shared_data_source.service.id: [fields2[0].db_column],
                workflow_action.service.id: [
                    color_field.db_column,
                    animal_field.db_column,
                ],
            },
            "external": {
                data_source.service.id: [fields[1].db_column],
                shared_data_source.service.id: [fields2[0].db_column],
                workflow_action.service.id: [
                    color_field.db_column,
                    animal_field.db_column,
                ],
            },
        }
        response = api_client.post(
            url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[color_field.name] == "Orange"
    assert response_json[animal_field.name] == f"{rows[1].id}"


@pytest.mark.django_db
def test_dispatch_workflow_action_with_invalid_form_data(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    button_element = data_fixture.create_builder_button_element(page=page)
    input_text_element = data_fixture.create_builder_input_text_element(
        page=page, required=True
    )
    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        page=page, element=button_element, event=EventTypes.CLICK, user=user
    )
    service = workflow_action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(
        field=field, value=f"get('form_data.{input_text_element.id}')"
    )

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    payload = {"metadata": json.dumps({"form_data": {input_text_element.id: ""}})}
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT",
        "detail": f'Value error for field "{field.name}": The value is required',
    }


@pytest.mark.django_db
def test_create_delete_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action_type = DeleteRowWorkflowActionType.type

    url = reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": workflow_action_type,
            "event": "click",
            "element_id": element.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == workflow_action_type
    assert response_json["element_id"] == element.id

    workflow_action = DeleteRowWorkflowActionType.model_class.objects.get(
        pk=response_json["id"]
    )
    assert response_json["service"] == {
        "id": workflow_action.service_id,
        "integration_id": None,
        "row_id": BaserowFormulaObject(
            formula="",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "type": DeleteRowWorkflowActionType.service_type,
        "schema": None,
        "table_id": None,
        "context_data": None,
        "context_data_schema": None,
        "sample_data": None,
    }


@pytest.mark.django_db
def test_update_delete_row_workflow_action(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_delete_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK
    )
    service = workflow_action.service
    service_type = service.get_type()

    url = reverse(
        "api:builder:workflow_action:item",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    response = api_client.patch(
        url,
        {
            "service": {
                "row_id": "123",
                "table_id": table.id,
                "type": service_type.type,
                "integration_id": workflow_action.service.integration_id,
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    service.refresh_from_db()

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == workflow_action.id
    assert response_json["element_id"] == workflow_action.element_id
    assert response_json["service"]["row_id"] == service.row_id
    assert response_json["service"]["table_id"] == service.table_id
    assert response_json["service"]["integration_id"] == service.integration_id


@pytest.fixture
def workflow_action_hidden_fields_fixture(data_fixture):
    """Fixture to help test hidden fields related to Workflow Actions."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Spiciness", "number"),
            ("Color", "text"),
        ],
        rows=[
            ["Paneer Tikka", 5, "Red"],
            ["Gobi Manchurian", 8, "Yellow"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(builder=builder)

    # Create the button and workflow actions
    button = data_fixture.create_builder_button_element(page=page)

    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    service.field_mappings.create(
        field=fields[0],
        value=f"'Palak Paneer'",
    )
    service.field_mappings.create(
        field=fields[1],
        value=f"'3'",
    )
    service.field_mappings.create(
        field=fields[2],
        value=f"'Green'",
    )

    return {
        "user": user,
        "token": token,
        "page": page,
        "service": service,
        "integration": integration,
        "button": button,
        "fields": fields,
    }


@pytest.mark.django_db
def test_workflow_action_dispatch_does_not_return_fields(
    data_fixture, api_client, workflow_action_hidden_fields_fixture
):
    """
    An Integration test to ensure that a Workflow Action does not return any
    field information by default.
    """

    page = workflow_action_hidden_fields_fixture["page"]
    service = workflow_action_hidden_fields_fixture["service"]
    button = workflow_action_hidden_fields_fixture["button"]
    token = workflow_action_hidden_fields_fixture["token"]

    action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        service=service,
        element=button,
        event=EventTypes.CLICK,
    )

    url = reverse(
        "api:builder:workflow_action:dispatch", kwargs={"workflow_action_id": action.id}
    )
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200

    # Ensure that field information is not returned.
    assert response.json() == {}


@pytest.mark.django_db
def test_notification_action_can_access_the_field_of_previous_action(
    data_fixture, api_client, workflow_action_hidden_fields_fixture
):
    """
    An Integration test to ensure that a chained Workflow Action has access to
    the Previous Action field. In this test, there are two Workflow Actions:
    'Create Row' followed by a 'Show Notification'.

    When dispatching a Workflow Action, the response will not contain any field
    information by default.

    However, if a field is explicitly referenced, e.g. in a Show Notification
    Workflow Action where the description uses the field, that field will
    be returned in the dispatch response. The field is needed for the frontend
    to correctly display the value.
    """

    page = workflow_action_hidden_fields_fixture["page"]
    service = workflow_action_hidden_fields_fixture["service"]
    button = workflow_action_hidden_fields_fixture["button"]
    fields = workflow_action_hidden_fields_fixture["fields"]
    token = workflow_action_hidden_fields_fixture["token"]

    action_1 = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        service=service,
        element=button,
        event=EventTypes.CLICK,
    )

    # This second workflow action references the field that was just created
    # by the first workflow action.
    _ = data_fixture.create_notification_workflow_action(
        page=page,
        element=button,
        event=EventTypes.CLICK,
        description=f"get('previous_action.{action_1.id}.{fields[0].db_column}')",
        title=f"'hello world'",
    )

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": action_1.id},
    )
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200

    # Since the first field was used in action_2, the dispatch response action
    # returns the field so that the frontend can display the value.
    #
    # Conversely, the other DB columns aren't returned, since they aren't used.
    assert response.json() == {
        fields[0].name: "Palak Paneer",
    }


@pytest.mark.django_db
def test_create_row_action_can_access_the_field_of_previous_action(
    data_fixture, api_client, workflow_action_hidden_fields_fixture
):
    """
    An Integration test to ensure that a chained Workflow Action has access to
    the Previous Action field. In this test, there are two Workflow Actions:
    'Create Row' followed by another 'Create row'.

    The second 'Create row' creates a new row in a different table, inserting
    the `id` of the previous 'Create row' action.
    """

    user = workflow_action_hidden_fields_fixture["user"]
    page = workflow_action_hidden_fields_fixture["page"]
    service = workflow_action_hidden_fields_fixture["service"]
    button = workflow_action_hidden_fields_fixture["button"]
    token = workflow_action_hidden_fields_fixture["token"]
    integration = workflow_action_hidden_fields_fixture["integration"]

    action_1 = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        service=service,
        element=button,
        event=EventTypes.CLICK,
    )

    table_2, fields_2, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[],
    )
    service_2 = data_fixture.create_local_baserow_upsert_row_service(
        table=table_2,
        integration=integration,
    )
    service_2.field_mappings.create(
        field=fields_2[0],
        value=f"get('previous_action.{action_1.id}.id')",
    )
    # This second workflow action references the field that was just created
    # by the first workflow action.
    action_2 = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        element=button,
        service=service_2,
        event=EventTypes.CLICK,
    )

    mock_dispatch_id = "3ae8b86c-6f5d-4215-918a-dd1aad85eb3a"
    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": action_1.id},
    )
    payload = {
        "metadata": json.dumps(
            {
                "previous_action": {
                    "current_dispatch_id": mock_dispatch_id,
                }
            }
        )
    }
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {}

    # Ensure that the 2nd table currently has zero rows
    assert action_2.service.table.get_model().objects.all().count() == 0

    # Now dispatch the 2nd Workflow Action
    payload = {
        "metadata": json.dumps(
            {
                "previous_action": {
                    "current_dispatch_id": mock_dispatch_id,
                    action_1.id: {},
                },
            }
        )
    }
    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": action_2.id},
    )
    response = api_client.post(
        url,
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {}

    results = table_2.get_model().objects.all()
    assert len(results) == 1
    # The ID of the new row that was created by the first Workflow Action
    row_id = action_1.service.table.get_model().objects.all()[2].id
    assert getattr(results[0], fields_2[0].db_column) == str(row_id)
