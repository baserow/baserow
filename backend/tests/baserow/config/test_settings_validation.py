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


@pytest.mark.parametrize(
    "configured_length,expected_length",
    [("", "12"), ("3", "7"), ("20", "20"), ("50", "50"), ("60", "50")],
)
def test_workspace_invitation_link_length_defaults_to_12_between_7_and_50(
    configured_length: str, expected_length: str
):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(sys.path),
        "BASEROW_WORKSPACE_INVITATION_LINK_LENGTH": configured_length,
    }
    result = subprocess.run(  # noqa: S603 - only the current interpreter runs fixed code.
        [
            sys.executable,
            "-c",
            "from baserow.config.settings import base; "
            "print(base.BASEROW_WORKSPACE_INVITATION_LINK_LENGTH)",
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.stdout.strip().splitlines()[-1] == expected_length


AGENT_TRIGGER_LIMIT_VARIABLES = (
    "BASEROW_AGENT_TRIGGER_RATE_LIMITS",
    "BASEROW_AGENT_TRIGGER_AGENT_RATE_LIMITS",
    "BASEROW_AGENT_TRIGGER_MAX_QUEUED_RUNS",
)
DEFAULT_AGENT_TRIGGER_LIMITS = (
    "((10, 5), (30, 300), (100, 3600)) ((20, 60), (300, 3600)) 10"
)


def _read_agent_trigger_limits(**configured: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    for name in AGENT_TRIGGER_LIMIT_VARIABLES:
        env.pop(name, None)
    env.update(configured)
    return subprocess.run(  # noqa: S603 - only the current interpreter runs fixed code.
        [
            sys.executable,
            "-c",
            "from baserow.config.settings import base; "
            "print(base.AGENT_TRIGGER_RATE_LIMITS, "
            "base.AGENT_TRIGGER_AGENT_RATE_LIMITS, "
            "base.AGENT_TRIGGER_MAX_QUEUED_RUNS)",
        ],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


@pytest.mark.parametrize(
    "configured,expected",
    [
        ({}, DEFAULT_AGENT_TRIGGER_LIMITS),
        ({"BASEROW_AGENT_TRIGGER_RATE_LIMITS": ""}, DEFAULT_AGENT_TRIGGER_LIMITS),
        (
            {
                "BASEROW_AGENT_TRIGGER_RATE_LIMITS": "1, 3600",
                "BASEROW_AGENT_TRIGGER_AGENT_RATE_LIMITS": ",",
                "BASEROW_AGENT_TRIGGER_MAX_QUEUED_RUNS": "1",
            },
            "((1, 3600),) () 1",
        ),
    ],
    ids=["unset", "empty_keeps_default", "custom_and_disabled"],
)
def test_agent_trigger_limits_are_read_as_pairs(
    configured: dict[str, str], expected: str
):
    result = _read_agent_trigger_limits(**configured)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == expected


@pytest.mark.parametrize("value", ["10,5,30", "10,five"])
def test_agent_trigger_rate_limits_must_be_integer_pairs(value: str):
    result = _read_agent_trigger_limits(BASEROW_AGENT_TRIGGER_RATE_LIMITS=value)

    assert result.returncode != 0
    assert "BASEROW_AGENT_TRIGGER_RATE_LIMITS must contain" in result.stderr
