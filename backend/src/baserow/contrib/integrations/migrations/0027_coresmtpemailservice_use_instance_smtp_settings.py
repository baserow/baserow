from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0026_backfill_coreperiodicservice_next_run_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="coresmtpemailservice",
            name="use_instance_smtp_settings",
            field=models.BooleanField(
                default=False,
                db_default=False,
                help_text="Whether to use the instance-level Django SMTP configuration.",
            ),
        ),
    ]
