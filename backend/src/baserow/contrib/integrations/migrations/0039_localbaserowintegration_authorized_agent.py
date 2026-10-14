from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0121_agent"),
        ("integrations", "0038_smtpintegration_use_ssl"),
    ]

    operations = [
        migrations.AddField(
            model_name="localbaserowintegration",
            name="authorized_subject_type",
            field=models.CharField(
                db_default="auth.User", default="auth.User", max_length=255
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="localbaserowintegration",
                    name="authorized_user",
                    field=models.BigIntegerField(
                        blank=True, db_column="authorized_user_id", null=True
                    ),
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name="localbaserowintegration",
                    old_name="authorized_user",
                    new_name="authorized_subject_id",
                ),
                migrations.AlterField(
                    model_name="localbaserowintegration",
                    name="authorized_subject_id",
                    field=models.BigIntegerField(
                        blank=True, db_column="authorized_user_id", null=True
                    ),
                ),
            ],
        ),
    ]
