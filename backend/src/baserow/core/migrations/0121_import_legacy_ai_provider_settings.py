from django.db import migrations

from loguru import logger


def import_legacy_ai_provider_settings(apps, schema_editor):
    # Imported here so the import shares the resolver's own completeness predicate:
    # a copy frozen into this migration could drift and silently narrow model lists.
    from baserow.core.ai_provider.legacy_import import (
        apply_import_plan,
        plan_instance_import,
        plan_workspace_import,
        suppress_inherited_instance_providers,
    )

    AIProviderConfig = apps.get_model("core", "AIProviderConfig")
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    AIProviderWorkspaceOverride = apps.get_model("core", "AIProviderWorkspaceOverride")
    Workspace = apps.get_model("core", "Workspace")
    using = schema_editor.connection.alias

    instance_plan = plan_instance_import(
        AIProviderConfig, AIProviderModel, using=using
    )
    workspace_plan = plan_workspace_import(
        AIProviderConfig, AIProviderModel, Workspace, using=using
    )
    _report_skipped(instance_plan, "instance")
    _report_skipped(workspace_plan, "workspace")

    apply_import_plan(instance_plan, AIProviderConfig, AIProviderModel, using=using)
    imported_workspace_providers = apply_import_plan(
        workspace_plan, AIProviderConfig, AIProviderModel, using=using
    )
    suppress_inherited_instance_providers(
        imported_workspace_providers,
        AIProviderConfig,
        AIProviderWorkspaceOverride,
        using=using,
    )


def _report_skipped(plan, scope):
    # An administrator cannot fix what the upgrade silently declined to import.
    for skipped in plan.skipped:
        scope_label = (
            f"workspace {skipped.workspace_id}"
            if skipped.workspace_id is not None
            else "instance"
        )
        logger.warning(
            "Did not import the {} {} AI provider settings: {}. Configure this "
            "provider under AI providers instead.",
            scope_label,
            skipped.provider_type,
            skipped.reason,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0120_add_ai_agent_provider_model_feature"),
    ]

    operations = [
        # Reversing must not delete providers an administrator edited in the new UI;
        # the previous version ignores these tables, so leaving the rows is safe.
        migrations.RunPython(
            import_legacy_ai_provider_settings, migrations.RunPython.noop
        ),
    ]
