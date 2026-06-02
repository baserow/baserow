import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_enterprise", "0061_core_code_service_action_node"),
    ]

    operations = [
        migrations.AlterField(
            model_name="corecodeservice",
            name="code",
            field=models.TextField(
                blank=True,
                help_text="The code to execute.",
                max_length=4096,
                validators=[django.core.validators.MaxLengthValidator(4096)],
            ),
        ),
    ]
