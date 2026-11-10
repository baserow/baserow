from django.db import migrations

OLD_NAME = "create_dashboards"
NEW_NAME = "create_dashboard"


def forward(apps, schema_editor):
    """
    `create_dashboards` is now `create_dashboard`. An unregistered name is ignored,
    so endpoints that allowed the old name would lose dashboard creation. The new
    `update_dashboard` is left for the user to allow.

    One UPDATE rewrites each list from the row it locks, so a change to an
    endpoint's tools committed while this runs, like a revoked tool, is kept.
    """

    MCPEndpoint = apps.get_model("core", "MCPEndpoint")
    table = schema_editor.quote_name(MCPEndpoint._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {table} SET allowed_tools = (
                SELECT jsonb_agg(tools.name ORDER BY tools.position)
                FROM (
                    SELECT
                        CASE WHEN tool.value = to_jsonb(%(old)s::text)
                            THEN to_jsonb(%(new)s::text)
                            ELSE tool.value
                        END AS name,
                        min(tool.position) AS position
                    FROM jsonb_array_elements(allowed_tools)
                        WITH ORDINALITY AS tool(value, position)
                    GROUP BY 1
                ) AS tools
            )
            WHERE allowed_tools @> jsonb_build_array(%(old)s::text)
            """,
            {"old": OLD_NAME, "new": NEW_NAME},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0135_workspaceinvitationlink_scope"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
