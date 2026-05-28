import json
import subprocess  # nosec
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from django.conf import settings


class CodeRunnerException(Exception):
    """Base exception for code runner failures."""


class CodeRunnerImproperlyConfigured(CodeRunnerException):
    """Raised when a code runner is missing required configuration."""


class CodeRunnerExecutionError(CodeRunnerException):
    """Raised when the underlying code runtime fails."""


class CodeRunnerResultError(CodeRunnerException):
    """Raised when the executed code returns an unsupported result."""


class CodeRunner(ABC):
    @abstractmethod
    def run(self, context_data: dict[str, Any], code: str) -> dict[str, Any]:
        """
        Execute the provided code with the given context data.

        The JavaScript code must export a default `main(context)` function and return
        a plain object.
        """


class WasmtimeQuickJSCodeRunner(CodeRunner):
    """
    Runs user JavaScript in a QuickJS WASI module launched by wasmtime.
    """

    def __init__(
        self,
        wasmtime_executable: str | None = None,
        quickjs_wasm_path: str | None = None,
        timeout_seconds: int | None = None,
    ):
        self.wasmtime_executable = wasmtime_executable or getattr(
            settings,
            "BASEROW_ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE",
            "wasmtime",
        )
        self.quickjs_wasm_path = quickjs_wasm_path or getattr(
            settings,
            "BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH",
            "",
        )
        self.timeout_seconds = timeout_seconds or getattr(
            settings,
            "BASEROW_ENTERPRISE_CODE_RUNNER_TIMEOUT_SECONDS",
            5,
        )

    def run(self, context_data: dict[str, Any], code: str) -> dict[str, Any]:
        if not self.quickjs_wasm_path:
            raise CodeRunnerImproperlyConfigured(
                "The QuickJS WASM runtime path is not configured."
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            context_path = temporary_path / "context.json"
            user_code_path = temporary_path / "user_code.mjs"
            runner_path = temporary_path / "runner.mjs"

            context_path.write_text(json.dumps(context_data), encoding="utf-8")
            user_code_path.write_text(code, encoding="utf-8")
            runner_path.write_text(self._runner_source(), encoding="utf-8")

            completed_process = self._run_process(temporary_path, runner_path.name)

        try:
            payload = json.loads(completed_process.stdout)
        except json.JSONDecodeError as exc:
            raise CodeRunnerExecutionError(
                "The code runner returned an invalid response."
            ) from exc

        if "error" in payload:
            raise CodeRunnerExecutionError(payload["error"])

        result = payload.get("result")
        if not isinstance(result, dict):
            raise CodeRunnerResultError("The code must return an object.")

        return result

    def _run_process(
        self, temporary_path: Path, runner_file_name: str
    ) -> subprocess.CompletedProcess:
        command = [
            self.wasmtime_executable,
            "run",
            "--dir",
            f"{temporary_path}::.",
            self.quickjs_wasm_path,
            "--std",
            runner_file_name,
        ]

        try:
            return subprocess.run(  # noqa: S603
                command,
                cwd=temporary_path,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise CodeRunnerExecutionError("The code runner timed out.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise CodeRunnerExecutionError(message) from exc
        except OSError as exc:
            raise CodeRunnerExecutionError(str(exc)) from exc

    def _runner_source(self) -> str:
        return """
import main from "./user_code.mjs";

try {
  const context = JSON.parse(std.loadFile("context.json"));
  const result = main(context);
  std.out.puts(JSON.stringify({ result }) + "\\n");
} catch (error) {
  const message = String(error && error.message || error);
  std.out.puts(JSON.stringify({ error: message }) + "\\n");
}
""".strip()


def get_code_runner() -> CodeRunner:
    return WasmtimeQuickJSCodeRunner()
