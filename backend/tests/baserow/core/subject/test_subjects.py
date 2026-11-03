from django.db import transaction

import pytest

from baserow.core.agents.handler import AgentHandler
from baserow.core.models import Agent, Subject, SubjectRollout, User
from baserow.core.subject.export import export_subject, import_subject
from baserow.core.subject.handler import (
    eligible_subjects,
    resolve_actor,
    subject_for_actor,
)


@pytest.mark.django_db
def test_human_identity_save_and_delete(data_fixture):
    """Account edits and account reuse preserve independent attribution."""
    user = data_fixture.create_user(first_name="Original", email="original@example.com")
    subject = user.profile.subject
    assert subject.id == user.id
    user.first_name, user.email = "Renamed", "renamed@example.com"
    user.save(update_fields=["first_name", "email"])
    subject.refresh_from_db()
    assert (subject.name, subject.uid) == ("Renamed", "renamed@example.com")
    user.delete()
    subject.refresh_from_db()
    assert (subject.state, subject.uid) == ("retained", "renamed@example.com")
    assert resolve_actor(subject) is None
    replacement = data_fixture.create_user(email="renamed@example.com")
    assert replacement.id != subject.id


@pytest.mark.django_db
def test_agent_identity_gate_and_lifecycle(data_fixture):
    """Agent IDs stay independent while lifecycle changes retain display identity."""
    from baserow.core.registries import subject_type_registry

    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user()
    agent = AgentHandler().create_agent(workspace, name="Assistant")
    following_user = data_fixture.create_user()
    assert user.id < agent.subject_id < following_user.id
    assert agent.subject.uid == str(agent.uid)
    subject_type = subject_type_registry.get_by_model(agent)
    assert subject_type.get_persistent_subject(agent).id == agent.subject_id
    assert subject_type.get_persistent_subject(agent, for_write=True) is None
    assert subject_for_actor(agent, for_write=True) is None
    SubjectRollout.objects.create(pk=1, agent_references_enabled=True)
    assert (
        subject_type.get_persistent_subject(agent, for_write=True).id
        == agent.subject_id
    )
    assert subject_for_actor(agent, for_write=True).id == agent.subject_id
    assert eligible_subjects(workspace.id).filter(pk=agent.subject_id).exists()
    agent.name, agent.trashed = "Renamed", True
    agent.save(update_fields=["name", "trashed"])
    subject = Subject.objects.get(pk=agent.subject_id)
    assert (subject.name, subject.state) == ("Renamed", "trashed")
    assert (
        subject_type.get_persistent_subject(
            Agent.objects_and_trash.get(pk=agent.pk), for_write=True
        )
        is None
    )
    assert resolve_actor(subject) is None
    assert not eligible_subjects(workspace.id).filter(pk=subject.id).exists()
    agent.trashed = False
    agent.save(update_fields=["trashed"])
    subject.refresh_from_db()
    assert resolve_actor(subject).id == agent.id
    agent.delete()
    subject.refresh_from_db()
    assert subject.state == "retained"


@pytest.mark.django_db
def test_identity_changes_roll_back_with_actor(data_fixture):
    """Actor and cached identity updates commit or roll back together."""
    user = data_fixture.create_user(first_name="Original")
    with pytest.raises(ValueError), transaction.atomic():
        user.first_name = "Rolled back"
        user.save(update_fields=["first_name"])
        raise ValueError()
    assert Subject.objects.get(pk=user.id).name == "Original"


@pytest.mark.django_db
def test_import_identity_does_not_create_agent_or_match_foreign_user(data_fixture):
    """Imports retain foreign attribution without manufacturing execution privileges."""
    workspace = data_fixture.create_workspace()
    foreign = data_fixture.create_user()
    value = export_subject(foreign.profile.subject)
    cache = {}
    retained = import_subject(value, workspace.id, cache)
    assert retained.id != foreign.id
    assert retained.state == "retained"
    assert import_subject(value, workspace.id, cache).id == retained.id
    assert resolve_actor(retained) is None
    assert import_subject(foreign.email, workspace.id, {}) is None
    agent_value = {
        "subject": {
            "version": 1,
            "type": "core.Agent",
            "uid": "stable-uuid",
            "name": "Imported",
        }
    }
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        import_subject(agent_value, workspace.id, {})
    SubjectRollout.objects.create(pk=1, agent_references_enabled=True)
    retained_agent = import_subject(agent_value, workspace.id, {})
    assert retained_agent.state == "retained"
    assert not Agent.objects.filter(subject=retained_agent).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_actor_creation_uses_one_sequence(data_fixture):
    """Concurrent actor creation cannot reuse a human or Agent identity ID."""
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections

    workspace = data_fixture.create_workspace()

    def create_actor(index):
        """Create one independently committed actor from a worker connection."""
        close_old_connections()
        try:
            if index % 2:
                agent = Agent.objects.create(
                    workspace_id=workspace.id, name=f"Agent {index}"
                )
                return agent.subject_id
            user = User.objects.create(
                username=f"concurrent-{index}", email=f"{index}@example.com"
            )
            assert Subject.objects.get(pk=user.pk).type == "auth.User"
            return user.pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(create_actor, range(12)))
    assert len(set(ids)) == 12
    assert Subject.objects.filter(pk__in=ids).count() == 12


