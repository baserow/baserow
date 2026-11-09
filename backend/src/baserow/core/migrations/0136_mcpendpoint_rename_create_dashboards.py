from django.db import migrations

OLD_NAME = "create_dashboards"
NEW_NAME = "create_dashboard"


def forward(apps, schema_editor):
    """
    `create_dashboards` is now `create_dashboard`. An unregistered name is ignored,
    so endpoints that allowed the old name would lose dashboard creation. The new
    `update_dashboard` is left for the user to allow.
    """

    MCPEndpoint = apps.get_model("core", "MCPEndpoint")
    endpoints = MCPEndpoint.objects.filter(allowed_tools__contains=[OLD_NAME])
    for endpoint in endpoints.iterator(chunk_size=500):
        tools = []
        for name in endpoint.allowed_tools:
            name = NEW_NAME if name == OLD_NAME else name
            if name not in tools:
                tools.append(name)
        endpoint.allowed_tools = tools
        endpoint.save(update_fields=["allowed_tools"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0135_workspaceinvitationlink_scope"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
