from django.core.exceptions import ValidationError

from baserow.core.exceptions import (
    InstanceTypeAlreadyRegistered,
    InstanceTypeDoesNotExist,
    LockConflict,
)


class FieldTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class FieldTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class FieldNotInTable(Exception):
    """Raised when the field does not belong to a table."""


class FieldDoesNotExist(Exception):
    """Raised when the requested field does not exist."""


class IncompatibleField(Exception):
    """Raised when the field doesn't have the required field type."""


class PrimaryFieldAlreadyExists(Exception):
    """Raised if a primary field is created, but is already exists for the table."""


class CannotDeletePrimaryField(Exception):
    """Raised if the user tries to delete the primary field which is not allowed."""


class CannotChangeFieldType(Exception):
    """Raised if the field type cannot be altered."""


class CannotCreateFieldType(Exception):
    """Raised if the field type cannot be created at the moment."""


class LinkRowTableNotProvided(Exception):
    """
    Raised when a link row field is trying to be created without the provided link
    row table.
    """


class LinkRowTableNotInSameDatabase(Exception):
    """
    Raised when the desired link row table is not in the same database as the table.
    """


class SelfReferencingLinkRowCannotHaveRelatedField(Exception):
    """
    Raised when a self referencing link row field is trying to be created with a
    related field.
    """


class MaxFieldLimitExceeded(Exception):
    """Raised when the field count exceeds the limit"""


class MaxFieldNameLengthExceeded(Exception):
    """Raised when the field name exceeds the max length."""

    def __init__(self, max_field_name_length, *args, **kwargs):
        self.max_field_name_length = max_field_name_length
        super().__init__(*args, **kwargs)


class OrderByFieldNotFound(Exception):
    """Raised when the field was not found in the table."""

    def __init__(self, field_name=None, *args, **kwargs):
        self.field_name = field_name
        super().__init__(*args, **kwargs)


class OrderByFieldNotPossible(Exception):
    """Raised when it is not possible to order by a field."""

    def __init__(
        self,
        field_name: str = None,
        field_type: str = None,
        sort_type: str = None,
        *args: list,
        **kwargs: dict,
    ):
        self.field_name = field_name
        self.field_type = field_type
        self.sort_type = sort_type
        super().__init__(*args, **kwargs)


class FilterFieldNotFound(Exception):
    """Raised when the field was not found in the table."""

    def __init__(self, field_name=None, *args, **kwargs):
        self.field_name = field_name
        super().__init__(*args, **kwargs)


class IncompatiblePrimaryFieldTypeError(Exception):
    """Raised when the primary field is changed to an incompatible field type."""

    def __init__(self, field_type=None, *args, **kwargs):
        self.field_type = field_type
        super().__init__(*args, **kwargs)


class DbIndexNotSupportedError(Exception):
    """Raised when trying to enable a db_index to a field that doesn't support is."""

    def __init__(self, field_type=None, *args, **kwargs):
        self.field_type = field_type
        super().__init__(*args, **kwargs)


class FieldWithSameNameAlreadyExists(Exception):
    """
    Raised when a field is created or updated with a name that matches an
    existing fields name in the same table.
    """


class ReservedBaserowFieldNameException(Exception):
    """
    Raised when a field is created or updated with a name that matches a reserved
    Baserow field name.
    """


class InvalidBaserowFieldName(Exception):
    """
    Raised when a field name is not provided or an invalid blank field name is
    provided.
    """


class AllProvidedValuesMustBeIntegersOrStrings(ValidationError):
    """
    Raised when one tries to create or update a row for a multivalued field that
    contains a value other than an integer or a string.
    """

    def __init__(self, ids, *args, **kwargs):
        if not isinstance(ids, list):
            ids = [ids]
        self.ids = ids
        msg = (
            f"The provided values '{self.ids}' are not valid integers or strings."
            if len(self.ids) > 1
            else f"The provided value '{self.ids}' is not a valid integer or string."
        )
        super().__init__(
            msg,
            code="invalid_value",
            *args,
            **kwargs,
        )


