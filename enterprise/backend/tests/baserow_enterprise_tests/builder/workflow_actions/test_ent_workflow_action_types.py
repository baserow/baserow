from collections import defaultdict

import pytest

from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.utils import MirrorDict
from baserow.core.workflow_actions.registries import WorkflowActionType


def pytest_generate_tests(metafunc):
    if "workflow_action_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "workflow_action_type",
            [
                pytest.param(e, id=e.type)
                for e in builder_workflow_action_type_registry.get_all()
            ],
        )


@pytest.mark.django_db
def test_export_workflow_action(
    enterprise_data_fixture, workflow_action_type: WorkflowActionType
):
    page = enterprise_data_fixture.create_builder_page()
    pytest_params = workflow_action_type.get_pytest_params(enterprise_data_fixture)
    workflow_action = enterprise_data_fixture.create_workflow_action(
        workflow_action_type.model_class, page=page, **pytest_params
    )

    exported = workflow_action_type.export_serialized(workflow_action)

    assert exported["id"] == workflow_action.id
    assert exported["type"] == workflow_action_type.type

    serialized_pytest_params = workflow_action_type.get_pytest_params_serialized(
        pytest_params
    )
    for key, value in serialized_pytest_params.items():
        assert exported[key] == value


@pytest.mark.django_db
def test_import_workflow_action(
    enterprise_data_fixture, workflow_action_type: WorkflowActionType
):
    page = enterprise_data_fixture.create_builder_page()
    pytest_params = workflow_action_type.get_pytest_params(enterprise_data_fixture)

    page_after_import = enterprise_data_fixture.create_builder_page()
    element = enterprise_data_fixture.create_builder_button_element(
        page=page_after_import
    )

    serialized = {
        "id": 9999,
        "type": workflow_action_type.type,
        "page_id": 41,
        "element_id": 42,
        "order": 0,
        "event": EventTypes.CLICK,
    }
    serialized.update(workflow_action_type.get_pytest_params_serialized(pytest_params))

    id_mapping = defaultdict(MirrorDict)
    id_mapping["builder_pages"] = {41: page_after_import.id}
    id_mapping["builder_page_elements"] = {42: element.id}

    workflow_action = workflow_action_type.import_serialized(
        page, serialized, id_mapping
    )

    assert workflow_action.id != 9999
    assert isinstance(workflow_action, workflow_action_type.model_class)

    for key, value in pytest_params.items():
        if key != "service":
            assert getattr(workflow_action, key) == value
