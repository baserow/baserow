from typing import List

from django.db import models as django_models

from baserow.contrib.database.fields.constants import UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
from baserow.contrib.database.fields.field_types import (
    DateFieldType,
    DurationFieldType,
    EmailFieldType,
    FieldType,
    LongTextFieldType,
    NumberFieldType,
    RatingFieldType,
    SingleSelectFieldType,
    TextFieldType,
    URLFieldType,
)
from baserow.core.registry import Instance


class FieldValueConstraint(Instance):
    """
    Base class for field value constraints.
    """

    type = None
    constraint_name = None
    can_support_default_value = None

    def get_constraint_name(self, field, field_name):
        return f"{field_name}_{self.type}"

    def build_field_constraint(self, field, field_name, **kwargs):
        raise NotImplementedError(
            "The build_field_constraint method must be implemented in subclass."
        )

    def get_compatible_field_types(self) -> List[str]:
        return []

    def is_field_type_compatible(self, field_type: FieldType):
        return field_type.type in self.get_compatible_field_types()


class UniqueWithEmptyConstraint(FieldValueConstraint):
    type = "generic_unique_with_empty"
    constraint_name = UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
    can_support_default_value = False

    def build_field_constraint(self, field, field_name, **kwargs):
        return django_models.UniqueConstraint(
            fields=[field_name],
            condition=(
                django_models.Q(trashed=False)
                & ~django_models.Q(**{f"{field_name}__isnull": True})
            ),
            name=self.get_constraint_name(field, field_name),
        )

    def get_compatible_field_types(self) -> List[str]:
        return [
            NumberFieldType.type,
            DateFieldType.type,
            DurationFieldType.type,
            SingleSelectFieldType.type,
        ]


class TextTypeUniqueWithEmptyConstraint(FieldValueConstraint):
    type = "text_type_unique_with_empty"
    constraint_name = UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
    can_support_default_value = False

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

    def get_compatible_field_types(self) -> List[str]:
        return [
            TextFieldType.type,
            LongTextFieldType.type,
            URLFieldType.type,
            EmailFieldType.type,
        ]


class RatingTypeUniqueWithEmptyConstraint(FieldValueConstraint):
    type = "rating_type_unique_with_empty"
    constraint_name = UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
    can_support_default_value = False

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

    def get_compatible_field_types(self) -> List[str]:
        return [RatingFieldType.type]
