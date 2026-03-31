import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0204_add_row_exists_not_trashed_function"),
    ]

    operations = [
        migrations.CreateModel(
            name="FormViewEditRowField",
            fields=[
                (
                    "field_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="database.field",
                    ),
                ),
                (
                    "form_view",
                    models.ForeignKey(
                        blank=True,
                        help_text="The form view that will be used to edit rows via this field.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="edit_row_fields",
                        to="database.formview",
                    ),
                ),
            ],
            bases=("database.field",),
        ),
    ]
