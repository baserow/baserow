import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0225_rich_text_file_uniques"),
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
        migrations.AddField(
            model_name="field",
            name="vector_search_enabled",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="If true, an embedding of every cell is kept in the "
                "workspace search data so the field can be searched semantically. "
                "Only field types that support vector search can enable it.",
            ),
        ),
        migrations.CreateModel(
            name="WorkspaceSearchTable",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "embedding_columns_added",
                    models.BooleanField(db_default=False, default=False),
                ),
                (
                    "workspace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="search_table_state",
                        to="core.workspace",
                    ),
                ),
            ],
        ),
    ]
