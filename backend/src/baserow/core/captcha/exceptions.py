from baserow.core.exceptions import InstanceTypeDoesNotExist


class CaptchaVerificationFailed(Exception):
    """Raised when captcha token validation fails."""


class CaptchaProviderDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when the requested captcha provider type does not exist."""
