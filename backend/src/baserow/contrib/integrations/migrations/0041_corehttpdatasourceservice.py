import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0039_localbaserowintegration_authorized_agent"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoreHTTPDataSourceService",
            fields=[
                (
                    "corehttprequestservice_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="integrations.corehttprequestservice",
                    ),
                ),
                (
                    "returns_list",
                    models.BooleanField(
                        db_default=False,
                        default=False,
                        help_text="Whether the records are a list in the response, at `list_path`, instead of the response being one record.",
                    ),
                ),
                (
                    "list_path",
                    models.CharField(
                        blank=True,
                        db_default="",
                        default="",
                        help_text="The dotted path to the list in the response. Blank means the response itself is the list.",
                        max_length=255,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("integrations.corehttprequestservice",),
        ),
    ]
