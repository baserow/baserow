import json

from django.core.exceptions import ValidationError

from baserow.core.exceptions import SubjectTypeNotExist
from baserow.core.registries import subject_type_registry


def export_subject(subject):
    """Portable attribution; numeric IDs and executable configuration never travel."""
    if subject is None:
        return None
    return {"subject": subject.get_type().export_persistent_subject(subject)}


def import_subject(value, workspace_id, cache):
    """Dispatch nullable and legacy portable values to their registered SubjectType."""
    if not value:
        return None
    if isinstance(value, str):
        for subject_type in subject_type_registry.get_all():
            if (
                subject_type.supports_persistent_subjects
                and subject_type.get_legacy_persistent_subject_uid(value) is not None
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


def human_readable_subject(subject, *, include_name=True):
    return subject.get_type().get_persistent_subject_export_value(
        subject, include_name=include_name
    )


def transform_table_identities(table, transform):
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


def pack_identity_manifest(table):
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

    transform_table_identities(table, pack)
    table["identity_manifest"] = {"version": 1, "identities": identities}


def unpack_identity_manifest(table):
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

    transform_table_identities(table, unpack)
