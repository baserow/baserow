import json
from unittest.mock import patch

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.elements.models import (
    FormContainerElement,
    RecordSelectorElement,
)
from baserow.contrib.builder.workflow_actions.models import EventTypes


@pytest.mark.django_db
def test_record_selector_element_api_rejects_schema_property(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    record_selector_element = data_fixture.create_builder_element(
        RecordSelectorElement, user, page
    )

    url = reverse(
        "api:builder:element:list",
        kwargs={"page_id": record_selector_element.page.id},
    )
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    for element in response.json():
        assert "schema_property" not in element

    url = reverse(
        "api:builder:element:item",
        kwargs={"element_id": record_selector_element.id},
    )
    response = api_client.patch(
        url,
        {"fields": [{"schema_property": "INVALID"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert "schema_property" not in response.json()


@pytest.mark.django_db
def test_record_selector_element_form_submission(api_client, data_fixture):
    """
    Regression test to make sure record selector element resolves the record
    names properly when an upsert action is used.

    See: https://gitlab.com/baserow/baserow/-/issues/3030
    """

    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[["Peter"], ["Afonso"], ["Tsering"], ["Jérémie"]],
    )
    view = data_fixture.create_grid_view(user, table=table)
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=page.builder
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
    )
    form = data_fixture.create_builder_element(FormContainerElement, user, page)
    record_selector_element = data_fixture.create_builder_element(
        RecordSelectorElement,
        user=user,
        page=page,
        data_source=data_source,
        parent_element=form,
    )

    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        user=user,
        page=page,
        element=form,
        event=EventTypes.CLICK,
    )
    service = workflow_action.service.specific
    service.table = table
    service.field_mappings.create(
        field=fields[0], value=f"get('form_data.{record_selector_element.id}')"
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
            "all": {workflow_action.service.id: ["id", f"field_{fields[0].id}"]},
            "external": {workflow_action.service.id: ["id", f"field_{fields[0].id}"]},
        }
        payload = {
            "metadata": json.dumps(
                {
                    "form_data": {
                        # Select the first item from the record selector list
                        f"{record_selector_element.id}": rows[0].id,
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
    assert "id" in response.json()
    # The created item should have "field_1" set to the first item of the
    # record selector list
    assert response.json()[fields[0].name] == f"{rows[0].id}"
