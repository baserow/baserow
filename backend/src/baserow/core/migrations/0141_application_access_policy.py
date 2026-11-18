from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0140_userprofile_trashed_idx")]
    operations = [
        migrations.AddField(
            model_name="application",
            name="access_policy",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]
