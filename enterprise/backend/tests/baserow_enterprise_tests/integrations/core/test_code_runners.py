import os
import subprocess

from django.test import override_settings

import pytest

from baserow.core.code_runner.registries import code_runner_type_registry
from baserow_enterprise.code_runner.code_runner_types import (
    CodeRunnerExecutionError,
    CodeRunnerImproperlyConfigured,
    CodeRunnerResultError,
    WasmtimeQuickJSCodeRunnerType,
)

runtime_variables_are_configured = all(
    [
        os.environ.get("BASEROW_ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE"),
        os.environ.get("BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH"),
    ]
)


@override_settings(
    BASEROW_ENTERPRISE_CODE_RUNNER_WASMTIME_EXECUTABLE="wasmtime-test",
    BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH="/runtime/qjs.wasm",
    BASEROW_ENTERPRISE_CODE_RUNNER_TIMEOUT_SECONDS=7,
)
def test_wasmtime_quickjs_code_runner_runs_code_in_subprocess(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        assert '"context": {"value": 2}' in kwargs["input"]
        assert "function main(context)" in kwargs["input"]

        return subprocess.CompletedProcess(
            command, 0, stdout='{"result": {"newValue": 4}}', stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = WasmtimeQuickJSCodeRunnerType().run(
        {"value": 2},
        "function main(context) { return { newValue: context.value * 2 } }",
    )

    assert result == {"newValue": 4}
    command, kwargs = calls[0]
    assert command[:4] == ["wasmtime-test", "run", "/runtime/qjs.wasm", "--std"]
    assert command[4] == "--eval"
    assert "std.in.getline()" in command[5]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 7
    assert kwargs["check"] is True


def test_wasmtime_quickjs_code_runner_type_is_registered():
    assert isinstance(
        code_runner_type_registry.get("wasmtime_quickjs"),
        WasmtimeQuickJSCodeRunnerType,
    )


def test_wasmtime_quickjs_code_runner_requires_quickjs_wasm_path():
    with override_settings(BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH=""):
        with pytest.raises(CodeRunnerImproperlyConfigured):
            WasmtimeQuickJSCodeRunnerType().run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_rejects_non_object_result(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout='{"result": 1}', stderr=""
        ),
    )

    with override_settings(
        BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH="/runtime/qjs.wasm"
    ):
        with pytest.raises(CodeRunnerResultError):
            WasmtimeQuickJSCodeRunnerType().run({}, "function main() {}")


def test_wasmtime_quickjs_code_runner_maps_process_errors(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with override_settings(
        BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH="/runtime/qjs.wasm"
    ):
        with pytest.raises(CodeRunnerExecutionError, match="boom"):
            WasmtimeQuickJSCodeRunnerType().run({}, "function main() {}")


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
