from abc import ABC, abstractmethod
from typing import Any

from django.conf import settings

from baserow.core.code_runner.exceptions import (
    CodeRunnerImproperlyConfigured,
    CodeRunnerTypeDoesNotExist,
)
from baserow.core.registry import Instance, Registry


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
    code_runner_type = code_runner_type or getattr(
        settings, "ENTERPRISE_CODE_RUNNER_DEFAULT_TYPE", ""
    )

    if not code_runner_type:
        raise CodeRunnerImproperlyConfigured(
            "The default code runner type is not configured."
        )

    try:
        return code_runner_type_registry.get(code_runner_type)
    except CodeRunnerTypeDoesNotExist as exc:
        raise CodeRunnerImproperlyConfigured(
            f"The code runner {code_runner_type} is not registered."
        ) from exc
