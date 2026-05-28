import json
import subprocess  # nosec
from typing import Any

from django.conf import settings

from baserow.core.code_runner.registries import (
    CodeRunnerExecutionError,
    CodeRunnerImproperlyConfigured,
    CodeRunnerResultError,
    CodeRunnerType,
)


class WasmtimeQuickJSCodeRunnerType(CodeRunnerType):
    """
    Runs user JavaScript in a QuickJS WASI module launched by wasmtime.
    """

    type = "wasmtime_quickjs"

    def __init__(
        self,
        wasmtime_executable: str | None = None,
        quickjs_wasm_path: str | None = None,
        timeout_seconds: int | None = None,
    ):
        self.wasmtime_executable = wasmtime_executable or getattr(
            settings,
            "ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE",
            "wasmtime",
        )
        self.quickjs_wasm_path = quickjs_wasm_path or getattr(
            settings,
            "ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH",
            "",
        )
        self.timeout_seconds = timeout_seconds or getattr(
            settings,
            "ENTERPRISE_CODE_RUNNER_TIMEOUT_SECONDS",
            5,
        )

    def run(self, context_data: dict[str, Any], code: str) -> dict[str, Any]:
        if not self.quickjs_wasm_path:
            raise CodeRunnerImproperlyConfigured(
                "The QuickJS WASM runtime path is not configured."
            )

        completed_process = self._run_process(context_data, code)

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
        self, context_data: dict[str, Any], code: str
    ) -> subprocess.CompletedProcess:
        command = [
            self.wasmtime_executable,
            "run",
            self.quickjs_wasm_path,
            "--std",
            "--eval",
            self._runner_source(),
        ]
        payload = json.dumps({"context": context_data, "code": code})

        try:
            return subprocess.run(  # noqa: S603
                command,
                input=payload,
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
try {
  const input = JSON.parse(std.in.getline());
  const write = std.out.puts.bind(std.out);
  delete globalThis.std;
  delete globalThis.os;
  delete globalThis.bjson;
  globalThis.eval(input.code);
  const result = globalThis.main(input.context);
  delete globalThis.main;
  write(JSON.stringify({ result }) + "\\n");
} catch (error) {
  const message = String(error && error.message || error);
  print(JSON.stringify({ error: message }));
}
""".strip()
