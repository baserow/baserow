import json
import os
import selectors
import subprocess  # nosec
import time
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
    output_size_limit_bytes = 1024 * 1024

    def __init__(
        self,
        wasmtime_executable: str | None = None,
        quickjs_wasm_path: str | None = None,
        timeout_seconds: int | None = None,
        memory_limit_bytes: int | None = None,
        output_size_limit_bytes: int | None = None,
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
        self.memory_limit_bytes = memory_limit_bytes or getattr(
            settings,
            "ENTERPRISE_CODE_RUNNER_MEMORY_LIMIT_BYTES",
            64 * 1024 * 1024,
        )
        self.output_size_limit_bytes = (
            output_size_limit_bytes or self.output_size_limit_bytes
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
            "-W",
            f"timeout={self.timeout_seconds}s",
            "-W",
            f"max-memory-size={self.memory_limit_bytes}",
            "-W",
            "trap-on-grow-failure=true",
            self.quickjs_wasm_path,
            "--std",
            "--eval",
            self._runner_source(),
        ]
        payload = json.dumps({"context": context_data, "code": code})

        try:
            completed_process = self._communicate_with_output_limit(command, payload)
        except subprocess.TimeoutExpired as exc:
            raise CodeRunnerExecutionError("The code runner timed out.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise CodeRunnerExecutionError(message) from exc
        except OSError as exc:
            raise CodeRunnerExecutionError(str(exc)) from exc

        if completed_process.returncode != 0:
            message = (
                completed_process.stderr.strip()
                or completed_process.stdout.strip()
                or f"Command returned non-zero exit status {completed_process.returncode}."
            )
            raise CodeRunnerExecutionError(message)

        return completed_process

    def _communicate_with_output_limit(
        self, command: list[str], payload: str
    ) -> subprocess.CompletedProcess:
        process = subprocess.Popen(  # noqa: S603
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            if process.stdin is None:
                raise CodeRunnerExecutionError(
                    "The code runner stdin pipe was not created."
                )
            process.stdin.write(payload.encode())
            process.stdin.close()

            stdout, stderr = self._read_bounded_process_output(process)
            return subprocess.CompletedProcess(
                command,
                process.wait(timeout=0),
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
            )
        except Exception:
            if process.poll() is None:
                process.kill()
                process.wait()
            raise

    def _read_bounded_process_output(
        self, process: subprocess.Popen
    ) -> tuple[bytes, bytes]:
        if process.stdout is None or process.stderr is None:
            raise CodeRunnerExecutionError(
                "The code runner output pipes were not created."
            )

        selector = selectors.DefaultSelector()
        streams = {
            process.stdout: bytearray(),
            process.stderr: bytearray(),
        }

        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)

        deadline = time.monotonic() + self.timeout_seconds

        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, self.timeout_seconds)

            for key, _ in selector.select(timeout=remaining):
                stream = key.fileobj
                chunk = stream.read(8192)
                if not chunk:
                    selector.unregister(stream)
                    continue

                output = streams[stream]
                output.extend(chunk)
                if len(output) > self.output_size_limit_bytes:
                    raise CodeRunnerExecutionError(
                        "The code runner produced too much output."
                    )

        return bytes(streams[process.stdout]), bytes(streams[process.stderr])

    def _runner_source(self) -> str:
        return """
try {
  const input = JSON.parse(std.in.getline());
  const write = std.out.puts.bind(std.out);
  const createFunction = Function;
  const originalEval = globalThis.eval;
  const originalFunction = globalThis.Function;
  delete globalThis.std;
  delete globalThis.os;
  delete globalThis.bjson;
  globalThis.eval = undefined;
  globalThis.Function = undefined;
  try {
    const run = createFunction("context", `
      "use strict";
      const std = undefined;
      const os = undefined;
      const bjson = undefined;
      const Function = undefined;
      const print = undefined;
      const globalThis = undefined;
      ${input.code}
      if (typeof main !== "function") {
        throw new Error("The code must define a main function.");
      }
      return main(context);
    `);
    const result = run(input.context);
    write(JSON.stringify({ result }) + "\\n");
  } finally {
    globalThis.eval = originalEval;
    globalThis.Function = originalFunction;
  }
} catch (error) {
  const message = String(error && error.message || error);
  print(JSON.stringify({ error: message }));
}
""".strip()
