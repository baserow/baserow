import json

from django.core.exceptions import ValidationError
from django.db import connections
from django.db.models import Q

from baserow.core.exceptions import SubjectTypeNotExist
from baserow.core.models import Subject, User
from baserow.core.subject.registries import subject_type_registry


class SubjectHandler:
    """Resolve, select and transfer retained identities through their SubjectTypes."""

    def allocate_subject_id(self, using="default"):
        """Reserve an ID from the same PostgreSQL sequence as new human accounts."""
        with connections[using].cursor() as cursor:
            cursor.execute(
                "SELECT nextval(pg_get_serial_sequence(%s, 'id'))",
                [User._meta.db_table],
            )
            return cursor.fetchone()[0]

    def persistent_subject_references_enabled(self, subject_type, cache=None):
        """Cache type-owned rollout checks once per import or bulk operation."""
        if not subject_type.supports_persistent_subjects:
            return False
        if cache is None:
            return subject_type.persistent_subject_references_enabled()
        key = ("subject_references_enabled", subject_type.type)
        if key not in cache:
            cache[key] = subject_type.persistent_subject_references_enabled()
        return cache[key]

    def subject_for_actor(self, actor, *, for_write=False):
        """Resolve attribution without treating an identity as a permission actor."""
        if actor is None or not getattr(actor, "pk", None):
            return None
        try:
            actor_type = subject_type_registry.get_by_model(actor)
        except SubjectTypeNotExist:
            return None
        return actor_type.get_persistent_subject(actor, for_write=for_write)

    def resolve_actor(self, subject):
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
        self, workspace_id, *, selectable=True, include_disabled_types=False
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
                and not self.persistent_subject_references_enabled(subject_type)
            ):
                continue
            query |= Q(
                type=subject_type.type
            ) & subject_type.get_persistent_subject_workspace_filter(
                workspace_id, selectable=selectable
            )
        return query

    def eligible_subjects(self, workspace_id, *, include_disabled_types=False):
        """Select live workspace identities in one query without granting access."""
        return Subject.objects.filter(
            self.workspace_subject_filter(
                workspace_id, include_disabled_types=include_disabled_types
            ),
            state="live",
        ).distinct()

    def export_subject(self, subject):
        """Portable attribution; numeric IDs and executable configuration never travel."""
        if subject is None:
            return None
        return {"subject": subject.get_type().export_persistent_subject(subject)}

    def import_subject(self, value, workspace_id, cache):
        """Dispatch nullable and legacy portable values to their registered SubjectType."""
        if not value:
            return None
        if isinstance(value, str):
            for subject_type in subject_type_registry.get_all():
                if (
                    subject_type.supports_persistent_subjects
                    and subject_type.get_legacy_persistent_subject_uid(value)
                    is not None
                ):
                    return subject_type.import_persistent_subject(
                        value, workspace_id, cache
                    )
            return None
        if not isinstance(value, dict):
            raise ValidationError("Invalid exported Subject identity")
        identity = value.get("subject", {})
        if not isinstance(identity, dict):
            raise ValueError("Unsupported exported Subject identity")
        try:
            subject_type = subject_type_registry.get(identity.get("type"))
        except SubjectTypeNotExist as exc:
            raise ValueError("Unsupported exported Subject identity") from exc
        return subject_type.import_persistent_subject(identity, workspace_id, cache)

    def human_readable_subject(self, subject, *, include_name=True):
        return subject.get_type().get_persistent_subject_export_value(
            subject, include_name=include_name
        )

    def transform_table_identities(self, table, transform):
        """Visit attribution values only; arbitrary cell JSON must remain untouched."""
        identity_field_ids = {
            f["id"]
            for f in table["fields"]
            if f["type"] in ("multiple_collaborators", "created_by", "last_modified_by")
        }
        for row in table["rows"]:
            for key in (
                "created_by",
                "last_modified_by",
                *[f"field_{i}" for i in identity_field_ids],
            ):
                if key in row:
                    value = row[key]
                    row[key] = (
                        [transform(v) for v in value]
                        if isinstance(value, list)
                        else transform(value)
                    )
        for view in table["views"]:
            for view_filter in view.get("filters", []):
                if view_filter["type"] in (
                    "multiple_collaborators_has",
                    "multiple_collaborators_has_not",
                ):
                    view_filter["value"] = transform(view_filter["value"])
            for default in view.get("default_row_values", {}).values():
                if default.get("field_id") in identity_field_ids and isinstance(
                    default.get("value"), list
                ):
                    default["value"] = [transform(v) for v in default["value"]]

    def pack_identity_manifest(self, table):
        """Partition the versioned workspace export manifest alongside each table."""
        identities = {}
        tokens = {}

        def pack(value):
            if not isinstance(value, dict) or "subject" not in value:
                return value
            identity = value["subject"]
            key = json.dumps(identity, sort_keys=True)
            if key not in tokens:
                token = str(len(tokens) + 1)
                tokens[key] = token
                identities[token] = identity
            return {"subject_ref": tokens[key]}

        self.transform_table_identities(table, pack)
        table["identity_manifest"] = {"version": 1, "identities": identities}

    def unpack_identity_manifest(self, table):
        """Expand scoped references before existing import hooks remap identities."""
        manifest = table.get("identity_manifest")
        if manifest is None:
            return
        if manifest.get("version") != 1:
            raise ValueError("Unsupported Subject manifest version")

        def unpack(value):
            if isinstance(value, dict) and "subject_ref" in value:
                return {"subject": manifest["identities"][value["subject_ref"]]}
            return value

        self.transform_table_identities(table, unpack)
