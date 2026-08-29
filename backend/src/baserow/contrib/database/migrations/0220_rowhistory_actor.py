from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0219_button_field_smtp_email_action"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
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
    ]
