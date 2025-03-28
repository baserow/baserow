import pytest

from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
    NotificationWorkflowAction,
)


def test_builder_workflow_action_is_collection_field_action():
    assert not BuilderWorkflowAction.is_collection_field_action("")
    assert not BuilderWorkflowAction.is_collection_field_action("click")
    assert BuilderWorkflowAction.is_collection_field_action(
        "f1594a0a-3ff0-4c8c-a175-992039b11411_click"
    )


@pytest.mark.django_db
def test_builder_workflow_action_target(data_fixture):
    page = data_fixture.create_builder_page()
    table_element = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {
                "name": "FieldA",
                "type": "button",
                "config": {"value": f"'Click me')"},
            },
        ],
    )
    collection_field = table_element.fields.get()
    collection_field_workflow_action = data_fixture.create_workflow_action(
        NotificationWorkflowAction,
        page=page,
        element=table_element,
        event=f"{collection_field.uid}_click",
    )

    assert collection_field_workflow_action.target == collection_field

    button_element = data_fixture.create_builder_button_element(page=page)
    button_element_workflow_action = data_fixture.create_workflow_action(
        NotificationWorkflowAction,
        page=page,
        element=button_element,
        event=EventTypes.CLICK,
    )

    assert button_element_workflow_action.target == button_element
