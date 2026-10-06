import uuid

from django.contrib.postgres.operations import ValidateConstraint
from django.db import migrations

# Copy of `baserow.core.models.OFFICIAL_TEMPLATE_UUID_NAMESPACE`. Migrations must not
# import it, and the value must never change.
OFFICIAL_TEMPLATE_UUID_NAMESPACE = uuid.UUID("cf2443f4-126b-44f1-a746-0700d8c4034c")


def backfill_official_template_uuids(apps, schema_editor):
    """
    Gives every official template the uuid derived from its slug, so the same
    official template has the same uuid on every instance.
    """

    Template = apps.get_model("core", "Template")
    templates = list(
        Template._default_manager.filter(template_type="official", uuid__isnull=True)
        .only("id", "slug")
        .order_by("id")
    )
    taken = set(
        Template._default_manager.filter(uuid__isnull=False).values_list("uuid", flat=True)
    )

    for template in templates:
        template_uuid = uuid.uuid5(OFFICIAL_TEMPLATE_UUID_NAMESPACE, template.slug)
        # Slugs are not unique. The oldest row gets the uuid; later duplicates stay
        # without one.
        if template_uuid in taken:
            continue
        taken.add(template_uuid)
        template.uuid = template_uuid

    Template._default_manager.bulk_update(templates, ["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0127_user_template_schema"),
    ]

    operations = [
        migrations.RunPython(
            backfill_official_template_uuids, reverse_code=migrations.RunPython.noop
        ),
        ValidateConstraint(
            model_name="template",
            name="template_user_type_requires_author",
        ),
    ]
