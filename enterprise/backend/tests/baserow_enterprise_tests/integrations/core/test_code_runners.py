import json
import subprocess

from django.test import override_settings

import pytest

from baserow_enterprise.integrations.core.code_runners import (
    CodeRunnerExecutionError,
    CodeRunnerImproperlyConfigured,
    CodeRunnerResultError,
    WasmtimeQuickJSCodeRunner,
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
        temporary_path = kwargs["cwd"]

        assert (temporary_path / "context.json").read_text() == json.dumps(
            {"value": 2}
        )
        assert (temporary_path / "user_code.mjs").read_text() == "export default main"
        assert "import main" in (temporary_path / "runner.mjs").read_text()

        return subprocess.CompletedProcess(
            command, 0, stdout='{"result": {"newValue": 4}}', stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = WasmtimeQuickJSCodeRunner().run(
        {"value": 2},
        "export default main",
    )

    assert result == {"newValue": 4}
    command, kwargs = calls[0]
    assert command[:3] == ["wasmtime-test", "run", "--dir"]
    assert command[4:] == ["/runtime/qjs.wasm", "runner.mjs"]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 7
    assert kwargs["check"] is True


def test_wasmtime_quickjs_code_runner_requires_quickjs_wasm_path():
    with override_settings(BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH=""):
        with pytest.raises(CodeRunnerImproperlyConfigured):
            WasmtimeQuickJSCodeRunner().run({}, "export default function main() {}")


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
            WasmtimeQuickJSCodeRunner().run({}, "export default function main() {}")


def test_wasmtime_quickjs_code_runner_maps_process_errors(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with override_settings(
        BASEROW_ENTERPRISE_CODE_RUNNER_QUICKJS_WASM_PATH="/runtime/qjs.wasm"
    ):
        with pytest.raises(CodeRunnerExecutionError, match="boom"):
            WasmtimeQuickJSCodeRunner().run({}, "export default function main() {}")
