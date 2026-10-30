class ServiceFilterTargetDoesNotExist(Exception):
    """Raised when the service whose filters must change cannot be found."""


class ServiceFilterTargetNotSupported(Exception):
    """Raised when the target's service cannot be filtered."""
