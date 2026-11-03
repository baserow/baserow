from django.conf import settings
from django.db import migrations, models, transaction

BATCH_SIZE = 1000


def backfill_subjects(apps, schema_editor):
    """Reconcile users in bounded transactions; safe to restart after any batch."""
    alias = schema_editor.connection.alias
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Subject = apps.get_model("core", "Subject")
    Profile = apps.get_model("core", "UserProfile")
    last_id = 0
    while True:
        with transaction.atomic(using=alias):
            user_ids = list(
                User.objects.using(alias).filter(pk__gt=last_id)
                .order_by("pk").values_list("pk", flat=True)[:BATCH_SIZE]
            )
            if not user_ids:
                break
            # Django deletes profiles before users. Take the same lock order and
            # allow concurrent FK inserts while holding the non-key User locks.
            list(Profile.objects.using(alias).select_for_update()
                 .filter(user_id__in=user_ids).values_list("pk", flat=True))
            users = list(
                User.objects.using(alias).select_for_update(no_key=True)
                .filter(pk__in=user_ids).order_by("pk")
            )
            Subject.objects.using(alias).bulk_create(
                [Subject(id=u.id, type="auth.User", name=u.first_name,
                         uid=u.email, state="live") for u in users],
                update_conflicts=True, update_fields=["name", "uid", "state"],
                unique_fields=["id"],
            )
            Profile.objects.using(alias).bulk_create(
                [Profile(user_id=u.id, subject_id=u.id) for u in users],
                ignore_conflicts=True,
            )
            Profile.objects.using(alias).filter(user_id__in=[u.id for u in users]).update(
                subject_id=models.F("user_id")
            )
            last_id = user_ids[-1]
    # Agent primary keys remain independent. Reserve Subject IDs in one sequence
    # query per batch, using the same built-in sequence function as User inserts.
    Agent = apps.get_model("core", "Agent")
    last_id = 0
    while True:
        with transaction.atomic(using=alias):
            agents = list(Agent._base_manager.using(alias).select_for_update()
                          .filter(pk__gt=last_id).order_by("pk")[:BATCH_SIZE])
            if not agents:
                break
            unlinked = [agent for agent in agents if agent.subject_id is None]
            if unlinked:
                with schema_editor.connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT nextval(pg_get_serial_sequence(%s, 'id')) "
                        "FROM generate_series(1, %s)",
                        [User._meta.db_table, len(unlinked)],
                    )
                    for agent, (subject_id,) in zip(unlinked, cursor.fetchall()):
                        agent.subject_id = subject_id
            Subject.objects.using(alias).bulk_create(
                [Subject(id=agent.subject_id, type="core.Agent", name=agent.name,
                         uid=str(agent.uid), state="trashed" if agent.trashed else "live")
                 for agent in agents],
                update_conflicts=True, update_fields=["name", "uid", "state"],
                unique_fields=["id"],
            )
            if unlinked:
                Agent._base_manager.using(alias).bulk_update(unlinked, ["subject"])
            last_id = agents[-1].pk
    # Old workers have no Python synchronization. Retain identities whose actors
    # disappeared during the deployment window, without inventing historical IDs.
    for subject_type, live_ids in [
        ("auth.User", User.objects.using(alias).values("pk")),
        ("core.Agent", Agent._base_manager.using(alias).exclude(subject_id=None)
         .values("subject_id")),
    ]:
        last_id = 0
        while True:
            with transaction.atomic(using=alias):
                ids = list(Subject.objects.using(alias)
                           .filter(type=subject_type, pk__gt=last_id)
                           .exclude(state="retained").exclude(pk__in=live_ids)
                           .order_by("pk").values_list("pk", flat=True)[:BATCH_SIZE])
                if not ids:
                    break
                Subject.objects.using(alias).filter(pk__in=ids).update(state="retained")
                last_id = ids[-1]


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("core", "0136_subject")]
    operations = [migrations.RunPython(backfill_subjects, migrations.RunPython.noop)]
