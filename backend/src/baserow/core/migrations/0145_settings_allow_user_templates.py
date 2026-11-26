from django.db import migrations, models

from baserow.core.migration_utils import LockTimeoutMigration


class Migration(LockTimeoutMigration):
    dependencies = [
        ("core", "0144_identity_definition"),
    ]

    operations = [
        migrations.AddField(
            model_name="settings",
            name="allow_user_templates",
            field=models.BooleanField(
                db_default=True,
                default=True,
                help_text="Indicates whether user templates can be created, shared, "
                "opened and installed. While off, only instance admins can open, "
                "install and download them.",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="template",
            name="core_template_row_role",
        ),
        migrations.RemoveField(
            model_name="template",
            name="shared_revision",
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("root__isnull", True), ("version", 1)),
                    models.Q(
                        ("author__isnull", True),
                        ("blocked_at__isnull", True),
                        ("blocked_by__isnull", True),
                        ("blocked_reason", ""),
                        ("install_count", 0),
                        ("marked_for_deletion_at__isnull", True),
                        ("owner__isnull", True),
                        ("private_link_token__isnull", True),
                        ("public_revision__isnull", True),
                        ("root__isnull", False),
                        ("slug", ""),
                        ("version__gte", 2),
                    ),
                    _connector="OR",
                ),
                name="core_template_row_role",
            ),
        ),
    ]
