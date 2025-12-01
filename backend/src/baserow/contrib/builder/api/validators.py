from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.core.user_files.models import UserFile


def login_page_id_validator(value: int) -> int:
    """Validate the Builder's login_page."""

    try:
        # Although only possible via the API, setting the login_page to the
        # shared page shouldn't be allowed because the shared page isn't
        # a real page.
        if value and PageHandler().get_page(value).shared:
            raise DRFValidationError(
                detail="The login page cannot be a shared page.",
                code="invalid_login_page_id",
            )
    except PageDoesNotExist as exc:
        raise DRFValidationError(
            detail=f"The login page with id {value} doesn't exist.",
            code="invalid_login_page_id",
        ) from exc

    return value


def image_file_validation(file: UserFile) -> None:
    """
    Validate that the file that is being set as the image source, is in fact an image

    :param file: The image file
    :raises ValidationError: If the file does not exist or is not an image
    """

    if not file.is_image:
        raise ValidationError(f"The file with name {file.name} is not an image")
