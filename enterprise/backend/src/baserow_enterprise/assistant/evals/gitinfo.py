from __future__ import annotations

import os
import subprocess  # nosec
from pathlib import Path

# enterprise/backend/src/baserow_enterprise/assistant/evals/gitinfo.py -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[6]


def _git(*args: str) -> str:
    """Run a git command in the repo root; "" on any failure (no git, no
    .git dir, timeout, non-zero exit) — this must never raise."""

    try:
        result = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_git_info() -> dict[str, str]:
    """Best-effort branch/commit for stamping eval experiment metadata.

    Tries a local git checkout first; falls back to BASEROW_EVAL_GIT_BRANCH /
    BASEROW_EVAL_GIT_COMMIT env vars, since the eval-runner container has no
    .git directory mounted — those env vars are how the host's branch/commit
    reach it (see the ``dc-dev`` justfile recipe).
    """

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or os.environ.get(
        "BASEROW_EVAL_GIT_BRANCH", ""
    )
    commit = _git("rev-parse", "--short", "HEAD") or os.environ.get(
        "BASEROW_EVAL_GIT_COMMIT", ""
    )

    info: dict[str, str] = {}
    if branch:
        info["git_branch"] = branch
    if commit:
        info["git_commit"] = commit
    return info
