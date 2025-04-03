from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction


def test_builder_workflow_action_is_dynamic_event():
    assert not BuilderWorkflowAction.is_dynamic_event("")
    assert not BuilderWorkflowAction.is_dynamic_event("click")
    assert BuilderWorkflowAction.is_dynamic_event(
        "f1594a0a-3ff0-4c8c-a175-992039b11411_click"
    )
