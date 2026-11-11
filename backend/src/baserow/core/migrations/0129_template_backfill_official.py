from django.db import migrations
from django.db.models import F


def forwards(apps, schema_editor):
    """
    Every existing template is official. The ones with a workspace are approved and
    listed as their own public revision, the same as the templates created by the
    sync from now on.
    """

    Template = apps.get_model("core", "Template")
    templates = Template.objects.using(schema_editor.connection.alias)

    templates.filter(type__isnull=True).update(type="official")
    templates.filter(
        type="official",
        root__isnull=True,
        public_revision__isnull=True,
        workspace__isnull=False,
    ).update(review_state="approved", public_revision_id=F("id"))


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0128_template_user_templates"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
