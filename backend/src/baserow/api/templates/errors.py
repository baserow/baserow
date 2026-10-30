from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_TEMPLATE_DOES_NOT_EXIST = (
    "ERROR_TEMPLATE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested template does not exist.",
)
ERROR_TEMPLATE_FILE_DOES_NOT_EXIST = (
    "ERROR_TEMPLATE_FILE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The requested template file does not exist anymore.",
)
ERROR_INVALID_TEMPLATE_ICON = (
    "ERROR_INVALID_TEMPLATE_ICON",
    HTTP_400_BAD_REQUEST,
    "The icon of the template is not allowed.",
)
ERROR_INVALID_TEMPLATE_CATEGORY = (
    "ERROR_INVALID_TEMPLATE_CATEGORY",
    HTTP_400_BAD_REQUEST,
    "The categories of the template are missing or do not exist.",
)
ERROR_TEMPLATE_HAS_NO_CONTENT = (
    "ERROR_TEMPLATE_HAS_NO_CONTENT",
    HTTP_400_BAD_REQUEST,
    "The content of the template was removed.",
)
ERROR_NO_APPLICATIONS_SELECTED = (
    "ERROR_NO_APPLICATIONS_SELECTED",
    HTTP_400_BAD_REQUEST,
    "At least one application must be selected.",
)
ERROR_TEMPLATE_BLOCKED = (
    "ERROR_TEMPLATE_BLOCKED",
    HTTP_400_BAD_REQUEST,
    "The template is blocked and can't be installed.",
)
ERROR_TEMPLATE_UPDATED = (
    "ERROR_TEMPLATE_UPDATED",
    HTTP_400_BAD_REQUEST,
    "The template was updated after it was opened.",
)
# Same code as `ERROR_TEMPLATE_BLOCKED`, for approving or rejecting a template.
ERROR_TEMPLATE_BLOCKED_REVIEW = (
    "ERROR_TEMPLATE_BLOCKED",
    HTTP_400_BAD_REQUEST,
    "The template is blocked, so it can't be approved or rejected.",
)
ERROR_TEMPLATE_ALREADY_APPROVED = (
    "ERROR_TEMPLATE_ALREADY_APPROVED",
    HTTP_400_BAD_REQUEST,
    "The template was already approved since it was opened.",
)
ERROR_TEMPLATE_ALREADY_REJECTED = (
    "ERROR_TEMPLATE_ALREADY_REJECTED",
    HTTP_400_BAD_REQUEST,
    "The template was already rejected since it was opened.",
)
ERROR_TEMPLATE_NOT_REVIEWABLE = (
    "ERROR_TEMPLATE_NOT_REVIEWABLE",
    HTTP_400_BAD_REQUEST,
    "The template can't be approved or rejected in its current state.",
)
ERROR_PUBLIC_LISTING_CONSENT_REQUIRED = (
    "ERROR_PUBLIC_LISTING_CONSENT_REQUIRED",
    HTTP_400_BAD_REQUEST,
    "Making a template public needs its author to agree that it's listed, with "
    "their name, for everybody on this instance.",
)
