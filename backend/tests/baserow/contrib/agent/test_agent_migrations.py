import pytest


@pytest.mark.once_per_day_in_ci
def test_0016_clears_run_as_bindings_to_legacy_agents(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate(
        [("agent", "0015_agent_shared_conversations"), ("core", "0138_user_identities")]
    )
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    AgentApplication = old_state.apps.get_model("agent", "AgentApplication")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="agent", model="agentapplication"
    )
    workspace = Workspace.objects.create(name="Legacy")
    for subject_type in ("core.Agent", "auth.User"):
        AgentApplication.objects.create(
            workspace=workspace,
            name=subject_type,
            order=1,
            content_type=content_type,
            run_as_subject_type=subject_type,
            run_as_subject_id=1,
        )

    migrator.migrate([("agent", "0016_clear_legacy_agent_run_as")])

    bindings = AgentApplication.objects.order_by("id").values_list(
        "run_as_subject_type", "run_as_subject_id"
    )
    assert list(bindings) == [(None, None), ("auth.User", 1)]
