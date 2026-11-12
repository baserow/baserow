from django.db import migrations


def clear_legacy_agent_run_as(apps, schema_editor):
    using = schema_editor.connection.alias
    # The Agent model is gone; an Agent without an identity has no workspace access.
    apps.get_model("agent", "AgentApplication").objects.using(using).filter(
        run_as_subject_type="core.Agent"
    ).update(run_as_subject_type=None, run_as_subject_id=None)
    apps.get_model("agent", "AgentReplyTranscript").objects.using(using).filter(
        paused_run_as_subject_type="core.Agent"
    ).update(paused_run_as_subject_type=None, paused_run_as_subject_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0015_agent_shared_conversations"),
        ("core", "0138_user_identities"),
    ]

    operations = [
        migrations.RunPython(clear_legacy_agent_run_as, migrations.RunPython.noop),
    ]
