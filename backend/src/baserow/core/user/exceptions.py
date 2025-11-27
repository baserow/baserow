class UserNotFound(Exception):
    """Raised when a user with given parameters is not found."""


class UserAlreadyExist(Exception):
    """Raised when a user could not be created because the email already exists."""


class InvalidVerificationToken(Exception):
    """Raised when the provided token is invalid."""


class EmailAlreadyVerified(Exception):
    """Raised when the user's email is verified already."""


class PasswordDoesNotMatchValidation(Exception):
    """Raised when the provided password does not match validation."""


class InvalidPassword(Exception):
    """Raised when the provided password is incorrect."""


class UserIsLastAdmin(Exception):
    """
    Raised when a user wants to delete himself but is the last instance wide admin.
    """


class DisabledSignupError(Exception):
    """
    Raised when a user account is created when the new signup setting is disabled.
    """


class ResetPasswordDisabledError(Exception):
    """Raised when a password reset is attempted but the password reset is disabled."""


class DeactivatedUserException(Exception):
    pass


class RefreshTokenAlreadyBlacklisted(Exception):
    """Raised when the provided refresh token is already blacklisted."""


class ChangeEmailNotAllowed(Exception):
    """Raised when a user without a password tries to change their email."""


class EmailAlreadyChanged(Exception):
    """Raised when the email has already been changed to the requested address."""
