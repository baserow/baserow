from abc import ABC, abstractmethod
from typing import Any

from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.registry import Instance, Registry

DEFAULT_CODE_RUNNER_TYPE = "wasmtime_quickjs"


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


class CodeRunnerType(Instance, ABC):
    @abstractmethod
    def run(self, context_data: dict[str, Any], code: str) -> dict[str, Any]:
        """
        Execute the provided code with the given context data.

        The JavaScript code must define a `main(context)` function and return a plain
        object.
        """


class CodeRunnerTypeRegistry(Registry[CodeRunnerType]):
    name = "code_runner"
    does_not_exist_exception_class = CodeRunnerTypeDoesNotExist


code_runner_type_registry: CodeRunnerTypeRegistry = CodeRunnerTypeRegistry()


def get_code_runner(code_runner_type: str | None = None) -> CodeRunnerType:
    code_runner_type = code_runner_type or DEFAULT_CODE_RUNNER_TYPE

    try:
        return code_runner_type_registry.get(code_runner_type)
    except CodeRunnerTypeDoesNotExist as exc:
        raise CodeRunnerImproperlyConfigured(
            f"The code runner {code_runner_type} is not registered."
        ) from exc
