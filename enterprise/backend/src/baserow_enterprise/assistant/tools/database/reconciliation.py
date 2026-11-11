from collections.abc import Sequence
from typing import Any

from baserow.contrib.database.tools.tables import (  # noqa: F401
    TableCreationPlan,
    missing_field_names,
    plan_table_creation,
    table_schema_conflict,
)


def reused_tables_next_steps(conflicts: Sequence[dict[str, Any]]) -> str:
    """
    Kuma's follow-up guidance for reused tables that lack what was requested.

    :param conflicts: The ``incomplete_reused_tables`` of the shared result.
    :return: The next steps, naming Kuma's own tools.
    """

    missing_names = missing_field_names(conflicts)
    missing_hint = (
        f" Missing fields: {', '.join(missing_names)}." if missing_names else ""
    )
    return (
        "Exact-name tables were reused, but their actual schemas in "
        "reused_tables do not satisfy the request."
        f"{missing_hint} Reuse does not authorize modifying existing tables. "
        "If the user has not already authorized the reported changes to these "
        "existing tables, call ask_user to explain the differences and confirm "
        "whether to modify them or create separate tables with different names, "
        "then stop. Only after that authorization, call create_fields with "
        "each table id and its missing_fields payload; use update_fields for "
        "supported field settings, with missing_options as add_options and "
        "option_color_mismatches as update_options by id. "
        "Field types and link/lookup relations cannot be changed in place. Do "
        "not claim completion while mismatches remain; report them accurately."
    )
