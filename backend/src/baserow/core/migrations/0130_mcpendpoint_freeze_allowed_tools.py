from django.db import migrations, models

# A copy of `LEGACY_DEFAULT_TOOLS`, the tools an endpoint without an allow-list
# could use before this migration. Inlined so later changes to the constant don't
# change what this migration writes.
LEGACY_DEFAULT_TOOLS = [
    "list_databases",
    "list_tables",
    "get_table_schema",
    "list_table_rows",
    "create_rows",
    "update_rows",
    "delete_rows",
]


def forward(apps, schema_editor):
    MCPEndpoint = apps.get_model("core", "MCPEndpoint")
    MCPEndpoint.objects.filter(allowed_tools__isnull=True).update(
        allowed_tools=LEGACY_DEFAULT_TOOLS
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0129_template_backfill_official"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mcpendpoint",
            name="allowed_tools",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text="Names of the MCP tools this endpoint may use. Null is only "
                "left by older versions and allows the legacy default tools.",
                null=True,
            ),
        ),
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
