import pytest


@pytest.mark.once_per_day_in_ci
def test_0073_deletes_rows_whose_subject_is_a_legacy_agent(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate([("baserow_enterprise", "0072_html_element")])
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Role = old_state.apps.get_model("baserow_enterprise", "Role")
    RoleAssignment = old_state.apps.get_model("baserow_enterprise", "RoleAssignment")
    Team = old_state.apps.get_model("baserow_enterprise", "Team")
    TeamSubject = old_state.apps.get_model("baserow_enterprise", "TeamSubject")

    agent_type, _ = ContentType.objects.get_or_create(app_label="core", model="agent")
    user_type, _ = ContentType.objects.get_or_create(app_label="auth", model="user")
    workspace = Workspace.objects.create(name="Legacy")
    role = Role.objects.create(uid="legacy", name="Legacy")
    team = Team.objects.create(name="Legacy", workspace=workspace)
    for subject_type in (agent_type, user_type):
        RoleAssignment.objects.create(
            subject_id=1,
            subject_type=subject_type,
            role=role,
            workspace=workspace,
            scope_id=workspace.id,
            scope_type=user_type,
        )
        TeamSubject.objects.create(subject_id=1, subject_type=subject_type, team=team)

    migrator.migrate([("baserow_enterprise", "0073_delete_legacy_agent_subjects")])

    for model in (RoleAssignment, TeamSubject):
        remaining = model.objects.values_list("subject_type_id", flat=True)
        assert list(remaining) == [user_type.id]
