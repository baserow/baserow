import os
import subprocess
import sys

import pytest


def _import_base_settings(retention_hours: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(sys.path),
        "BASEROW_REALTIME_REPLAY_RETENTION_HOURS": retention_hours,
    }
    return subprocess.run(  # noqa: S603 - only the current interpreter runs fixed code.
        [sys.executable, "-c", "import baserow.config.settings.base"],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


@pytest.mark.parametrize("retention_hours", ["0", "-1"])
def test_non_positive_realtime_replay_retention_is_rejected(retention_hours: str):
    """
    A non-positive retention disables compaction instead of failing, so the guard
    in ``settings.base`` is the only thing stopping it.

    The settings module validates at import time, so the check can only be
    exercised from a fresh interpreter; the ``settings`` fixture never re-runs it.
    """

    result = _import_base_settings(retention_hours)

    assert result.returncode != 0
    assert (
        "BASEROW_REALTIME_REPLAY_RETENTION_HOURS must be a positive integer"
        in result.stderr
    )


@pytest.mark.parametrize(
    "configured,expected", [(None, "None"), ("", "None"), ("0", "None"), ("10", "10")]
)
def test_agent_workspace_reply_limit_is_optional(configured: str | None, expected: str):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    name = "BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE"
    if configured is None:
        env.pop(name, None)
    else:
        env[name] = configured

    result = subprocess.run(  # noqa: S603 - only the current interpreter runs fixed code.
        [
            sys.executable,
            "-c",
            "from baserow.config.settings import base; "
            "print(base.BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE)",
        ],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
