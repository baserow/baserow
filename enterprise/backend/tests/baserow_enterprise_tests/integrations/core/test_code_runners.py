import os
import subprocess
import sys
from pathlib import Path
from shutil import which

from django.test import override_settings

import pytest

from baserow.core.code_runner.registries import (
    get_code_runner,
)
from baserow_enterprise.apps import register_code_runner_features
from baserow_enterprise.code_runner.code_runner_types import (
    CodeRunnerExecutionError,
    CodeRunnerImproperlyConfigured,
    CodeRunnerResultError,
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

    assert 'createFunction("context"' in source
    assert "globalThis.eval = undefined;" in source
    assert "globalThis.Function = undefined;" in source
    assert "const std = undefined;" in source
    assert "const os = undefined;" in source
    assert "const Function = undefined;" in source
    assert "const globalThis = undefined;" in source


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
def test_wasmtime_quickjs_code_runner_hides_wrapper_and_std_globals():
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
  return {
    std: typeof std,
    os: typeof os,
    bjson: typeof bjson,
    eval: typeof eval,
    Function: typeof Function,
    print: typeof print,
    globalThis: typeof globalThis,
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
        "eval": "undefined",
        "Function": "undefined",
        "print": "undefined",
        "globalThis": "undefined",
        "input": "undefined",
        "write": "undefined",
    }
