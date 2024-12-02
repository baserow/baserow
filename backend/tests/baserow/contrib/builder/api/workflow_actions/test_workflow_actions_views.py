from unittest.mock import patch

from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.builder.data_providers.exceptions import (
    FormDataProviderChunkInvalidException,
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
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.formula.serializers import FormulaSerializerField


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
    assert response_json["description"] == "'hello'"


class PublicTestWorkflowActionType(NotificationWorkflowActionType):
    type = "test_workflow_action"

    public_serializer_field_names = ["test"]
    public_serializer_field_overrides = {
        "test": FormulaSerializerField(
            required=False,
            allow_blank=True,
            default="",
        ),
    }


@pytest.mark.django_db
def test_public_workflow_actions_view(
    api_client, data_fixture, mutable_builder_workflow_action_registry
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    mutable_builder_workflow_action_registry.unregister(
        NotificationWorkflowActionType().type
    )
    mutable_builder_workflow_action_registry.register(PublicTestWorkflowActionType())

    workflow_action = BuilderWorkflowActionHandler().create_workflow_action(
        PublicTestWorkflowActionType(), test="hello", page=page
    )

    url = reverse(
        "api:builder:workflow_action:item",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert "test" not in response.json()

    url = reverse(
        "api:builder:domains:list_workflow_actions",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    [workflow_action_in_response] = response.json()
    assert "test" in workflow_action_in_response


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
        "row_id": "",
        "type": LocalBaserowUpsertRowServiceType.type,
        "schema": None,
        "table_id": None,
        "field_mappings": [],
        "context_data": None,
        "context_data_schema": None,
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
        {"field_id": field.id, "value": "'Pony'", "enabled": True}
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
        "row_id": "",
        "table_id": None,
        "field_mappings": [],
        "context_data": None,
        "context_data_schema": None,
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
    assert response_json["service"]["row_id"] == str(first_row.id)
    assert (
        response_json["service"]["integration_id"]
        == workflow_action.service.integration_id
    )
    assert response_json["service"]["field_mappings"] == [
        {"field_id": field.id, "value": "'Pony'", "enabled": True}
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

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[color_field.db_column] == "Brown"
    assert response_json[animal_field.db_column] == "Horse"


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

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == first_row.id
    assert response_json[color_field.db_column] == "Blue"
    assert response_json[animal_field.db_column] == "Horse"


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

    response = api_client.post(
        url,
        {"current_record": 123},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[index.db_column] == "Index 123"


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

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == first_row.id
    assert response_json[color_field.db_column] == "Orange"
    assert response_json[animal_field.db_column] == f"{rows[1].id}"


@pytest.mark.django_db
@patch(
    "baserow.contrib.builder.data_providers.data_provider_types.FormDataProviderType.validate_data_chunk",
    side_effect=FormDataProviderChunkInvalidException,
)
def test_dispatch_workflow_action_with_invalid_form_data(
    mock_validate, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK, user=user
    )
    service = workflow_action.service.specific
    service.table = table
    service.save()
    field_mapping = service.field_mappings.create(
        field=field, value="get('form_data.17')"
    )

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )

    response = api_client.post(
        url,
        {
            "form_data": {
                "17": {"value": "", "type": "string", "isValid": False},
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_WORKFLOW_ACTION_IMPROPERLY_CONFIGURED",
        "detail": "The workflow_action configuration is incorrect: "
        f"Path error in formula for field {field.name}({field.id})",
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
        "row_id": "",
        "type": DeleteRowWorkflowActionType.service_type,
        "schema": None,
        "table_id": None,
        "context_data": None,
        "context_data_schema": None,
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
