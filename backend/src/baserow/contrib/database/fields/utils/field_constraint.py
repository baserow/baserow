from typing import Dict, List, Optional

from django.db.models.constraints import BaseConstraint

from baserow.contrib.database.fields.models import Field, FieldConstraint
from baserow.contrib.database.fields.registries import (
    field_constraint_registry,
    field_type_registry,
)


def _create_constraint_objects(
    field: Field, constraint_data: List[Dict]
) -> List[FieldConstraint]:
    """
    Convert constraint data to FieldConstraint objects.

    :param field: The Field model instance the constraints belong to
    :param constraint_data: List of constraint configuration dictionaries
    :return: List of unsaved FieldConstraint objects
    """

    constraints = []
    for constraint_dict in constraint_data:
        constraint = FieldConstraint(
            field=field, type_name=constraint_dict.get("type_name")
        )
        constraints.append(constraint)
    return constraints


def build_django_field_constraints(
    field: Field, field_constraints: Optional[List[FieldConstraint]] = None
) -> List[BaseConstraint]:
    """
    Builds Django database constraints for a field based on
    the provided field_constraints list.

    :param field: The Field model instance to build constraints for
    :param field_constraints: Optional list of FieldConstraint instances
    :return: List of Django database constraint objects
    """

    if field_constraints is None:
        return []

    field_type = field_type_registry.get_by_model(field)
    db_constraints = []

    for constraint in field_constraints:
        constraint_name = constraint.type_name
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
