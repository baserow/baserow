ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST = (
    "ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST",
    404,
    "There is no integration type of that name that connects an account.",
)
ERROR_OAUTH_NOT_CONFIGURED = (
    "ERROR_OAUTH_NOT_CONFIGURED",
    400,
    "This Baserow installation isn't set up to connect accounts of this provider.",
)
ERROR_OAUTH_STATE_INVALID = (
    "ERROR_OAUTH_STATE_INVALID",
    400,
    "This sign-in expired, was already used or was started by someone else. Try "
    "connecting again.",
)
ERROR_OAUTH_FAILED = ("ERROR_OAUTH_FAILED", 400, "{e.message}")
ERROR_OAUTH_SIGN_IN_CANCELLED = (
    "ERROR_OAUTH_SIGN_IN_CANCELLED",
    400,
    "The sign-in was cancelled.",
)
# The detail is the admin consent URL, for the page to show. It can be empty.
ERROR_OAUTH_ADMIN_CONSENT_REQUIRED = (
    "ERROR_OAUTH_ADMIN_CONSENT_REQUIRED",
    400,
    "{e.admin_consent_url}",
)
ERROR_OAUTH_TENANT_NOT_ALLOWED = (
    "ERROR_OAUTH_TENANT_NOT_ALLOWED",
    400,
    "This Baserow installation doesn't accept accounts of this organisation.",
)
ERROR_OAUTH_CLIENT_REJECTED = (
    "ERROR_OAUTH_CLIENT_REJECTED",
    400,
    "The provider refused the OAuth app the sign-in goes through, maybe because "
    "its secret expired. Contact your Baserow admin.",
)
ERROR_OAUTH_ACCOUNT_MISMATCH = (
    "ERROR_OAUTH_ACCOUNT_MISMATCH",
    400,
    "You signed in as another account than the one connected. Create another "
    "integration to connect it.",
)
ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED = (
    "ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED",
    400,
    "The account can't be connected for one of these actions.",
)
