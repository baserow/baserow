import django.db.models.deletion
from django.db import migrations, models

import baserow.core.formula.field


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0121_agent"),
        ("database", "0226_rowhistory_actor"),
        ("integrations", "0037_coreresponseservice_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="localbaserowintegration",
            name="authorized_agent",
            field=models.ForeignKey(
                blank=True,
                db_default=None,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.agent",
            ),
        ),
        migrations.CreateModel(
            name="LocalBaserowVectorSearch",
            fields=[
                (
                    "service_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.service",
                    ),
                ),
                (
                    "max_results",
                    models.PositiveIntegerField(
                        db_default=5,
                        default=5,
                        help_text="The maximum number of rows returned.",
                    ),
                ),
                (
                    "search_query",
                    baserow.core.formula.field.FormulaField(
                        blank=True,
                        default="",
                        help_text="The text to search for.",
                        null=True,
                    ),
                ),
                (
                    "field",
                    models.ForeignKey(
                        help_text="The field with vector search enabled that is "
                        "searched.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="database.field",
                    ),
                ),
                (
                    "included_fields",
                    models.ManyToManyField(
                        help_text="The fields returned for every matching row. All "
                        "fields when empty.",
                        related_name="+",
                        to="database.field",
                    ),
                ),
                (
                    "table",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="database.table",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("core.service",),
        ),
        migrations.CreateModel(
            name='GmailSendEmailService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('to_emails', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Recipient addresses, separated by commas.', null=True)),
                ('cc_emails', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='CC addresses, separated by commas.', null=True)),
                ('bcc_emails', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='BCC addresses, separated by commas.', null=True)),
                ('subject', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The subject line.', null=True)),
                ('body', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The plain text body.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service',),
        ),
        migrations.CreateModel(
            name='GoogleCalendarCreateEventService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; 'primary' is the account's main calendar.", null=True)),
                ('summary', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event title.', null=True)),
                ('description', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event description.', null=True)),
                ('location', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Where the event takes place.', null=True)),
                ('start', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Start as an ISO 8601 date-time (2026-10-06T09:00:00+02:00) or a date (2026-10-06) for an all-day event.', null=True)),
                ('end', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='End, in the same format as the start.', null=True)),
                ('time_zone', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='IANA time zone (Europe/Amsterdam) applied when the start and end carry no offset.', null=True)),
                ('attendees', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Attendee email addresses, separated by commas.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='GoogleCalendarDeleteEventService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; 'primary' is the account's main calendar.", null=True)),
                ('event_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The id of the event to delete.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='GoogleCalendarListEventsService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; 'primary' is the account's main calendar.", null=True)),
                ('time_min', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Only events ending after this ISO 8601 date-time.', null=True)),
                ('time_max', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Only events starting before this ISO 8601 date-time.', null=True)),
                ('query', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="Free text matched against the events' fields.", null=True)),
                ('max_results', models.PositiveIntegerField(default=50, help_text='The most events to return (1-250).')),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='GoogleCalendarUpdateEventService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; 'primary' is the account's main calendar.", null=True)),
                ('summary', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event title.', null=True)),
                ('description', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event description.', null=True)),
                ('location', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Where the event takes place.', null=True)),
                ('start', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Start as an ISO 8601 date-time (2026-10-06T09:00:00+02:00) or a date (2026-10-06) for an all-day event.', null=True)),
                ('end', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='End, in the same format as the start.', null=True)),
                ('time_zone', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='IANA time zone (Europe/Amsterdam) applied when the start and end carry no offset.', null=True)),
                ('attendees', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Attendee email addresses, separated by commas.', null=True)),
                ('event_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The id of the event to change.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='GoogleIntegration',
            fields=[
                ('integration_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.integration')),
                ('client_id', models.CharField(blank=True, default='', help_text='The client id of the OAuth app registered with the provider.', max_length=255)),
                ('client_secret', models.CharField(blank=True, default='', help_text='The client secret of the OAuth app.', max_length=255)),
                ('refresh_token', models.TextField(blank=True, default='', help_text='Issued when the account was connected; used to mint access tokens.')),
                ('access_token', models.TextField(blank=True, default='')),
                ('access_token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('account_email', models.CharField(blank=True, default='', help_text='The email address of the connected account, for display.', max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.integration',),
        ),
        migrations.CreateModel(
            name='JiraCreateIssueService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('summary', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The issue title.', null=True)),
                ('description', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The description, in Jira wiki markup or plain text.', null=True)),
                ('issue_type', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The issue type name, e.g. Task, Bug or Story.', null=True)),
                ('priority', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The priority name, e.g. High.', null=True)),
                ('labels', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Labels separated by commas; a label holds no spaces.', null=True)),
                ('assignee', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The assignee's account id (Cloud) or username (Server).", null=True)),
                ('project_key', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The project key, e.g. PROJ.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='JiraDeleteIssueService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('issue_key', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The key of the issue to delete, e.g. PROJ-12.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service',),
        ),
        migrations.CreateModel(
            name='JiraIntegration',
            fields=[
                ('integration_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.integration')),
                ('url', models.URLField(blank=True, default='', help_text='The base URL of the Jira site, e.g. https://your-domain.atlassian.net.', max_length=2000)),
                ('authentication', models.CharField(choices=[('API_TOKEN', 'API token'), ('PERSONAL_ACCESS_TOKEN', 'Personal access token')], db_default='API_TOKEN', default='API_TOKEN', max_length=32)),
                ('username', models.CharField(blank=True, default='', help_text='The email address of the account, used with an API token.', max_length=255)),
                ('api_token', models.CharField(blank=True, default='', help_text='The API token or personal access token.', max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.integration',),
        ),
        migrations.CreateModel(
            name='JiraListIssuesService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('jql', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The JQL query, e.g. project = PROJ AND status != Done ORDER BY created DESC.', null=True)),
                ('max_results', models.PositiveIntegerField(default=50, help_text='The most issues to return (1-100).')),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service',),
        ),
        migrations.CreateModel(
            name='JiraUpdateIssueService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('summary', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The issue title.', null=True)),
                ('description', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The description, in Jira wiki markup or plain text.', null=True)),
                ('issue_type', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The issue type name, e.g. Task, Bug or Story.', null=True)),
                ('priority', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The priority name, e.g. High.', null=True)),
                ('labels', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Labels separated by commas; a label holds no spaces.', null=True)),
                ('assignee', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The assignee's account id (Cloud) or username (Server).", null=True)),
                ('issue_key', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The key of the issue to change, e.g. PROJ-12.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='MicrosoftIntegration',
            fields=[
                ('integration_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.integration')),
                ('client_id', models.CharField(blank=True, default='', help_text='The client id of the OAuth app registered with the provider.', max_length=255)),
                ('client_secret', models.CharField(blank=True, default='', help_text='The client secret of the OAuth app.', max_length=255)),
                ('refresh_token', models.TextField(blank=True, default='', help_text='Issued when the account was connected; used to mint access tokens.')),
                ('access_token', models.TextField(blank=True, default='')),
                ('access_token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('account_email', models.CharField(blank=True, default='', help_text='The email address of the connected account, for display.', max_length=255)),
                ('tenant', models.CharField(default='common', help_text="The Entra tenant the app registration lives in: 'common' for any account, 'organizations' for work accounts, or a tenant id.", max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.integration',),
        ),
        migrations.CreateModel(
            name='MicrosoftTeamsSendMessageService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('team_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The id of the team.', null=True)),
                ('channel_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The id of the channel.', null=True)),
                ('message', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The message to post.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service',),
        ),
        migrations.CreateModel(
            name='OutlookCalendarCreateEventService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; leave empty for the account's default calendar.", null=True)),
                ('subject', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event title.', null=True)),
                ('body', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event description.', null=True)),
                ('location', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Where the event takes place.', null=True)),
                ('start', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Start as an ISO 8601 date-time (2026-10-06T09:00:00) or a date (2026-10-06) for an all-day event.', null=True)),
                ('end', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='End, in the same format as the start.', null=True)),
                ('time_zone', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The IANA time zone (Europe/Amsterdam) of the start and end.', null=True)),
                ('attendees', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Attendee email addresses, separated by commas.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='OutlookCalendarDeleteEventService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; leave empty for the account's default calendar.", null=True)),
                ('event_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The id of the event to delete.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='OutlookCalendarListEventsService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; leave empty for the account's default calendar.", null=True)),
                ('start', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Only events ending after this ISO 8601 date-time.', null=True)),
                ('end', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Only events starting before this ISO 8601 date-time.', null=True)),
                ('max_results', models.PositiveIntegerField(default=50, help_text='The most events to return (1-250).')),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='OutlookCalendarUpdateEventService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('calendar_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text="The calendar id; leave empty for the account's default calendar.", null=True)),
                ('subject', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event title.', null=True)),
                ('body', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The event description.', null=True)),
                ('location', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Where the event takes place.', null=True)),
                ('start', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Start as an ISO 8601 date-time (2026-10-06T09:00:00) or a date (2026-10-06) for an all-day event.', null=True)),
                ('end', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='End, in the same format as the start.', null=True)),
                ('time_zone', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The IANA time zone (Europe/Amsterdam) of the start and end.', null=True)),
                ('attendees', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Attendee email addresses, separated by commas.', null=True)),
                ('event_id', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The id of the event to change.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service', models.Model),
        ),
        migrations.CreateModel(
            name='OutlookSendEmailService',
            fields=[
                ('service_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.service')),
                ('to_emails', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='Recipient addresses, separated by commas.', null=True)),
                ('cc_emails', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='CC addresses, separated by commas.', null=True)),
                ('bcc_emails', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='BCC addresses, separated by commas.', null=True)),
                ('subject', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The subject line.', null=True)),
                ('body', baserow.core.formula.field.FormulaField(blank=True, default='', help_text='The plain text body.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('core.service',),
        ),
    ]
