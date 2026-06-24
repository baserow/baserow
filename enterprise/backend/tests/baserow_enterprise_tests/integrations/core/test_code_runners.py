import io
import os
import subprocess
import sys
from pathlib import Path
from shutil import which

from django.test import override_settings

import pytest

from baserow.core.code_runner.exceptions import (
    CodeRunnerExecutionError,
    CodeRunnerImproperlyConfigured,
    CodeRunnerResultError,
)
from baserow.core.code_runner.registries import (
    get_code_runner,
)
from baserow_enterprise.apps import register_code_runner_features
from baserow_enterprise.code_runner.code_runner_types import (
    WasmtimeQuickJSCodeRunnerType,
)

wasmtime_executable = os.environ.get(
    "BASEROW_ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE"
)
quickjs_wasm_path = os.environ.get("BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH")
runtime_variables_are_configured = (
    wasmtime_executable
    and (Path(wasmtime_executable).is_file() or which(wasmtime_executable))
    and quickjs_wasm_path
    and Path(quickjs_wasm_path).is_file()
)


@override_settings(
    ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE="wasmtime-test",
    ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH="/runtime/qjs.wasm",
    ENTERPRISE_CODE_RUNNER_TIMEOUT_SECONDS=7,
    ENTERPRISE_CODE_RUNNER_MEMORY_LIMIT_BYTES=1024 * 1024,
    ENTERPRISE_CODE_RUNNER_FUEL_LIMIT=100_000,
)
def test_wasmtime_quickjs_code_runner_runs_code_in_subprocess(monkeypatch):
    calls = []
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "payload = sys.stdin.read();"
                    'assert \'"context": {"value": 2}\' in payload;'
                    "assert 'function main(context)' in payload;"
                    'sys.stdout.write(\'{"result": {"newValue": 4}}\')'
                ),
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = WasmtimeQuickJSCodeRunnerType().run(
        {"value": 2},
        "function main(context) { return { newValue: context.value * 2 } }",
    )

    assert result == {"newValue": 4}
    command, kwargs = calls[0]
    assert command[:11] == [
        "wasmtime-test",
        "run",
        "-W",
        "timeout=7s",
        "-W",
        "max-memory-size=1048576",
        "-W",
        "trap-on-grow-failure=true",
        "-W",
        "fuel=100000",
        "/runtime/qjs.wasm",
    ]
    assert command[11] == "--std"
    assert command[12] == "--eval"
    assert "std.in.getline()" in command[13]
    assert 'createFunction("context"' in command[13]
    assert "globalThis.eval(input.code)" not in command[13]
    assert kwargs["stdin"] == subprocess.PIPE
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stderr"] == subprocess.PIPE


def test_wasmtime_quickjs_code_runner_uses_explicit_memory_limit(monkeypatch):
    calls = []
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); sys.stdout.write('{\"result\": {}}')",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(
        quickjs_wasm_path="/runtime/qjs.wasm",
        memory_limit_bytes=2 * 1024 * 1024,
    )

    runner.run({}, "function main() { return { newValue: 4 } }")

    assert "max-memory-size=2097152" in calls[0][0]


def test_wasmtime_quickjs_code_runner_uses_explicit_fuel_limit(monkeypatch):
    calls = []
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); sys.stdout.write('{\"result\": {}}')",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(
        quickjs_wasm_path="/runtime/qjs.wasm",
        fuel_limit=200_000,
    )

    runner.run({}, "function main() { return { newValue: 4 } }")

    assert "fuel=200000" in calls[0][0]


def test_wasmtime_quickjs_code_runner_reaps_process_with_remaining_timeout(
    monkeypatch,
):
    class RaceProcess:
        args = ["wasmtime"]
        stdin = io.BytesIO()

        def wait(self, timeout=None):
            assert timeout is not None
            assert timeout > 0
            return 0

        def poll(self):
            return 0

    class RaceRunner(WasmtimeQuickJSCodeRunnerType):
        def _write_process_input(self, process, payload, deadline):
            pass

        def _read_bounded_process_output(self, process, deadline):
            return b'{"result": {}}', b""

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: RaceProcess())

    runner = RaceRunner(quickjs_wasm_path="/runtime/qjs.wasm")

    assert runner.run({}, "function main() { return {} }") == {}


def test_wasmtime_quickjs_code_runner_can_disable_fuel_limit(monkeypatch):
    calls = []
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); sys.stdout.write('{\"result\": {}}')",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(
        quickjs_wasm_path="/runtime/qjs.wasm",
        fuel_limit=0,
    )

    runner.run({}, "function main() { return { newValue: 4 } }")

    assert not any(arg.startswith("fuel=") for arg in calls[0][0])


