from typing import Any, Dict

# The mappings of applications an import may not hold. A reference is only remapped
# when its mapping exists, and kept as is otherwise, so a builder imported without
# its database would keep the ids of the source instance and point at whatever
# table or field has them here. Seeding the mappings clears such references
# instead.
#
# The views mapping is created together with the mappings of its children, see
# `ViewType.import_serialized`, so they're seeded together too.
SEEDED_ID_MAPPINGS = (
    "database_tables",
    "database_fields",
    "database_views",
    "database_view_filters",
    "database_view_filter_groups",
    "database_view_sortings",
    "database_view_group_bys",
    "database_view_decorations",
    "automation_workflows",
)


def seed_id_mappings(id_mapping: Dict[str, Any]) -> None:
    """
    Creates the mappings of applications an import may not hold, so references to
    anything that isn't imported are cleared instead of kept as the ids of the
    source instance. Only an import that isn't a duplicate may be seeded: a
    duplicate stays in the same workspace, where those ids are still right.

    :param id_mapping: The id mapping of the import, updated in place.
    """

    for key in SEEDED_ID_MAPPINGS:
        id_mapping.setdefault(key, {})
