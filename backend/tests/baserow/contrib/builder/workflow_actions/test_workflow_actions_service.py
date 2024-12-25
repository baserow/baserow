from django.http import HttpRequest

import pytest

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.workflow_actions.exceptions import (
    BuilderWorkflowActionCannotBeDispatched,
)
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
)
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    CreateRowWorkflowActionType,
    NotificationWorkflowActionType,
)
from baserow.core.exceptions import UserNotInWorkspace


@pytest.mark.django_db
def test_create_workflow_action(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action_type = NotificationWorkflowActionType()
    workflow_action = (
        BuilderWorkflowActionService()
        .create_workflow_action(
            user, workflow_action_type, page=page, element=element, event=event
        )
        .specific
    )

    assert workflow_action is not None
    assert workflow_action.element is element
    assert BuilderWorkflowAction.objects.count() == 1


@pytest.mark.django_db
def test_create_workflow_action_no_permissions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action_type = NotificationWorkflowActionType()

    with pytest.raises(UserNotInWorkspace):
        BuilderWorkflowActionService().create_workflow_action(
            user, workflow_action_type, page=page, element=element, event=event
        )


@pytest.mark.django_db
def test_delete_workflow_action(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    assert BuilderWorkflowAction.objects.count() == 1

    BuilderWorkflowActionService().delete_workflow_action(user, workflow_action)

    assert BuilderWorkflowAction.objects.count() == 0


@pytest.mark.django_db
def test_delete_workflow_action_no_permissions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    with pytest.raises(UserNotInWorkspace):
        BuilderWorkflowActionService().delete_workflow_action(user, workflow_action)


@pytest.mark.django_db
def test_update_workflow_action(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    element_changed = data_fixture.create_builder_button_element()

    workflow_action = BuilderWorkflowActionService().update_workflow_action(
        user, workflow_action, element=element_changed
    )

    workflow_action.refresh_from_db()
    assert workflow_action.element_id == element_changed.id


@pytest.mark.django_db
def test_update_workflow_action_change_type(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    updated_workflow_action = BuilderWorkflowActionService().update_workflow_action(
        user, workflow_action, type=CreateRowWorkflowActionType.type
    )

    assert workflow_action.id != updated_workflow_action.id
    assert workflow_action.order == updated_workflow_action.order
    assert workflow_action.event == updated_workflow_action.event
    assert workflow_action.page_id == updated_workflow_action.page_id
    assert workflow_action.element_id == updated_workflow_action.element_id


@pytest.mark.django_db
def test_update_workflow_action_no_permissions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    element_changed = data_fixture.create_builder_button_element()

    with pytest.raises(UserNotInWorkspace):
        BuilderWorkflowActionService().update_workflow_action(
            user, workflow_action, element=element_changed
        )


@pytest.mark.django_db
def test_get_workflow_action(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    workflow_action_fetched = BuilderWorkflowActionService().get_workflow_action(
        user, workflow_action.id
    )

    assert workflow_action_fetched.id == workflow_action.id


@pytest.mark.django_db
def test_get_workflow_action_no_permissions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    with pytest.raises(UserNotInWorkspace):
        BuilderWorkflowActionService().get_workflow_action(user, workflow_action.id)


@pytest.mark.django_db
def test_get_workflow_actions(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    def exclude_wa_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=workflow_action_one.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_wa_1

        [
            workflow_action_two_fetched,
        ] = BuilderWorkflowActionService().get_workflow_actions(user, page)

        assert workflow_action_two_fetched.id == workflow_action_two.id


@pytest.mark.django_db
def test_get_builder_workflow_actions(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page.builder)

    element = data_fixture.create_builder_button_element(page=page)
    element2 = data_fixture.create_builder_button_element(page=page2)

    event = EventTypes.CLICK
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )
    workflow_action_three = data_fixture.create_notification_workflow_action(
        page=page, element=element2, event=event
    )

    def exclude_wa_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=workflow_action_one.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_wa_1

        was = BuilderWorkflowActionService().get_builder_workflow_actions(
            user, page.builder
        )

        assert sorted([w.id for w in was]) == sorted(
            [workflow_action_two.id, workflow_action_three.id]
        )


@pytest.mark.django_db
def test_get_workflow_actions_no_permissions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    event = EventTypes.CLICK
    workflow_action_one = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=event
    )

    with pytest.raises(UserNotInWorkspace):
        BuilderWorkflowActionService().get_workflow_actions(user, page)


@pytest.mark.django_db
def test_order_workflow_actions(data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_button_element(user=user)
    workflow_action_one = data_fixture.create_notification_workflow_action(
        element=element, order=0
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        element=element,
        order=1,
    )

    BuilderWorkflowActionService().order_workflow_actions(
        user,
        element.page,
        [workflow_action_two.id, workflow_action_one.id],
        element=element,
    )

    workflow_action_one.refresh_from_db()
    workflow_action_two.refresh_from_db()

    assert workflow_action_one.order > workflow_action_two.order


@pytest.mark.django_db
def test_order_workflow_actions_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_button_element()
    workflow_action_one = data_fixture.create_notification_workflow_action(
        element=element, order=0
    )
    workflow_action_two = data_fixture.create_notification_workflow_action(
        element=element, order=1
    )

    with pytest.raises(UserNotInWorkspace):
        BuilderWorkflowActionService().order_workflow_actions(
            user,
            element.page,
            [workflow_action_two.id, workflow_action_one.id],
            element=element,
        )


@pytest.mark.django_db
def test_dispatch_action_with_incompatible_action(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK
    )
    dispatch_context = BuilderDispatchContext(HttpRequest(), page)
    with pytest.raises(BuilderWorkflowActionCannotBeDispatched):
        BuilderWorkflowActionService().dispatch_action(
            user, workflow_action, dispatch_context
        )


@pytest.mark.django_db
def test_dispatch_workflow_action_no_permissions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK, user=user
    )

    dispatch_context = BuilderDispatchContext(HttpRequest(), page)
    with pytest.raises(UserNotInWorkspace):
        BuilderWorkflowActionService().dispatch_action(
            user, workflow_action, dispatch_context
        )
