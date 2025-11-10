from django.contrib.contenttypes.models import ContentType

import pytest

from baserow.contrib.automation.nodes.models import get_default_node_content_type


@pytest.mark.django_db
def test_automation_node_get_parent(data_fixture):
    node = data_fixture.create_automation_node()

    result = node.get_parent()

    assert result == node.workflow


@pytest.mark.django_db
def test_get_default_node_content_type(data_fixture):
    result = get_default_node_content_type()
    node = data_fixture.create_automation_node()

    assert isinstance(result, ContentType)
    assert isinstance(node.content_type, ContentType)


@pytest.mark.django_db
def test_get_previous_service_outputs(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()

    router_a = data_fixture.create_core_router_action_node(
        workflow=workflow, label="router a"
    )
    router_a_edge_1 = data_fixture.create_core_router_service_edge(
        service=router_a.service,
        label="Router A, Edge 1",
        condition="'true'",
        skip_output_node=True,
    )
    data_fixture.create_core_router_service_edge(
        service=router_a.service,
        label="Router A, Edge 2",
        condition="'false'",
        skip_output_node=True,
    )

    router_b = data_fixture.create_core_router_action_node(
        workflow=workflow,
        reference_node=router_a,
        position="south",
        output=router_a_edge_1.uid,
        label="router b",
    )

    data_fixture.create_core_router_service_edge(
        service=router_b.service,
        label="Router B, Edge 1",
        condition="'false'",
        skip_output_node=True,
    )
    router_b_edge_2 = data_fixture.create_core_router_service_edge(
        service=router_b.service,
        label="Router B, Edge 2",
        condition="'true'",
        skip_output_node=True,
    )

    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        reference_node=router_a,
        position="south",
        output="",
        label="action a",
    )

    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        reference_node=router_b,
        position="south",
        output="",
        label="action b",
    )
    node_c_2 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        reference_node=router_b,
        position="south",
        output=router_b_edge_2.uid,
        label="action b on edge",
    )

    # TODO add a container

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router a"]}},
            "router a": {"next": {"": ["action a"], "Router A, Edge 1": ["router b"]}},
            "action a": {},
            "router b": {
                "next": {"": ["action b"], "Router B, Edge 2": ["action b on edge"]}
            },
            "action b": {},
            "action b on edge": {},
        }
    )

    result = node_c_2.get_previous_service_outputs()

    assert result == {
        trigger.service_id: "",
        router_a.service_id: str(router_a_edge_1.uid),
        router_b.service_id: str(router_b_edge_2.uid),
    }