@pytest.mark.django_db
def test_missing_profile_link_fails_closed_without_losing_attribution(data_fixture):
    """Deleting a profile keeps the identity but removes executable resolution."""
    user = data_fixture.create_user(first_name="Retained attribution")
    subject = user.profile.subject
    user.profile.delete()
    subject.refresh_from_db()
    assert subject.state == "retained"
    assert subject.name == "Retained attribution"
    assert User.objects.filter(pk=user.pk).exists()
    from baserow.core.registries import subject_type_registry

    fresh_user = User.objects.get(pk=user.pk)
    assert (
        subject_type_registry.get_by_model(fresh_user).get_persistent_subject(
            fresh_user, for_write=True
        )
        is None
    )
    assert subject_for_actor(fresh_user, for_write=True) is None
    assert resolve_actor(subject) is None


@pytest.mark.django_db(transaction=True)
def test_reconciliation_repairs_missing_profiles_before_activation(data_fixture):
    """Explicit activation repairs links and preserves independent Agent IDs."""
    from django.core.management import call_command

    from baserow.core.models import UserProfile

    user = data_fixture.create_user(first_name="Reconciled")
    workspace = data_fixture.create_workspace(user=user)
    agent = AgentHandler().create_agent(workspace, name="Reconciled Agent")
    user.profile.delete()
    call_command("reconcile_subjects", enable_agent_references=True)
    assert UserProfile.objects.get(user_id=user.id).subject_id == user.id
    assert SubjectRollout.objects.get(pk=1).agent_references_enabled is True
    assert (
        subject_for_actor(Agent.objects.get(pk=agent.pk), for_write=True).id
        == agent.subject_id
    )


@pytest.mark.django_db
def test_registered_identity_type_controls_selection_import_and_display(
    data_fixture, monkeypatch, django_assert_num_queries
):
    """An extension identity participates through SubjectType without consumer edits."""
    from django.core.exceptions import ValidationError
    from django.db.models import Q

    from baserow.core.registries import subject_type_registry
    from baserow.core.subject.export import human_readable_subject
    from baserow.core.subject.handler import allocate_subject_id
    from baserow.core.subjects import AnonymousUserSubjectType

    workspace = data_fixture.create_workspace()

    class ExternalSubjectType(AnonymousUserSubjectType):
        type = "test.External"
        supports_persistent_subjects = True
        enabled = True

        def persistent_subject_references_enabled(self):
            return self.enabled

        def get_persistent_subject_workspace_filter(
            self, workspace_id, *, selectable=True
        ):
            return Q(uid="external") if workspace_id == workspace.id else Q(pk__in=[])

        def export_persistent_subject(self, subject):
            return {
                **super().export_persistent_subject(subject),
                "name": f"Exported: {subject.name}",
            }

        def import_persistent_subject(self, identity, workspace_id, cache):
            cache["external_import_called"] = True
            return super().import_persistent_subject(identity, workspace_id, cache)

        def get_persistent_subject_export_value(self, subject, *, include_name=True):
            return f"External: {subject.name}"

    subject_type = ExternalSubjectType()
    monkeypatch.setitem(subject_type_registry.registry, subject_type.type, subject_type)
    identity = Subject.objects.create(
        id=allocate_subject_id(),
        type=subject_type.type,
        name="Extension",
        uid="external",
    )
    assert eligible_subjects(workspace.id).get(pk=identity.pk).id == identity.pk
    assert human_readable_subject(identity) == "External: Extension"
    assert export_subject(identity)["subject"] == {
        "version": 1,
        "type": subject_type.type,
        "uid": "external",
        "name": "Exported: Extension",
    }
    assert identity.name == "Extension"
    cache = {}
    assert (
        import_subject(export_subject(identity), workspace.id, cache).id == identity.pk
    )
    assert cache["external_import_called"] is True
    with django_assert_num_queries(0):
        assert (
            import_subject(export_subject(identity), workspace.id, cache).id
            == identity.pk
        )
    subject_type.enabled = False
    assert not eligible_subjects(workspace.id).filter(pk=identity.pk).exists()
    with pytest.raises(ValidationError):
        import_subject(export_subject(identity), workspace.id, {})


