from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("database", "0228_delete_password_view_default_values")]

    operations = [
        migrations.AddField(
            model_name="airtableimportjob",
            name="name",
            field=models.CharField(blank=True, max_length=160, null=True),
        ),
        migrations.AddField(
            model_name="airtableimportjob",
            name="access_policy",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]
