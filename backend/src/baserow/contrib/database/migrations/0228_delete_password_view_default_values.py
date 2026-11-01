from django.db import migrations
from django.db.models import Q


def delete_password_view_default_values(apps, schema_editor):
    """
    Password fields can't have view default values any more, so the stored ones
    are deleted, including those stored before the field became a password field.
    """

    ContentType = apps.get_model("contenttypes", "ContentType")
    ViewDefaultValue = apps.get_model("database", "ViewDefaultValue")
    database_alias = schema_editor.connection.alias

    password_field_content_types = ContentType.objects.using(database_alias).filter(
        app_label="database", model="passwordfield"
    )
    ViewDefaultValue.objects.using(database_alias).filter(
        Q(field__content_type__in=password_field_content_types)
        | Q(field_type="password")
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0227_backfill_rowhistory_anonymous_actor_type"),
    ]

    operations = [
        migrations.RunPython(
            delete_password_view_default_values, migrations.RunPython.noop
        ),
    ]
