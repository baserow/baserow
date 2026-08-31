import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0118_aiproviderworkspaceoverride_and_more'),
        ('database', '0218_button_field_http_request_action'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoreSMTPEmailWorkflowAction',
            fields=[
                ('databaseworkflowaction_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='database.databaseworkflowaction')),
                ('service', models.ForeignKey(help_text='The service which this action is associated with.', on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='core.service')),
            ],
            options={
                'abstract': False,
            },
            bases=('database.databaseworkflowaction',),
        ),
    ]
