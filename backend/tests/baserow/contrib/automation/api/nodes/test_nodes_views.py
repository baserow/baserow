from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.test_utils.helpers import AnyInt, AnyStr

API_URL_BASE = "api:automation:nodes"
API_URL_LIST = f"{API_URL_BASE}:list"
API_URL_ITEM = f"{API_URL_BASE}:item"


@pytest.mark.django_db
def test_create_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(
        user=user, name="test"
    )
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"type": "row_created"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert workflow.automation_workflow_nodes.count() == 1


@pytest.mark.django_db
def test_create_node_invalid_body(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(
        user=user, name="test"
    )
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"foo": "bar"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        'detail': {                                                                            
        'type': [                                                                            
            {                                                                                  
                'code': 'required',                                                              
                'error': 'This field is required.',                                              
            },                                                                                 
        ],                                                                                   
        },                                                                                     
        'error': 'ERROR_REQUEST_BODY_VALIDATION',                                              
    }


@pytest.mark.django_db
def test_create_node_invalid_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(
        user=user, name="test"
    )
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": 999})
    response = api_client.post(
        url,
        {"type": "row_created"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        'detail': 'The requested workflow does not exist.',
        'error': 'ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST',
    }


@pytest.mark.django_db
def test_get_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(
        user=user
    )

    url = reverse(API_URL_LIST, kwargs={"workflow_id": node.workflow.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {                                                                            
            'id': node.id,                                                                   
            'order': AnyStr(),
            'previous_node_output': '',                                                
            'service': AnyInt(),
            'type': 'row_created',                                                     
            'workflow': node.workflow.id,
        },                                                                           
    ]


@pytest.mark.django_db
def test_get_node_invalid_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_LIST, kwargs={"workflow_id": 999})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
