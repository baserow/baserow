import json
from collections import defaultdict

from django.http import HttpRequest
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.data_providers.data_provider_types import (
    CurrentRecordDataProviderType,
)
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.formula_property_extractor import (
    get_workflow_action_property_names,
)
from baserow.contrib.builder.tools.formulas import (
    current_record_of,
    page_formula_context,
)
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.core.formula import BaserowFormulaObject
from baserow.core.graph.types import GraphPointPosition
from baserow.core.utils import MirrorDict


@pytest.fixture(params=["choice", "record_selector"])
def change_action(data_fixture, request):
    user = data_fixture.create_user()
    draft = data_fixture.create_builder_application(user=user)
    builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(builder=draft, published_to=builder)
    page = data_fixture.create_builder_page(builder=builder)
    database = data_fixture.create_database_application(workspace=draft.workspace)
    records, record_fields, record_rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Record", "text")],
        rows=[["Alpha"], ["Beta"]],
    )
    options, _, option_rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Option", "text")],
        rows=[["First option"], ["Second option"], ["Selected option"]],
    )
    output, output_fields, _ = data_fixture.build_table(
        user=user, database=database, columns=[("Selected", "text")], rows=[]
    )
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    record_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=records, integration=integration
    )
    option_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=options, integration=integration
    )
    repeat = data_fixture.create_builder_repeat_element(
        page=page, data_source=record_source
    )
    element_kwargs = (
        {"data_source": option_source}
        if request.param == "record_selector"
        else {"options": [{"name": "Selected", "value": "selected"}]}
    )
    element = data_fixture.create_builder_element(
        type(element_type_registry.get(request.param)),
        page=page,
        reference_element=repeat,
        position=GraphPointPosition.CHILD,
        required=True,
        **element_kwargs,
    )
    selected = (
        str(option_rows[2].id) if request.param == "record_selector" else "selected"
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration, table=output
    )
    service.field_mappings.create(
        field=output_fields[0],
        value=(
            f"concat(get('current_record.{record_fields[0].db_column}'), "
            f"':', get('form_data.{element.id}'))"
        ),
    )
    action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=EventTypes.CHANGE, service=service
    )
    return {
        "user": user,
        "page": page,
        "element": element,
        "record_source": record_source,
        "option_source": option_source,
        "record_field": record_fields[0],
        "record": record_rows[1],
        "output": output,
        "output_field": output_fields[0],
        "action": action,
        "selected": selected,
    }


@pytest.mark.django_db
def test_public_change_action_reads_new_value_and_enclosing_record(
    api_client, change_action
):
    fixture = change_action
    element = fixture["element"]
    response = api_client.post(
        reverse(
            "api:builder:workflow_action:dispatch",
            kwargs={"workflow_action_id": fixture["action"].id},
        ),
        {
            "metadata": {
                "data_source": {"element": element.id},
                "form_data": {str(element.id): fixture["selected"]},
                "current_record": {
                    "index_path": [1],
                    "record_id": fixture["record"].id,
                },
            }
        },
        format="json",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert list(
        fixture["output"]
        .get_model()
        .objects.values_list(fixture["output_field"].db_column, flat=True)
    ) == [f"Beta:{fixture['selected']}"]


@pytest.mark.django_db
def test_change_action_formula_context_reads_repeat_schema(change_action):
    fixture = change_action
    context = page_formula_context(fixture["page"])
    with current_record_of(context, "action", fixture["action"]):
        path_context = context.path_context()
        assert path_context.current_record == fixture["record_source"].id
        assert path_context.current_record_is_row
        assert str(fixture["element"].id) in path_context.form_inputs


@pytest.mark.django_db
def test_change_action_import_remaps_enclosing_record_and_form_input(
    data_fixture, change_action
):
    fixture = change_action
    page = fixture["page"]
    action = data_fixture.create_notification_workflow_action(
        page=page,
        element=fixture["element"],
        event=EventTypes.CHANGE,
        title=BaserowFormulaObject.create(
            f"get('current_record.{fixture['record_field'].db_column}')"
        ),
        description=BaserowFormulaObject.create(
            f"get('form_data.{fixture['element'].id}')"
        ),
    )
    properties = get_workflow_action_property_names([action], {})
    assert properties["external"] == {
        fixture["record_source"].service_id: [fixture["record_field"].db_column]
    }

    imported_page = data_fixture.create_builder_page(builder=page.builder)
    imported_table, imported_fields, _ = data_fixture.build_table(
        user=fixture["user"],
        database=fixture["record_field"].table.database,
        columns=[("Imported record", "text")],
        rows=[["Imported Alpha"]],
    )
    imported_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=imported_page,
        table=imported_table,
        integration=fixture["record_source"].service.integration,
    )
    imported_options = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=imported_page,
        table=fixture["option_source"].service.specific.table,
        integration=fixture["option_source"].service.integration,
    )
    repeat = data_fixture.create_builder_repeat_element(
        page=imported_page, data_source=imported_source
    )
    kwargs = (
        {"data_source": imported_options}
        if fixture["element"].get_type().type == "record_selector"
        else {}
    )
    imported_element = data_fixture.create_builder_element(
        type(fixture["element"].get_type()),
        page=imported_page,
        reference_element=repeat,
        position=GraphPointPosition.CHILD,
        **kwargs,
    )
    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["builder_page_elements"] = {fixture["element"].id: imported_element.id}
    id_mapping["database_fields"] = {fixture["record_field"].id: imported_fields[0].id}
    id_mapping["builder_data_sources"] = {
        fixture["record_source"].id: imported_source.id,
        fixture["option_source"].id: imported_options.id,
    }
    imported = action.get_type().import_serialized(
        imported_page, action.get_type().export_serialized(action), id_mapping
    )

    assert imported.event == EventTypes.CHANGE
    assert imported.element_id == imported_element.id
    assert imported.title["formula"] == (
        f"get('current_record.{imported_fields[0].db_column}')"
    )
    assert imported.description["formula"] == f"get('form_data.{imported_element.id}')"
    assert get_workflow_action_property_names([imported], {})["external"] == {
        imported_source.service_id: [imported_fields[0].db_column]
    }


@pytest.mark.django_db
def test_root_change_action_has_no_current_record(data_fixture, change_action):
    fixture = change_action
    kwargs = (
        {"data_source": fixture["option_source"]}
        if fixture["element"].get_type().type == "record_selector"
        else {}
    )
    root_input = data_fixture.create_builder_element(
        type(fixture["element"].get_type()), page=fixture["page"], **kwargs
    )
    action = data_fixture.create_notification_workflow_action(
        page=fixture["page"], element=root_input, event=EventTypes.CHANGE
    )
    request = HttpRequest()
    request.user = fixture["user"]
    request.data = {
        "metadata": json.dumps({"current_record": {"index_path": [0], "record_id": 1}})
    }
    context = BuilderDispatchContext(request, fixture["page"], workflow_action=action)

    assert CurrentRecordDataProviderType().get_data_chunk(context, ["id"]) is None