class AllProvidedMultipleSelectValuesMustBeSelectOption(ValidationError):
    """
    Raised when one tries to create or update a row for a MultipleSelectField that
    contains a SelectOption ID that either does not exists or does not belong to the
    field.
    """

    def __init__(self, values, *args, **kwargs):
        if not isinstance(values, list):
            values = [values]
        self.values = values
        msg = (
            f"The provided select option values {self.values} are not valid select options."
            if len(self.values) > 1
            else f"The provided select option value '{self.values[0]}' is not a valid select "
            "option."
        )
        super().__init__(
            msg,
            *args,
            code="invalid_option",
            **kwargs,
        )


class AllProvidedCollaboratorIdsMustBeValidUsers(ValidationError):
    """
    Raised when the provided user ids don't exist or cannot be used
    as collaborators.
    """

    def __init__(self, ids, *args, **kwargs):
        if not isinstance(ids, list):
            ids = [ids]
        self.ids = ids
        msg = (
            f"The provided user ids {self.ids} are not valid collaborators."
            if len(self.ids) > 1
            else f"The provided user id {self.ids} is not a valid collaborator."
        )
        super().__init__(
            msg,
            *args,
            code="invalid_collaborator",
            **kwargs,
        )


class InvalidCountThroughField(Exception):
    """
    Raised when a count field is attempted to be created or updated with a through a
    field that does not exist, is in a different table or is not a link row field.
    """


class InvalidRollupThroughField(Exception):
    """
    Raised when a rollup field is attempted to be created or updated with a through a
    field that does not exist, is in a different table or is not a link row field.
    """


class InvalidRollupTargetField(Exception):
    """
    Raised when a rollup field is attempted to be created or updated with a target
    field that does not exist or is not in the through fields linked table.
    """


class InvalidLookupThroughField(Exception):
    """
    Raised when a a lookup field is attempted to be created or updated with a through
    field that does not exist, is in a different table or is not a link row field.
    """


class InvalidLookupTargetField(Exception):
    """
    Raised when a lookup field is attempted to be created or updated with a target
    field that does not exist or is not in the through fields linked table.
    """


class IncompatibleFieldTypeForUniqueValues(Exception):
    """Raised when the unique values of an incompatible field are requested."""


class FailedToLockFieldDueToConflict(LockConflict):
    """
    Raised when a user tried to update a field which was locked by another
    concurrent operation
    """


class DateForceTimezoneOffsetValueError(ValueError):
    """
    Raised when the force_timezone_offset value offset cannot be set.
    """


class ReadOnlyFieldHasNoInternalDbValueError(Exception):
    """
    Raised when a read only field is trying to get its internal db value.
    This is because there is no valid value that can be returned which can then pass
    through "prepare_value_for_db" for a read_only field."
    """


class RichTextFieldCannotBePrimaryField(Exception):
    """
    Raised when a rich text field is attempted to be set as the primary field.
    """


class FieldIsAlreadyPrimary(Exception):
    """
    Raised when the new primary field is already the primary field.
    """


class TableHasNoPrimaryField(Exception):
    """
    Raised when the table doesn't have a primary field.
    """


class ImmutableFieldType(Exception):
    """
    Raised when trying to change the field type and the field type immutable.
    """


class FieldConstraintException(Exception):
    """
    Raised when a field constraint cannot be applied due to existing data conflicts.
    """

    def __init__(self, constraint_type=None, *args, **kwargs):
        self.constraint_type = constraint_type
        super().__init__(*args, **kwargs)


class FieldConstraintDoesNotSupportDefaultValueError(FieldConstraintException):
    """
    Raised when a constraint is being set but the field has a default value and the
    constraint does not support it.
    """


class ImmutableFieldProperties(Exception):
    """
    Raised when trying to change any of the field properties and the field properties
    are immutable.
    """


class SelectOptionDoesNotBelongToField(Exception):
    """
    Raised when the provided select option does not belong to the select options
    in the field.
    """

    def __init__(self, select_option_id=None, field_id=None, *args, **kwargs):
        self.select_option_id = select_option_id
        self.field_id = field_id
        super().__init__(*args, **kwargs)


class FieldDataConstraintException(Exception):
    """
    Raised when a data operation violates a field constraint.
    """


class InvalidFieldConstraint(Exception):
    """
    Raised when a field constraint is invalid.
    """

    def __init__(self, field_type=None, constraint_type=None, *args, **kwargs):
        self.constraint_type = constraint_type
        self.field_type = field_type
        super().__init__(*args, **kwargs)


class InvalidPasswordFieldPassword(Exception):
    """Raised when the provided password field is invalid."""
