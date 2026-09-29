from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete

from baserow_enterprise.teams.subjects import TeamSubjectType

User = get_user_model()


def cascade_subject_delete(sender, instance, **kwargs):
    from .models import TeamSubject

    subject_ct = ContentType.objects.get_for_model(instance)
    # Permanent subject deletion must also clean memberships in trashed teams.
    TeamSubject.objects_and_trash.filter(
        subject_id=instance.id, subject_type=subject_ct
    ).delete()


def cascade_workspace_user_delete(sender, instance, **kwargs):
    from .models import TeamSubject

    user_id = instance.user_id
    user_ct = ContentType.objects.get_for_model(User)
    TeamSubject.objects.filter(
        subject_id=user_id, subject_type=user_ct, team__workspace=instance.workspace_id
    ).delete()


def connect_to_post_delete_signals_to_cascade_deletion_to_team_subjects():
    from baserow.core.models import WorkspaceUser
    from baserow.core.registries import subject_type_registry

    for subject_type in subject_type_registry.get_all():
        if subject_type.type == TeamSubjectType.type:
            # We don't need to issue a `post_delete` for `Team`,
            # when one is deleted we'll CASCADE to `TeamSubject`.
            continue
        post_delete.connect(cascade_subject_delete, subject_type.model_class)

    post_delete.connect(cascade_workspace_user_delete, WorkspaceUser)
