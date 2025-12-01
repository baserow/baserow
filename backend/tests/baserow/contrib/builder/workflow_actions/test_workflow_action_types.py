from collections import defaultdict
from unittest.mock import MagicMock, patch

import pytest

from baserow.contrib.builder.pages.service import PageService
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    LocalBaserowWorkflowActionType,
    LogoutWorkflowActionType,
    NotificationWorkflowActionType,
    OpenPageWorkflowActionType,
    RefreshDataSourceWorkflowActionType,
)
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.core.services.exceptions import InvalidServiceTypeDispatchSource
from baserow.core.utils import MirrorDict
from baserow.core.workflow_actions.registries import WorkflowActionType


def local_baserow_service_backed_workflow_actions():
    """
    Responsible for returning all workflow action types which are backed by a local
    baserow service.

    :return: A list of workflow action types backed by a local baserow service.
    """

    return [
        workflow_action_type
        for workflow_action_type in builder_workflow_action_type_registry.get_all()
        if issubclass(workflow_action_type.__class__, LocalBaserowWorkflowActionType)
    ]


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
def test_export_workflow_action(data_fixture, workflow_action_type: WorkflowActionType):
    page = data_fixture.create_builder_page()
    pytest_params = workflow_action_type.get_pytest_params(data_fixture)
    workflow_action = data_fixture.create_workflow_action(
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
def test_import_workflow_action(data_fixture, workflow_action_type: WorkflowActionType):
    page = data_fixture.create_builder_page()
    pytest_params = workflow_action_type.get_pytest_params(data_fixture)

    page_after_import = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page_after_import)

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


