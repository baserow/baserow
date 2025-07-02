from typing import Dict, List, Optional

from django.db.models.constraints import BaseConstraint

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import (
    field_constraint_registry,
    field_type_registry,
)


def build_django_field_constraints(
    field: Field, field_constraints: Optional[List[Dict]] = None
) -> List[BaseConstraint]:
    """
    Builds Django database constraints for a field based on
    the provided field_constraints configuration list.

    :param field: The Field model instance to build constraints for
    :param field_constraints: Optional list of constraint configurations
    :return: List of Django database constraint objects
    """

    if field_constraints is None:
        return []

    field_type = field_type_registry.get_by_model(field)
    db_constraints = []

    for constraint_config in field_constraints:
        constraint_name = constraint_config.get("name")
        if not constraint_name:
            continue

        constraint_instance = field_constraint_registry.get_specific_constraint(
            constraint_name, field_type
        )
        if constraint_instance:
            db_constraints.append(
                constraint_instance.build_field_constraint(field, field.db_column)
            )
    return db_constraints
