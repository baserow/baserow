from django.urls import reverse
from django.utils import timezone

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.integrations.core.constants import RESPONSE_BODY_TYPE
from baserow.contrib.integrations.core.models import CoreResponseHeader


def get_url(uid):
    return reverse("api:http_trigger", kwargs={"webhook_uid": uid})


@pytest.mark.parametrize(
    "http_method",
    ["head", "options", "trace"],
)
@pytest.mark.django_db
def test_rejects_disallowed_methods(api_client, data_fixture, http_method):
    node = data_fixture.create_http_trigger_node()

    url = get_url(node.service.uid)
    resp = getattr(api_client, http_method)(url)

    assert resp.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_rejects_http_get_if_service_excludes_get(
    api_client, data_fixture, django_assert_num_queries
):
    node = data_fixture.create_http_trigger_node()
    node.service.exclude_get = True
    node.service.save()

    url = get_url(node.service.uid) + "?test=true"

    with django_assert_num_queries(1):
        resp = api_client.get(url)

    assert resp.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
@pytest.mark.parametrize(
    "http_method",
    ["get", "post", "put", "patch", "delete"],
)
def test_allows_valid_http_methods(api_client, data_fixture, http_method):
    node = data_fixture.create_http_trigger_node()

    url = get_url(node.service.uid) + "?test=true"
    resp = getattr(api_client, http_method)(url)

    assert resp.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db(transaction=True)
def test_http_trigger_with_response_node_returns_workflow_response(
    api_client, data_fixture
):
    trigger = data_fixture.create_http_trigger_node(
        service_kwargs={
            "response_timeout_seconds": 1,
        },
    )
    workflow = trigger.workflow
    workflow.state = WorkflowState.LIVE
    workflow.allow_test_run_until = timezone.now()
    workflow.save()
    response_node = data_fixture.create_core_response_action_node(
        workflow=workflow,
        service_kwargs={
            "status_code": HTTP_200_OK,
            "body_type": RESPONSE_BODY_TYPE.TEXT,
            "body": "'Hello'",
        },
    )
    CoreResponseHeader.objects.create(
        service=response_node.service.specific,
        key="X-Workflow",
        value="'done'",
    )

    url = get_url(trigger.service.uid) + "?test=true"
    resp = api_client.post(url)

    assert resp.status_code == HTTP_200_OK
    assert resp.content == b"Hello"
    assert resp["X-Workflow"] == "done"
