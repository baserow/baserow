from django.db import connections
from django.db.models import Q

from baserow.core.exceptions import SubjectTypeNotExist
from baserow.core.models import Subject, User
from baserow.core.registries import subject_type_registry


def allocate_subject_id(using="default"):
    """Reserve an ID from the same PostgreSQL sequence as new human accounts."""
    with connections[using].cursor() as cursor:
        cursor.execute(
            "SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [User._meta.db_table]
        )
        return cursor.fetchone()[0]


def persistent_subject_references_enabled(subject_type, cache=None):
    """Cache type-owned rollout checks once per import or bulk operation."""
    if not subject_type.supports_persistent_subjects:
        return False
    if cache is None:
        return subject_type.persistent_subject_references_enabled()
    key = ("subject_references_enabled", subject_type.type)
    if key not in cache:
        cache[key] = subject_type.persistent_subject_references_enabled()
    return cache[key]


def subject_for_actor(actor, *, for_write=False):
    """Resolve attribution without treating an identity as a permission actor."""
    if actor is None or not getattr(actor, "pk", None):
        return None
    try:
        actor_type = subject_type_registry.get_by_model(actor)
    except SubjectTypeNotExist:
        return None
    return actor_type.get_persistent_subject(actor, for_write=for_write)


def resolve_actor(subject):
    """Fail closed when retained attribution has no live executable actor."""
    if subject.state != "live":
        return None
    try:
        subject_type = subject.get_type()
        if not subject_type.supports_persistent_subjects:
            return None
        return subject_type.resolve_persistent_subject(subject)
    except SubjectTypeNotExist:
        return None


def workspace_subject_filter(
    workspace_id, *, selectable=True, include_disabled_types=False
):
    """Compose registered identity types without fetching or resolving actors."""
    query = Q(pk__in=[])
    if workspace_id is None:
        return query
    for subject_type in subject_type_registry.get_all():
        if not subject_type.supports_persistent_subjects:
            continue
        if (
            selectable
            and not include_disabled_types
            and not persistent_subject_references_enabled(subject_type)
        ):
            continue
        query |= Q(
            type=subject_type.type
        ) & subject_type.get_persistent_subject_workspace_filter(
            workspace_id, selectable=selectable
        )
    return query


def eligible_subjects(workspace_id, *, include_disabled_types=False):
    """Select live workspace identities in one query without granting access."""
    return Subject.objects.filter(
        workspace_subject_filter(
            workspace_id, include_disabled_types=include_disabled_types
        ),
        state="live",
    ).distinct()