@pytest.mark.django_db
def test_registered_permission_only_type_cannot_be_imported(data_fixture):
    """Registry membership alone does not permit creating retained field identities."""
    from baserow.core.subjects import AnonymousUserSubjectType

    workspace = data_fixture.create_workspace()
    value = {
        "subject": {
            "version": 1,
            "type": AnonymousUserSubjectType.type,
            "name": "Anonymous",
            "uid": "not-persistent",
        }
    }
    with pytest.raises(ValueError, match="Unsupported exported Subject identity"):
        import_subject(value, workspace.id, {})
    assert not Subject.objects.filter(uid="not-persistent").exists()


@pytest.mark.django_db
def test_admin_edits_synchronize_subject(data_fixture):
    """Administrative name/email changes update the same retained identity."""
    from baserow.core.admin.users.handler import UserAdminHandler

    admin = data_fixture.create_user(is_staff=True)
    user = data_fixture.create_user()
    UserAdminHandler().update_user(
        admin, user.id, name="Admin renamed", username="admin-renamed@example.com"
    )
    subject = Subject.objects.get(pk=user.pk)
    assert (subject.name, subject.uid) == ("Admin renamed", "admin-renamed@example.com")


@pytest.mark.django_db
def test_subject_failure_rolls_back_account_handler(data_fixture, monkeypatch):
    """An identity write failure must not leave an account change committed."""
    from baserow.core.registries import subject_type_registry
    from baserow.core.user.handler import UserHandler

    user = data_fixture.create_user(first_name="Original")

    def fail_sync(*args, **kwargs):
        raise ValueError("Identity write failed")

    monkeypatch.setattr(
        subject_type_registry.get_by_model(user),
        "synchronize_persistent_subject",
        fail_sync,
    )
    with pytest.raises(ValueError, match="Identity write failed"):
        UserHandler().update_user(user, first_name="Rolled back")
    user.refresh_from_db()
    assert user.first_name == "Original"
    assert Subject.objects.get(pk=user.pk).name == "Original"


@pytest.mark.django_db
def test_unrelated_actor_edits_skip_subject_queries(data_fixture):
    """Preference and activity updates must not read or rewrite attribution."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from django.utils import timezone

    user = data_fixture.create_user()
    agent = AgentHandler().create_agent(
        data_fixture.create_workspace(), name="Assistant"
    )
    with CaptureQueriesContext(connection) as queries:
        user.profile.language = "en"
        user.profile.save(update_fields=["language"])
        agent.last_active = timezone.now()
        agent.save(update_fields=["last_active"])
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
    assert not any('"core_subject"' in query["sql"] for query in queries)


@pytest.mark.django_db
def test_bulk_user_creation_links_subjects(data_fixture):
    """The bulk population command explicitly synchronizes accounts without signals."""
    from baserow.contrib.database.management.commands.fill_users import crete_users

    workspace = data_fixture.create_workspace()
    crete_users(limit=3, workspace=workspace)
    users = User.objects.filter(workspaceuser__workspace=workspace)
    assert users.count() == 3
    for user in users.select_related("profile__subject"):
        assert user.profile.subject_id == user.pk
        assert (user.profile.subject.name, user.profile.subject.uid) == (
            user.first_name,
            user.email,
        )


@pytest.mark.django_db
def test_subject_lifecycle_registration_is_idempotent(data_fixture, monkeypatch):
    """Repeated startup registration must not synchronize a single save twice."""
    from baserow.core.registries import subject_type_registry

    user = data_fixture.create_user(first_name="Original")
    subject_type = subject_type_registry.get_by_model(user)
    subject_type.register_lifecycle_signals()
    subject_type.register_lifecycle_signals()
    synchronize = subject_type.synchronize_persistent_subject
    synchronized_ids = []

    def track_synchronization(actor, **kwargs):
        synchronized_ids.append(actor.pk)
        return synchronize(actor, **kwargs)

    monkeypatch.setattr(
        subject_type, "synchronize_persistent_subject", track_synchronization
    )
    user.first_name = "Renamed"
    user.save(update_fields=["first_name"])
    assert synchronized_ids == [user.pk]
    assert Subject.objects.get(pk=user.pk).name == "Renamed"