def unregister_code_runner_features(
    builder_workflow_action_registry,
    automation_node_type_registry,
    service_type_registry,
    code_runner_type_registry,
):
    builder_workflow_action_registry.registry.pop("code", None)
    automation_node_type_registry.registry.pop("code", None)
    service_type_registry.registry.pop("code", None)
    code_runner_type_registry.registry.pop("wasmtime_quickjs", None)


def test_wasmtime_quickjs_code_runner_type_is_registered(
    mutable_builder_workflow_action_registry,
    mutable_automation_node_type_registry,
    mutable_service_type_registry,
    mutable_code_runner_type_registry,
):
    unregister_code_runner_features(
        mutable_builder_workflow_action_registry,
        mutable_automation_node_type_registry,
        mutable_service_type_registry,
        mutable_code_runner_type_registry,
    )

    with override_settings(ENTERPRISE_CODE_RUNNER_DEFAULT_TYPE="wasmtime_quickjs"):
        register_code_runner_features()

    assert isinstance(
        mutable_code_runner_type_registry.get("wasmtime_quickjs"),
        WasmtimeQuickJSCodeRunnerType,
    )


def test_get_code_runner_requires_default_code_runner_type():
    with override_settings(ENTERPRISE_CODE_RUNNER_DEFAULT_TYPE=""):
        with pytest.raises(CodeRunnerImproperlyConfigured):
            get_code_runner()


def test_get_code_runner_uses_default_code_runner_type(
    mutable_builder_workflow_action_registry,
    mutable_automation_node_type_registry,
    mutable_service_type_registry,
    mutable_code_runner_type_registry,
):
    unregister_code_runner_features(
        mutable_builder_workflow_action_registry,
        mutable_automation_node_type_registry,
        mutable_service_type_registry,
        mutable_code_runner_type_registry,
    )

    with override_settings(ENTERPRISE_CODE_RUNNER_DEFAULT_TYPE="wasmtime_quickjs"):
        register_code_runner_features()

        assert isinstance(get_code_runner(), WasmtimeQuickJSCodeRunnerType)


def test_code_runner_features_are_not_registered_without_default_type(
    mutable_builder_workflow_action_registry,
    mutable_automation_node_type_registry,
    mutable_service_type_registry,
    mutable_code_runner_type_registry,
):
    unregister_code_runner_features(
        mutable_builder_workflow_action_registry,
        mutable_automation_node_type_registry,
        mutable_service_type_registry,
        mutable_code_runner_type_registry,
    )

    with override_settings(ENTERPRISE_CODE_RUNNER_DEFAULT_TYPE=""):
        register_code_runner_features()

    assert "code" not in mutable_builder_workflow_action_registry.registry
    assert "code" not in mutable_automation_node_type_registry.registry
    assert "code" not in mutable_service_type_registry.registry
    assert "wasmtime_quickjs" not in mutable_code_runner_type_registry.registry


def test_wasmtime_quickjs_code_runner_requires_quickjs_wasm_path():
    with override_settings(ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH=""):
        with pytest.raises(CodeRunnerImproperlyConfigured):
            WasmtimeQuickJSCodeRunnerType().run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_rejects_non_object_result(monkeypatch):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); sys.stdout.write('{\"result\": 1}')",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with override_settings(
        ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH="/runtime/qjs.wasm"
    ):
        with pytest.raises(CodeRunnerResultError):
            WasmtimeQuickJSCodeRunnerType().run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_rejects_oversized_integer_result(monkeypatch):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "sys.stdin.read();"
                    "sys.stdout.write("
                    '\'{"result": {"nested": [{"value": 18446744073709551616}]}}\''
                    ")"
                ),
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(quickjs_wasm_path="/runtime/qjs.wasm")

    with pytest.raises(CodeRunnerResultError, match="outside the supported range"):
        runner.run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_allows_msgpack_range_integer_result(
    monkeypatch,
):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "sys.stdin.read();"
                    "sys.stdout.write("
                    '\'{"result": {"value": 18446744073709551615, "ok": true}}\''
                    ")"
                ),
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(quickjs_wasm_path="/runtime/qjs.wasm")

    assert runner.run({}, "function main() {}") == {
        "value": 18446744073709551615,
        "ok": True,
    }


