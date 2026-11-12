from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("database", "0228_delete_password_view_default_values")]

    operations = [
        migrations.AddField(
            model_name="rowhistory",
            name="actor_user_type",
            field=models.CharField(max_length=8, null=True),
        ),
    ]
