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
        fuel_limit: int | None = None,
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
        self.fuel_limit = (
            fuel_limit
            if fuel_limit is not None
            else getattr(settings, "ENTERPRISE_CODE_RUNNER_FUEL_LIMIT", 100_000_000)
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
        # Using wastime with no host access at all for best security
        command = [
            self.wasmtime_executable,
            "run",
            "-W",
            f"timeout={self.timeout_seconds}s",  # Limits the execution time
            "-W",
            f"max-memory-size={self.memory_limit_bytes}",  # Limits memory consumption
            "-W",
            "trap-on-grow-failure=true",  # Ensure a proper exception on memory limit
        ]
        # Fuel limit allow a precise number of instruction to be executed
        # Extra security in addition to memory and timeout.
        if self.fuel_limit > 0:
            command.extend(["-W", f"fuel={self.fuel_limit}"])

        command.extend(
            [
                self.quickjs_wasm_path,
                "--std",  # Give access to STD but it's removed in JS code
                "--eval",
                self._runner_source(),
            ]
        )
        # We send the context data and the code through STDIN to the js process
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
        """
        Run the code runner command with the given stdin payload.

        This intentionally avoids subprocess.communicate() so stdout and stderr can
        be read incrementally by _read_bounded_process_output(), enforcing both the
        execution timeout and per-stream output size limit while the process is
        still running. If setup, writing, reading, or waiting fails, the child
        process is killed before the original exception is re-raised.
        """

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
        """
        Read stdout and stderr from a running process without blocking indefinitely.

        Both streams are switched to nonblocking mode and monitored together so a
        full stderr pipe cannot block stdout, or vice versa. Reading continues
        until both streams close, the configured timeout expires, or either stream
        exceeds the configured output size limit.
        """

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
        """
        Build the JavaScript wrapper that QuickJS evaluates before running
        user-submitted code.

        Security model
        --------------
        The real isolation boundary is Wasmtime + WASI: the guest is launched
        with no --dir, no --env, and no inherit-network/env capabilities, so
        user code has no host I/O surface even with arbitrary JS execution
        inside the guest. Do not weaken those flags on the assumption that the
        scrubbing in this wrapper provides containment — it does not.

        Defense in depth (this wrapper)
        -------------------------------
        qjs --std injects bridge globals (std, os, bjson, print, console,
        scriptArgs, ...) that connect JS to host capabilities. We capture the
        I/O we need into closure-local references and then ``delete`` those
        globals so user code cannot reach them, even after recovering a real
        ``Function`` via tricks like ``(function(){}).constructor``. This is
        safe because this QuickJS build does NOT register std/os/bjson as
        importable modules either (dynamic ``import("std")`` raises
        "could not load module"), so deletion from globalThis is sufficient at
        the JS layer.

        We intentionally do NOT shadow ECMAScript intrinsics such as
        ``Function``, ``eval``, or ``globalThis``: such shadowing is bypassed
        in one line via the constructor-escape trick, and pretending otherwise
        creates a false sense of security. Those intrinsics are harmless on
        their own — they grant no host access without bridge globals.
        """
        return """
const _stdOutPuts = std.out.puts.bind(std.out);
try {
  const _input = JSON.parse(std.in.getline());
  const _createFunction = Function;

  // Delete the qjs --std bridge globals so user code cannot reach host I/O.
  // Wasmtime + WASI is the real isolation boundary; this is defense in
  // depth. Keep this list in sync with what qjs --std injects.
  const _HOST_GLOBALS = [
    "std", "os", "bjson",
    "print", "console",
    "scriptArgs", "execArgv", "argv0",
    "gc", "queueMicrotask", "performance", "navigator",
    "atob", "btoa",
  ];
  for (const _name of _HOST_GLOBALS) {
    delete globalThis[_name];
  }

  const run = _createFunction("context", `
    "use strict";
    ${_input.code}
    if (typeof main !== "function") {
      throw new Error("The code must define a main function.");
    }
    return main(context);
  `);
  const result = run(_input.context);
  _stdOutPuts(JSON.stringify({ result }) + "\\n");
} catch (error) {
  _stdOutPuts(JSON.stringify({ error: String(error && error.message || error) }) + "\\n");
}
""".strip()
