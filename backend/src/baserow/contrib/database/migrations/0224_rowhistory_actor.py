from django.db import migrations, models


def set_anonymous_actor_type(apps, schema_editor):
    RowHistory = apps.get_model("database", "RowHistory")
    RowHistory.objects.filter(actor_id__isnull=True).update(actor_type="anonymous")


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0223_gridview_group_by_layout"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="rowhistory",
                    name="user_name",
                    field=models.CharField(
                        blank=True,
                        help_text="The name of the user that performed the action.",
                        max_length=160,
                    ),
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name="rowhistory",
                    old_name="user_id",
                    new_name="actor_id",
                ),
                migrations.AlterField(
                    model_name="rowhistory",
                    name="actor_id",
                    field=models.PositiveIntegerField(
                        db_column="user_id",
                        help_text="The ID of the actor that performed the action.",
                        null=True,
                    ),
                ),
                migrations.RenameField(
                    model_name="rowhistory",
                    old_name="user_name",
                    new_name="actor_name",
                ),
                migrations.AlterField(
                    model_name="rowhistory",
                    name="actor_name",
                    field=models.CharField(
                        blank=True,
                        db_column="user_name",
                        help_text="The name of the actor that performed the action.",
                        max_length=160,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="rowhistory",
            name="actor_type",
            field=models.CharField(db_default="auth.User", max_length=255),
        ),
        migrations.RunPython(set_anonymous_actor_type, migrations.RunPython.noop),
    ]
