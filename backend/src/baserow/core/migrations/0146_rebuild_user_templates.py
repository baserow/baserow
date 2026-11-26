from django.db import migrations


class Migration(migrations.Migration):
    """
    Applying it rebuilds the user templates once all migrations of the run are
    applied, see `rebuild_user_templates_after_migrate`.
    """

    dependencies = [
        ("core", "0145_settings_allow_user_templates"),
    ]

    operations = []
