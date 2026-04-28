"""Git-based validation gating.

The agent's workspace is required to be a git repo. Validation can only run
when:
  1. There are no uncommitted changes (clean tree).
  2. The current HEAD sha differs from the sha recorded at the previous
     validation checkpoint.

Rationale: validation cost should only be paid when the workspace has
*actually changed*, otherwise we'd just be measuring sampling noise. This
also forces the agent to commit its learning to git, which is exactly the
artifact we want — a diffable history of what changed between checkpoints.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitGateError(Exception):
    """Raised when the workspace fails a git-state precondition for validation."""


def _run(cmd: list[str], workspace: Path) -> str:
    result = subprocess.run(
        cmd,
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitGateError(
            f"git command failed: {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def is_git_repo(workspace: Path) -> bool:
    try:
        out = _run(["git", "rev-parse", "--is-inside-work-tree"], workspace)
    except GitGateError:
        return False
    return out == "true"


def head_sha(workspace: Path) -> str:
    return _run(["git", "rev-parse", "HEAD"], workspace)


def is_clean(workspace: Path) -> bool:
    """True if there are no uncommitted changes (tracked or untracked)."""
    out = _run(["git", "status", "--porcelain"], workspace)
    return out == ""


def assert_can_validate(workspace: Path, last_val_sha: str | None) -> str:
    """Verify the workspace state allows running validation.

    Returns the current HEAD sha if all checks pass.
    Raises GitGateError otherwise with a clear, actionable message.
    """
    if not is_git_repo(workspace):
        raise GitGateError(
            f"Workspace {workspace} is not a git repo. "
            f"Initialize one with `git init` and commit your starting state."
        )

    try:
        sha = head_sha(workspace)
    except GitGateError as e:
        raise GitGateError(
            f"Could not read HEAD sha: {e}. Have you made any commits yet?"
        ) from e

    if not is_clean(workspace):
        raise GitGateError(
            "Workspace has uncommitted changes. Validation requires a clean "
            "tree so the val checkpoint corresponds to a committed snapshot. "
            "Commit (or stash) your changes and try again."
        )

    if last_val_sha is not None and sha == last_val_sha:
        raise GitGateError(
            f"Workspace HEAD ({sha[:8]}) matches the last validation checkpoint. "
            f"Validation only runs when the workspace has changed since the last "
            f"checkpoint — otherwise we'd just be measuring sampling noise. "
            f"Make a commit and try again."
        )

    return sha
