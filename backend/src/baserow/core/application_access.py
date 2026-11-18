from collections.abc import Iterable

from baserow.core.cache import local_cache
from baserow.core.models import Application, Workspace
from baserow.core.registries import object_scope_type_registry


def applications_with_policies(
    workspaces: Iterable[Workspace], policy: str | None = None
) -> dict[int, list[Application]]:
    """Load policy-bearing scopes once per request, in one query across workspaces."""
    by_workspace = {}
    missing = []
    for workspace in workspaces:
        cached = local_cache.get_if_cached(f"application_policies_{workspace.id}")
        if cached is None:
            missing.append(workspace.id)
            cached = []
        by_workspace[workspace.id] = cached
    if missing:
        for app in Application.objects_and_trash.filter(
            workspace_id__in=missing, access_policy__isnull=False
        ).select_related("workspace"):
            by_workspace[app.workspace_id].append(app)
        for workspace_id in missing:
            local_cache.get(
                f"application_policies_{workspace_id}", by_workspace[workspace_id]
            )
    if policy is None:
        return by_workspace
    return {
        workspace_id: [app for app in apps if app.access_policy == policy]
        for workspace_id, apps in by_workspace.items()
    }


def containing_application(context) -> Application | None:
    """Find the application governing this permission context, if it has one."""
    if isinstance(context, Application):
        return context
    if context is None:
        return None
    scope = object_scope_type_registry.get("application")
    if not object_scope_type_registry.scope_type_includes_scope_type(
        scope, object_scope_type_registry.get_by_model(context)
    ):
        return None
    return object_scope_type_registry.get_parent(context, at_scope_type=scope)
