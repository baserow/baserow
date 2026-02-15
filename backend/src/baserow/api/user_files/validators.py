from rest_framework.exceptions import ValidationError

from baserow.core.user_files.exceptions import InvalidUserFileNameError
from baserow.core.user_files.models import UserFile


def user_file_name_validator(value):
    """
    Validates that a file name is in the correct generated format.
    
    This validator ensures that file names follow the pattern: unique_hash.extension
    where both unique and hash are alphanumeric strings. This is the format used
    by Baserow's file upload system.
    
    :param value: The file name to validate
    :raises ValidationError: If the file name is not in the correct format
    """
    try:
        UserFile.deconstruct_name(value)
    except InvalidUserFileNameError as e:
        raise ValidationError(
            f"Invalid file name format: {e.name}. "
            f"Expected format: 'unique_hash.extension' with alphanumeric unique and hash. "
            f"Please use the file name returned from the upload endpoint.",
            code="invalid_file_name",
        )