def test_wasmtime_quickjs_code_runner_maps_process_errors(monkeypatch):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); sys.stderr.write('boom'); sys.exit(1)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with override_settings(
        ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH="/runtime/qjs.wasm"
    ):
        with pytest.raises(CodeRunnerExecutionError, match="boom"):
            WasmtimeQuickJSCodeRunnerType().run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_formats_fuel_exhaustion_error(monkeypatch):
    popen = subprocess.Popen
    wasmtime_path = "/opt/baserow/runtime/bin/wasmtime"
    quickjs_path = "/opt/baserow/runtime/modules/qjs.wasm"

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "sys.stdin.read();"
                    "sys.stderr.write("
                    f"'error while executing {wasmtime_path}: "
                    f"failed to run main module {quickjs_path}: all fuel consumed'"
                    ");"
                    "sys.exit(1)"
                ),
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(
        wasmtime_executable=wasmtime_path,
        quickjs_wasm_path=quickjs_path,
    )

    with pytest.raises(CodeRunnerExecutionError) as exc_info:
        runner.run({}, "function main() {}")

    message = str(exc_info.value)
    assert message == "The code instruction limit was reached."
    assert wasmtime_path not in message
    assert quickjs_path not in message
    assert "all fuel consumed" not in message


def test_wasmtime_quickjs_code_runner_formats_memory_trap_error(monkeypatch):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "sys.stdin.read();"
                    "sys.stderr.write("
                    "'Error: failed to run main module `qjs.wasm`\\n\\n"
                    "Caused by:\\n"
                    "      0: failed to invoke command default\\n"
                    "      1: error while executing at wasm backtrace:\\n"
                    "             0: 0x1acfc - qjs!JS_CallInternal\\n"
                    "           537: 0x11c0 - qjs!_start\\n"
                    "      2: memory fault at wasm address 0x100000094 "
                    "in linear memory of size 0x50000\\n"
                    "      3: wasm trap: out of bounds memory access'"
                    ");"
                    "sys.exit(1)"
                ),
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(quickjs_wasm_path="/runtime/qjs.wasm")

    with pytest.raises(CodeRunnerExecutionError) as exc_info:
        runner.run({}, "function main(context) { return main() }")

    message = str(exc_info.value)
    assert message == "The code exceeded the runtime memory or stack limit."
    assert "wasm backtrace" not in message
    assert "qjs!JS_CallInternal" not in message


def test_wasmtime_quickjs_code_runner_formats_generic_wasm_trap_error(monkeypatch):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "sys.stdin.read();"
                    "sys.stderr.write('error while executing at wasm backtrace: "
                    "wasm trap: unreachable');"
                    "sys.exit(1)"
                ),
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(quickjs_wasm_path="/runtime/qjs.wasm")

    with pytest.raises(CodeRunnerExecutionError) as exc_info:
        runner.run({}, "function main() {}")

    message = str(exc_info.value)
    assert message == "The code stopped because of a runtime execution error."
    assert "wasm trap" not in message


def test_wasmtime_quickjs_code_runner_redacts_startup_error_paths(monkeypatch):
    wasmtime_path = "/opt/baserow/runtime/bin/wasmtime"

    def fake_popen(command, **kwargs):
        raise OSError(f"No such file or directory: '{wasmtime_path}'")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(
        wasmtime_executable=wasmtime_path,
        quickjs_wasm_path="/opt/baserow/runtime/modules/qjs.wasm",
    )

    with pytest.raises(CodeRunnerExecutionError) as exc_info:
        runner.run({}, "function main() {}")

    message = str(exc_info.value)
    assert wasmtime_path not in message
    assert "wasmtime" in message


def test_wasmtime_quickjs_code_runner_limits_stdout(monkeypatch):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); sys.stdout.write('x' * 32)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(
        quickjs_wasm_path="/runtime/qjs.wasm",
        output_size_limit_bytes=16,
    )

    with pytest.raises(CodeRunnerExecutionError, match="too much output"):
        runner.run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_limits_stderr(monkeypatch):
    popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); sys.stderr.write('x' * 32)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = WasmtimeQuickJSCodeRunnerType(
        quickjs_wasm_path="/runtime/qjs.wasm",
        output_size_limit_bytes=16,
    )

    with pytest.raises(CodeRunnerExecutionError, match="too much output"):
        runner.run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_uses_isolated_function_wrapper():
    source = WasmtimeQuickJSCodeRunnerType(
        quickjs_wasm_path="/runtime/qjs.wasm"
    )._runner_source()

    # User code is executed inside Function("context", ...), not via eval on
    # the wrapper's own scope.
    assert '_createFunction("context"' in source
    assert "globalThis.eval(input.code)" not in source

    # Bridge globals injected by qjs --std are deleted before user code runs.
    assert "delete globalThis[_name]" in source
    for bridge_global in ("std", "os", "bjson", "print", "console"):
        assert f'"{bridge_global}"' in source

    # ECMAScript intrinsics are intentionally NOT shadowed — that pretense was
    # bypassable in one line and only created a false sense of security. The
    # real boundary is Wasmtime + WASI (see _runner_source docstring).
    assert "globalThis.eval = undefined" not in source
    assert "globalThis.Function = undefined" not in source


