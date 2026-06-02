from baserow.core.exceptions import InstanceTypeDoesNotExist


class CodeRunnerException(Exception):
    """Base exception for code runner failures."""


class CodeRunnerTypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when the requested code runner type does not exist."""


class CodeRunnerImproperlyConfigured(CodeRunnerException):
    """Raised when a code runner is missing required configuration."""


class CodeRunnerExecutionError(CodeRunnerException):
    """Raised when the underlying code runtime fails."""


class CodeRunnerResultError(CodeRunnerException):
    """Raised when the executed code returns an unsupported result."""
