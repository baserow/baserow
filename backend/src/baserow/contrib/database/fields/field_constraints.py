from typing import Dict, List, Optional

from django.db import models as django_models
from django.db.models.constraints import CheckConstraint, UniqueConstraint

from baserow.contrib.database.fields.models import Field
from baserow.core.registry import Instance


def build_field_constraints(
    field: Field, model, field_constraints: Optional[List[Dict]] = None
) -> List[CheckConstraint | UniqueConstraint]:
    """
    Builds new field constraints for a field based on the field_constraints
    configuration.
    """

    from baserow.contrib.database.fields.registries import (
        field_constraint_registry,
        field_type_registry,
    )

    if not field_constraints:
        return []

    field_type = field_type_registry.get_by_model(field)
    supported_constraints = field_type.get_supported_field_constraints()
    db_constraints = []

    for constraint_config in field_constraints:
        constraint_type = constraint_config.get("type")
        if constraint_type not in supported_constraints:
            continue

        constraint_params = constraint_config.get("params", {})
        constraint_instance = field_constraint_registry.get(constraint_type)
        db_constraints.append(
            constraint_instance.build_field_constraint(
                field, field.db_column, **constraint_params
            )
        )
    return db_constraints


def get_field_constraints_from_field(
    field: Field, model
) -> List[CheckConstraint | UniqueConstraint]:
    """
    Return existing field constraints for a field
    """

    from baserow.contrib.database.fields.registries import field_constraint_registry

    if not field.field_constraints:
        return []

    db_constraints = []

    for constraint_config in field.field_constraints:
        constraint_type = constraint_config.get("type")
        constraint_params = constraint_config.get("params", {})
        constraint_instance = field_constraint_registry.get(constraint_type)
        if constraint_instance:
            db_constraints.append(
                constraint_instance.build_field_constraint(
                    field, field.db_column, **constraint_params
                )
            )
    return db_constraints


class FieldValueConstraint(Instance):
    """
    Base class for field value constraints.
    """

    type = None

    def get_constraint_name(self, field, field_name):
        return f"{field_name}_{self.type}"

    def build_field_constraint(self, field, field_name, **kwargs):
        raise NotImplementedError(
            "The build_field_constraint method must be implemented in subclass."
        )


class UniqueWithEmptyConstraint(FieldValueConstraint):
    type = "unique_with_empty"

    def build_field_constraint(self, field, field_name, **kwargs):
        return django_models.UniqueConstraint(
            fields=[field_name],
            condition=(
                django_models.Q(trashed=False)
                & ~django_models.Q(**{f"{field_name}__isnull": True})
            ),
            name=self.get_constraint_name(field, field_name),
        )


class TextTypeUniqueWithEmptyConstraint(FieldValueConstraint):
    type = "text_type_unique_with_empty"

    def build_field_constraint(self, field, field_name, **kwargs):
        return django_models.UniqueConstraint(
            fields=[field_name],
            condition=(
                django_models.Q(trashed=False)
                & ~django_models.Q(**{f"{field_name}__isnull": True})
                & ~django_models.Q(**{field_name: ""})
            ),
            name=self.get_constraint_name(field, field_name),
        )


class RatingTypeUniqueWithEmptyConstraint(FieldValueConstraint):
    type = "rating_type_unique_with_empty"

    def build_field_constraint(self, field, field_name, **kwargs):
        return django_models.UniqueConstraint(
            fields=[field_name],
            condition=(
                django_models.Q(trashed=False)
                & ~django_models.Q(**{f"{field_name}__isnull": True})
                & ~django_models.Q(**{f"{field_name}": 0})
            ),
            name=self.get_constraint_name(field, field_name),
        )


class TextTypeNotEmptyConstraint(FieldValueConstraint):
    type = "text_type_not_empty"

    def build_field_constraint(self, field, field_name, **kwargs):
        return django_models.CheckConstraint(
            check=(
                ~django_models.Q(**{f"{field_name}__isnull": True})
                & ~django_models.Q(**{field_name: ""})
            ),
            name=self.get_constraint_name(field, field_name),
        )


class TextTypeUniqueConstraint(FieldValueConstraint):
    type = "text_type_unique"

    def build_field_constraint(self, field, field_name, **kwargs):
        return django_models.UniqueConstraint(
            fields=[field_name],
            condition=django_models.Q(trashed=False),
            name=self.get_constraint_name(field, field_name),
        )