@pytest.mark.skipif(
    not runtime_variables_are_configured,
    reason="Code runner runtime environment variables are not configured.",
)
def test_wasmtime_quickjs_code_runner_executes_real_javascript():
    runner = WasmtimeQuickJSCodeRunnerType(
        wasmtime_executable=os.environ[
            "BASEROW_ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE"
        ],
        quickjs_wasm_path=os.environ[
            "BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH"
        ],
    )

    result = runner.run(
        {"value": 21},
        """
function main(context) {
  return {
    newValue: context.value * 2,
  }
}
""",
    )

    assert result == {"newValue": 42}


@pytest.mark.skipif(
    not runtime_variables_are_configured,
    reason="Code runner runtime environment variables are not configured.",
)
def test_wasmtime_quickjs_code_runner_deletes_host_bridge_globals():
    """
    Verify that qjs --std bridge globals are unreachable from user code, even
    after a constructor-escape back to the real globalThis. The bridge globals
    are the actual security-relevant scrubbing; ECMAScript intrinsics
    (Function, eval, globalThis) are intentionally left reachable since they
    grant no host access on their own.
    """

    runner = WasmtimeQuickJSCodeRunnerType(
        wasmtime_executable=os.environ[
            "BASEROW_ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE"
        ],
        quickjs_wasm_path=os.environ[
            "BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH"
        ],
    )

    result = runner.run(
        {},
        """
function main() {
  // Walk back to the real globalThis via constructor escape to confirm the
  // bridge globals are not reachable even there.
  const realGlobal = (function () {}).constructor("return globalThis")();
  return {
    std: typeof realGlobal.std,
    os: typeof realGlobal.os,
    bjson: typeof realGlobal.bjson,
    print: typeof realGlobal.print,
    console: typeof realGlobal.console,
    scriptArgs: typeof realGlobal.scriptArgs,
    execArgv: typeof realGlobal.execArgv,
    argv0: typeof realGlobal.argv0,
    navigator: typeof realGlobal.navigator,
    atob: typeof realGlobal.atob,
    btoa: typeof realGlobal.btoa,
    // wrapper-local closure refs must not leak into user code's scope
    input: typeof input,
    write: typeof write,
  }
}
""",
    )

    assert result == {
        "std": "undefined",
        "os": "undefined",
        "bjson": "undefined",
        "print": "undefined",
        "console": "undefined",
        "scriptArgs": "undefined",
        "execArgv": "undefined",
        "argv0": "undefined",
        "navigator": "undefined",
        "atob": "undefined",
        "btoa": "undefined",
        "input": "undefined",
        "write": "undefined",
    }


@pytest.mark.skipif(
    not runtime_variables_are_configured,
    reason="Code runner runtime environment variables are not configured.",
)
def test_wasmtime_quickjs_code_runner_does_not_register_std_as_importable_module():
    """
    The bridge-global deletion only contains user code if std/os/bjson are not
    available via dynamic ``import()`` either. This guards against a future
    qjs.wasm rebuild that registers them as importable modules — which would
    silently make the wrapper's scrubbing incomplete.
    """

    runner = WasmtimeQuickJSCodeRunnerType(
        wasmtime_executable=os.environ[
            "BASEROW_ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE"
        ],
        quickjs_wasm_path=os.environ[
            "BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH"
        ],
    )

    result = runner.run(
        {},
        """
function main() {
  const outcomes = {};
  for (const spec of ["std", "os", "bjson"]) {
    let outcome = "pending";
    try {
      import(spec).then(
        () => { outcome = "loaded"; },
        () => { outcome = "rejected"; }
      );
    } catch (e) {
      outcome = "threw";
    }
    outcomes[spec] = outcome;
  }
  return outcomes;
}
""",
    )

    # If a future build registered these as modules, at least one of these
    # would be "loaded" once the microtask queue drains. The "pending" status
    # is acceptable because dynamic-import resolution is async and the
    # surrounding main() returns synchronously — but it must NEVER be
    # "loaded".
    assert "loaded" not in result.values()
