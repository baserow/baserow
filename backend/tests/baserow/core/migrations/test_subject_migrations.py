from importlib import import_module

import pytest
from django.db import connection


@pytest.mark.once_per_day_in_ci
def test_subject_backfill_missing_profiles_and_retries(migrator, monkeypatch):
    """Backfill missing profiles in multiple batches and reconcile overlapping writes."""
    migration = import_module("baserow.core.migrations.0137_backfill_subjects")
    monkeypatch.setattr(migration, "BATCH_SIZE", 2)
    old = migrator.migrate([("core", "0135_workspaceinvitationlink_scope")])
    User = old.apps.get_model("auth", "User")
    Profile = old.apps.get_model("core", "UserProfile")
    users = [User.objects.create(username=f"legacy-{i}", first_name=f"User {i}", email=f"{i}@example.com") for i in range(5)]
    Profile.objects.create(user_id=users[0].pk)
    Workspace = old.apps.get_model("core", "Workspace")
    Agent = old.apps.get_model("core", "Agent")
    workspace = Workspace.objects.create(name="Legacy Agents")
    agent_ids = [Agent.objects.create(workspace=workspace, name=f"Agent {i}").id for i in range(2)]
    state = migrator.migrate([("core", "0137_backfill_subjects")])
    Subject = state.apps.get_model("core", "Subject")
    Profile = state.apps.get_model("core", "UserProfile")
    Agent = state.apps.get_model("core", "Agent")
    agents = list(Agent.objects.filter(pk__in=agent_ids).order_by("pk"))
    assert len({agent.uid for agent in agents}) == 2
    for agent in agents:
        assert agent.uid.version == 4
        assert Subject.objects.get(pk=agent.subject_id).uid == str(agent.uid)
    for user in users:
        subject = Subject.objects.get(pk=user.pk)
        assert (subject.name, subject.uid, subject.type) == (user.first_name, user.email, "auth.User")
        assert Profile.objects.get(user_id=user.pk).subject_id == user.pk
    # An old worker creates/renames/deletes users after the initial backfill.
    User.objects.filter(pk=users[0].pk).update(first_name="Overlap rename")
    newcomer = User.objects.create(username="overlap", first_name="New", email="new@example.com")
    User.objects.filter(pk=users[1].pk).delete()
    Agent.objects.filter(pk=agents[0].pk).update(name="Overlap Agent", trashed=True)
    Agent.objects.filter(pk=agents[1].pk).delete()
    assert Subject.objects.get(pk=users[0].pk).name == users[0].first_name
    with connection.schema_editor(atomic=False) as schema_editor:
        migration.backfill_subjects(state.apps, schema_editor)
        migration.backfill_subjects(state.apps, schema_editor)
    assert Subject.objects.get(pk=users[0].pk).name == "Overlap rename"
    assert Subject.objects.get(pk=users[1].pk).state == "retained"
    assert Profile.objects.get(user_id=newcomer.pk).subject_id == newcomer.pk
    renamed_agent = Subject.objects.get(pk=agents[0].subject_id)
    assert (renamed_agent.name, renamed_agent.state) == ("Overlap Agent", "trashed")
    assert Subject.objects.get(pk=agents[1].subject_id).state == "retained"
