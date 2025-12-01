import json
from unittest.mock import MagicMock

import pytest

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.workflow_actions.exceptions import (
    WorkflowActionNotInElement,
)
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
)
from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    NotificationWorkflowActionType,
    OpenPageWorkflowActionType,
)
from baserow.core.services.models import Service
from baserow.test_utils.helpers import AnyInt, AnyStr


@pytest.mark.django_db
def test_create_workflow_action(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action_type = NotificationWorkflowActionType()
    workflow_action = (
        BuilderWorkflowActionHandler()
        .create_workflow_action(
            workflow_action_type, page=page, element=element, event=event
        )
        .specific
    )

    assert workflow_action is not None
    assert workflow_action.element is element
    assert BuilderWorkflowAction.objects.count() == 1


@pytest.mark.django_db
def test_delete_workflow_action(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    assert BuilderWorkflowAction.objects.count() == 1

    BuilderWorkflowActionHandler().delete_workflow_action(workflow_action)

    assert BuilderWorkflowAction.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_delete_workflow_action_with_service(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=event
    )

    assert BuilderWorkflowAction.objects.count() == 1
    assert Service.objects.count() == 1

    BuilderWorkflowActionHandler().delete_workflow_action(workflow_action)

    assert BuilderWorkflowAction.objects.count() == 0
    assert Service.objects.count() == 0


@pytest.mark.django_db
def test_update_workflow_action(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    element_changed = data_fixture.create_builder_button_element()

    workflow_action = BuilderWorkflowActionHandler().update_workflow_action(
        workflow_action, element=element_changed
    )

    workflow_action.refresh_from_db()
    assert workflow_action.element_id == element_changed.id


@pytest.mark.django_db
def test_update_workflow_action_type_switching(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    workflow_action_changed = BuilderWorkflowActionHandler().update_workflow_action(
        workflow_action, type=OpenPageWorkflowActionType.type
    )

    assert workflow_action_changed.get_type().type == OpenPageWorkflowActionType.type
    assert workflow_action_changed.event == event
    assert workflow_action_changed.page_id == page.id
    assert workflow_action_changed.element_id == element.id


@pytest.mark.django_db
def test_get_workflow_action(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    workflow_action_fetched = BuilderWorkflowActionHandler().get_workflow_action(
        workflow_action.id
    )

    assert workflow_action_fetched.id == workflow_action.id


@pytest.mark.django_db
def test_get_workflow_actions(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    [
        workflow_action_one_fetched,
        workflow_action_two_fetched,
    ] = BuilderWorkflowActionHandler().get_workflow_actions(page)

    assert workflow_action_one_fetched.id == workflow_action_one.id
    assert workflow_action_two_fetched.id == workflow_action_two.id


@pytest.mark.django_db
def test_get_builder_workflow_actions(data_fixture):
    page = data_fixture.create_builder_page()
    page2 = data_fixture.create_builder_page(builder=page.builder)
    element = data_fixture.create_builder_button_element(page=page)
    element2 = data_fixture.create_builder_button_element(page=page2)

    event = EventTypes.CLICK
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, element=element2, event=event
    )

    data_fixture.create_notification_workflow_action(event=event)

    workflow_actions = BuilderWorkflowActionHandler().get_workflow_actions(page)

    assert sorted([w.id for w in workflow_actions]) == sorted(
        [workflow_action_one.id, workflow_action_two.id]
    )


@pytest.mark.django_db
def test_order_workflow_actions(data_fixture):
    element = data_fixture.create_builder_button_element()
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=element.page, element=element, order=1
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=element.page, element=element, order=2
    )

    assert BuilderWorkflowActionHandler().order_workflow_actions(
        element.page,
        [workflow_action_two.id, workflow_action_one.id],
        element=element,
    ) == [
        workflow_action_two.id,
        workflow_action_one.id,
    ]

    workflow_action_one.refresh_from_db()
    workflow_action_two.refresh_from_db()

    assert workflow_action_one.order == 2
    assert workflow_action_two.order == 1


@pytest.mark.django_db
def test_order_workflow_action_not_in_element(data_fixture):
    element = data_fixture.create_builder_button_element()
    element_unrelated = data_fixture.create_builder_button_element()
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=element.page, element=element, order=1
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=element_unrelated.page, order=2
    )

    base_qs = BuilderWorkflowAction.objects.filter(id=workflow_action_two.id)

    with pytest.raises(WorkflowActionNotInElement):
        BuilderWorkflowActionHandler().order_workflow_actions(
            element.page,
            [workflow_action_two.id, workflow_action_one.id],
            element=element,
            base_qs=base_qs,
        )


@pytest.mark.django_db
def test_order_workflow_actions_different_scopes(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    page_workflow_action = BuilderWorkflowActionHandler().create_workflow_action(
        NotificationWorkflowActionType(), page=page
    )
    element_workflow_action = BuilderWorkflowActionHandler().create_workflow_action(
        NotificationWorkflowActionType(), page=page, element_id=element.id
    )

    assert page_workflow_action.order == element_workflow_action.order


@pytest.mark.django_db
def test_dispatch_workflow_action_doesnt_trigger_formula_recursion(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
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
    page = data_fixture.create_builder_page(builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user, authorized_user=user
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        integration=integration,
        page=page,
        table=table,
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    service.field_mappings.create(
        field=fields[0],
        value=f'concat(get("data_source.{data_source.id}.0.{fields[0].db_column}"), '
        f'get("data_source.{data_source.id}.0.{fields[1].db_column}"))',
    )
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, service=service, element=element, event=EventTypes.CLICK
    )

    fake_request = MagicMock()
    fake_request.data = {"metadata": json.dumps({})}

    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    result = BuilderWorkflowActionHandler().dispatch_workflow_action(
        workflow_action, dispatch_context
    )

    assert result.data == {
        "id": AnyInt(),
        "order": AnyStr(),
        "Name": "AudiOrange",
        "My Color": None,
    }
