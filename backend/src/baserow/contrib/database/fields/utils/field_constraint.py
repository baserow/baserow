from typing import Any, Dict, List, Optional

from django.db.models.constraints import BaseConstraint

from baserow.contrib.database.fields.exceptions import (
    FieldConstraintDoesNotSupportDefaultValueError,
    InvalidFieldConstraint,
)
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


def validate_field_constraints(field_type, field_constraints: List[Dict[str, Any]]):
    for constraint in field_constraints:
        constraint_name = constraint.get("type_name")
        if not constraint_name:
            raise InvalidFieldConstraint(
                field_type=field_type.type,
                constraint_type="missing_type_name",
            )

        constraint_instance = field_constraint_registry.get_specific_constraint(
            constraint_name, field_type
        )
        if not constraint_instance:
            raise InvalidFieldConstraint(
                field_type=field_type.type,
                constraint_type=constraint_name,
            )


def validate_default_value_with_constraints(
    field_type, field_constraints=None, field_data=None, field=None
):
    """
    Validates that the field's default value is compatible with its constraints.

    :param field_type: The field type instance
    :param field_constraints: List of constraint data to validate against
    :param field_data: Dictionary containing field attributes including default value
    :param field: The field instance to check for existing default value
    :raises FieldConstraintDoesNotSupportDefaultValueError: If any constraint
        doesn't support default values
    """

    if not field_constraints:
        return

    default_field_name = field_type.get_default_options_field_name()

    # default value from provided data takes precedence over
    # default value stored in the field
    if field_data and default_field_name:
        default_value = field_data.get(default_field_name)
    elif field:
        default_value = getattr(field, default_field_name, None)
    else:
        default_value = None

    if not default_value:
        return

    can_have_default_value = all(
        field_constraint_registry.get_specific_constraint(
            constraint.get("type_name"), field_type
        ).can_support_default_value
        for constraint in field_constraints
    )
    if not can_have_default_value:
        raise FieldConstraintDoesNotSupportDefaultValueError()
