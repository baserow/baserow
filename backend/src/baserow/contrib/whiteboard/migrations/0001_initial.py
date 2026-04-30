import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0114_alter_workspaceinvitation_message"),
    ]

    operations = [
        migrations.CreateModel(
            name="Whiteboard",
            fields=[
                (
                    "application_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.application",
                    ),
                ),
                ("content", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "abstract": False,
            },
            bases=("core.application",),
        ),
    ]
