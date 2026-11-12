from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_enterprise", "0072_html_element"),
    ]

    operations = [
        # The Agent model is gone, so these rows can no longer resolve their subject.
        migrations.RunSQL(
            [
                "DELETE FROM baserow_enterprise_roleassignment WHERE subject_type_id IN "
                "(SELECT id FROM django_content_type "
                "WHERE app_label = 'core' AND model = 'agent')",
                "DELETE FROM baserow_enterprise_teamsubject WHERE subject_type_id IN "
                "(SELECT id FROM django_content_type "
                "WHERE app_label = 'core' AND model = 'agent')",
            ],
            migrations.RunSQL.noop,
        ),
    ]
