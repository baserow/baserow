from baserow.core.user_sources.constants import DEFAULT_USER_ROLE_PREFIX


def remap_user_source_roles(
    roles: list[str],
    existing_roles: list[str],
    user_sources_mapping: dict[int, int],
) -> list[str]:
    """Remap default roles, preserving explicit and unmapped role values.

    Explicit roles can match the default-role format, so roles already exposed
    by the imported user sources take precedence. Callers decide whether to
    filter roles that do not exist in the imported application.
    """

    default_role_mapping = {
        f"{DEFAULT_USER_ROLE_PREFIX}{old_id}": f"{DEFAULT_USER_ROLE_PREFIX}{new_id}"
        for old_id, new_id in user_sources_mapping.items()
    }
    for role in existing_roles:
        default_role_mapping.pop(role, None)
    return [default_role_mapping.get(role, role) for role in roles]