@pytest.mark.django_db
def test_export_import_upsert_row_workflow_action_type(data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Animal", "text"),
        ],
        rows=[],
    )
    integration = data_fixture.create_local_baserow_integration(user=user)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    duplicated_page = PageService().duplicate_page(user, page)
    data_source2 = duplicated_page.datasource_set.first()

    field = table.field_set.get(name="Animal")
    element = data_fixture.create_builder_button_element(page=page)
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration, table=table
    )
    field_mapping = service.field_mappings.create(
        field=field, value=f"get('data_source.{data_source.id}.{field.db_column}')"
    )
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK, service=service
    )

    workflow_action_type = workflow_action.get_type()
    exported = workflow_action_type.export_serialized(workflow_action)

    assert exported == {
        "id": workflow_action.id,
        "order": workflow_action.order,
        "type": workflow_action_type.type,
        "page_id": page.id,
        "element_id": element.id,
        "event": EventTypes.CLICK,
        "service": {
            "id": service.id,
            "integration_id": integration.id,
            "type": "local_baserow_upsert_row",
            "row_id": BaserowFormulaObject(
                formula="",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            ),
            "table_id": table.id,
            "field_mappings": [
                {
                    "field_id": field.id,
                    "value": field_mapping.value,
                    "enabled": True,
                }
            ],
            "sample_data": None,
        },
    }

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["builder_data_sources"] = {data_source.id: data_source2.id}

    new_workflow_action = workflow_action_type.import_serialized(
        page, exported, id_mapping
    )
    new_action_service = new_workflow_action.service

    assert new_workflow_action.id != exported["id"]
    assert new_workflow_action.event == exported["event"]
    assert new_workflow_action.page_id == exported["page_id"]
    assert new_workflow_action.element_id == exported["element_id"]

    assert new_workflow_action.service_id != exported["service"]["id"]
    assert new_action_service.row_id == exported["service"]["row_id"]
    assert new_action_service.table_id == exported["service"]["table_id"]
    assert new_action_service.integration_id == exported["service"]["integration_id"]

    field_mapping = service.field_mappings.get()
    assert (
        field_mapping.field_id == exported["service"]["field_mappings"][0]["field_id"]
    )
    assert field_mapping.value == exported["service"]["field_mappings"][0]["value"]

    # Ensure the service's field mapping value has the updated Data Source ID
    # in its formula.
    imported_field_mapping = new_workflow_action.service.field_mappings.all()[0]
    assert (
        imported_field_mapping.value["formula"]
        == f"get('data_source.{data_source2.id}.{field.db_column}')"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "local_baserow_builder_workflow_action_type",
    local_baserow_service_backed_workflow_actions(),
)
def test_builder_local_baserow_workflow_service_type_prepare_values_with_instance(
    local_baserow_builder_workflow_action_type,
    data_fixture,
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    workspace = page.builder.workspace
    element = data_fixture.create_builder_button_element(page=page)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    workflow_action = data_fixture.create_builder_workflow_service_action(
        local_baserow_builder_workflow_action_type.model_class,
        page=page,
        element=element,
        event=EventTypes.CLICK,
        user=user,
    )
    service = workflow_action.service.specific
    service.table = table
    service.save()
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()
    row2 = model.objects.create(**{f"field_{field.id}": "Cheese"})
    local_baserow_builder_workflow_action_type.prepare_values(
        {
            "service": {
                "row_id": row2.id,
                "table_id": table.id,
                "integration_id": integration.id,
            }
        },
        user,
        workflow_action,
    )
    assert service.row_id["formula"] == str(row2.id)
    assert service.table_id == table.id
    assert service.integration_id == integration.id


@patch(
    "baserow.contrib.builder.workflow_actions.workflow_action_types.BuilderWorkflowActionType.deserialize_property"
)
def test_refresh_data_source_returns_value_from_id_mapping(mock_deserialize):
    """
    Ensure value is returned from id_mapping if prop_name is 'data_source_id'
    and a value is provided.
    """

    action = RefreshDataSourceWorkflowActionType()
    mock_result = MagicMock()
    id_mapping = {"builder_data_sources": {"1": mock_result}}

    result = action.deserialize_property(
        "data_source_id",
        "1",
        id_mapping,
    )

    assert result is mock_result
    mock_deserialize.assert_not_called()


@patch(
    "baserow.contrib.builder.workflow_actions.workflow_action_types.BuilderWorkflowActionType.deserialize_property"
)
@pytest.mark.parametrize(
    "value,id_mapping",
    [
        # Both value and id_mapping are empty
        (
            "",
            {},
        ),
        # id_mapping is valid but value is empty
        (
            "",
            {
                "builder_data_sources": {"foo": "bar"},
            },
        ),
        # value is valid but id_mapping doesn't have matching value
        (
            "foo",
            {
                "builder_data_sources": {"baz": "bar"},
            },
        ),
    ],
)
def test_refresh_data_source_returns_value_from_super_method(
    mock_deserialize, value, id_mapping
):
    """Ensure value is returned from the parent class' deserialize_property method."""

    mock_result = MagicMock()
    mock_deserialize.return_value = mock_result
    action = RefreshDataSourceWorkflowActionType()

    args = ["data_source_id", value, id_mapping]
    result = action.deserialize_property(*args)

    assert result is mock_result
    mock_deserialize.assert_called_once_with(
        *args, files_zip=None, cache=None, storage=None
    )


@pytest.mark.django_db
def test_import_notification_workflow_action(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    workflow_action_type = NotificationWorkflowActionType()
    button_1 = data_fixture.create_builder_button_element(page=page)
    button_2 = data_fixture.create_builder_button_element(page=page)

    exported_workflow_action = data_fixture.create_notification_workflow_action(
        page=page,
        element=button_1,
        event=EventTypes.CLICK,
        title=f"get('data_source.{data_source_1.id}.field_1')",
        description=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = workflow_action_type.export_serialized(exported_workflow_action)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {
        "builder_data_sources": {data_source_1.id: data_source_2.id},
        "builder_page_elements": {button_1.id: button_2.id},
    }
    imported_workflow_action = workflow_action_type.import_serialized(
        page, serialized, id_mapping
    )

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_workflow_action.title["formula"] == expected_formula
    assert imported_workflow_action.description["formula"] == expected_formula


@pytest.mark.django_db
def test_import_open_page_workflow_action(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    workflow_action_type = OpenPageWorkflowActionType()
    button_1 = data_fixture.create_builder_button_element(page=page)
    button_2 = data_fixture.create_builder_button_element(page=page)

    exported_workflow_action = data_fixture.create_open_page_workflow_action(
        page=page,
        event=EventTypes.CLICK,
        element=button_1,
        navigate_to_url=f"get('data_source.{data_source_1.id}.field_1')",
        page_parameters=[
            {
                "name": "fooPageParam",
                "value": f"get('data_source.{data_source_1.id}.field_1')",
            },
        ],
        query_parameters=[
            {
                "name": "fooQueryParam",
                "value": f"get('data_source.{data_source_1.id}.field_2')",
            },
        ],
    )

    serialized = workflow_action_type.export_serialized(exported_workflow_action)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {
        "builder_data_sources": {data_source_1.id: data_source_2.id},
        "builder_page_elements": {button_1.id: button_2.id},
    }
    imported_workflow_action = workflow_action_type.import_serialized(
        page, serialized, id_mapping
    )

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    expected_query_formula = f"get('data_source.{data_source_2.id}.field_2')"
    assert imported_workflow_action.navigate_to_url["formula"] == expected_formula
    assert (
        imported_workflow_action.page_parameters[0]["value"]["formula"]
        == expected_formula
    )
    assert (
        imported_workflow_action.query_parameters[0]["value"]["formula"]
        == expected_query_formula
    )


@pytest.mark.parametrize(
    "workflow_action",
    [
        NotificationWorkflowActionType,
        OpenPageWorkflowActionType,
        LogoutWorkflowActionType,
        RefreshDataSourceWorkflowActionType,
    ],
)
def test_builder_workflow_action_type_dispatch(workflow_action):
    """Ensure the base dispatch() raises an exception."""

    instance = workflow_action()
    mock_workflow_action = MagicMock()
    mock_dispatch_context = MagicMock()

    with pytest.raises(InvalidServiceTypeDispatchSource) as e:
        instance.dispatch(mock_workflow_action, mock_dispatch_context)

    assert str(e.value) == "This service cannot be dispatched."
