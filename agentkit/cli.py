"""agentkit CLI — the surface the agent talks to.

Setup commands:
  install-skill        copy the global agentkit skill to ~/.claude/skills/
  init-task            scaffold a task project in cwd (must be empty)
  init-run --task PATH scaffold a training run in cwd (must be empty)

Training commands (run from inside a training run dir):
  task-info            describe the task and the answer-script contract
  next-train           draw the next training sample
  submit-train         invoke ./answer for the pending sample, score, return feedback
  skip-train           skip the pending training sample (no feedback)
  val-sample --n N     return N validation samples
  submit-val --n N     score N validation samples and append a checkpoint

All commands print JSON to stdout. Errors are JSON on stderr with non-zero exit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, NoReturn

import click

import agentkit
from agentkit.git_gate import GitGateError, assert_can_validate
from agentkit.loader import TaskLoadError, load_task
from agentkit.state import FrameworkState, load_state, save_state
from agentkit.task import Task

ANSWER_SCRIPT = "answer"
ANSWER_TIMEOUT_S = 600  # generous default for v1


def _emit(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, default=str))


def _die(msg: str, code: int = 1) -> NoReturn:
    click.echo(json.dumps({"error": msg}, indent=2), err=True)
    sys.exit(code)


def _cwd() -> Path:
    return Path.cwd()


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _load_task_for_run(workspace: Path) -> Task:
    state = load_state(workspace)
    try:
        return load_task(state.task_path)
    except TaskLoadError as e:
        _die(str(e))


def _is_dir_empty(path: Path) -> bool:
    return not any(path.iterdir())


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_init_and_commit(workspace: Path, message: str) -> None:
    """Initialize a git repo in workspace and make an initial commit.

    Idempotent on git init (won't error if already a repo).
    """
    init_result = _git(workspace, "init", "-q")
    if init_result.returncode != 0:
        _die(f"git init failed: {init_result.stderr.strip()}")
    add_result = _git(workspace, "add", "-A")
    if add_result.returncode != 0:
        _die(f"git add failed: {add_result.stderr.strip()}")
    commit_result = _git(workspace, "commit", "-q", "-m", message)
    if commit_result.returncode != 0:
        _die(
            f"git commit failed: {commit_result.stderr.strip()}\n"
            f"(if this is a fresh git install, you may need to set "
            f"user.email and user.name first)"
        )


def _run_answer_script(workspace: Path, prompt: str) -> tuple[str | None, str | None]:
    script = workspace / ANSWER_SCRIPT
    if not script.exists():
        return None, (
            f"No `{ANSWER_SCRIPT}` script found in workspace. Create an "
            f"executable file named `{ANSWER_SCRIPT}` that reads a prompt on "
            f"stdin and prints an answer to stdout."
        )
    if not script.is_file():
        return None, f"`{ANSWER_SCRIPT}` exists but is not a regular file."
    if not _is_executable(script):
        return None, (
            f"`{ANSWER_SCRIPT}` is not executable. Run `chmod +x {ANSWER_SCRIPT}`."
        )
    try:
        result = subprocess.run(
            [str(script.resolve())],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=workspace,
            timeout=ANSWER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return None, f"`{ANSWER_SCRIPT}` timed out after {ANSWER_TIMEOUT_S}s."
    except OSError as e:
        return None, f"Could not invoke `{ANSWER_SCRIPT}`: {e}"
    if result.returncode != 0:
        return None, (
            f"`{ANSWER_SCRIPT}` exited with code {result.returncode}. "
            f"stderr:\n{result.stderr.strip()}"
        )
    return result.stdout, None


def _is_executable(path: Path) -> bool:
    import os
    return os.access(path, os.X_OK)


# ============================================================
# Commands
# ============================================================

@click.group()
def main() -> None:
    """agentkit — a framework for agents that learn how to learn."""


@main.command("install-skill")
def install_skill() -> None:
    """Install the global agentkit skill to ~/.claude/skills/agentkit/.

    Idempotent. Run once after `uv tool install agentkit` to make the
    `agentkit` skill discoverable in any Claude Code session.
    """
    src = _templates_dir() / "global_skill"
    if not src.is_dir():
        _die(f"Bundled skill template not found at {src}.")

    dst = Path.home() / ".claude" / "skills" / "agentkit"
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if target.exists():
            target.unlink() if target.is_file() else shutil.rmtree(target)
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy(item, target)
    _emit({
        "ok": True,
        "installed_to": str(dst),
        "files": sorted(p.name for p in dst.iterdir()),
        "next": "Open Claude Code anywhere and ask 'help me set up an agentkit task'.",
    })


@main.command("init-task")
def init_task() -> None:
    """Scaffold a fresh agentkit task project in the current directory.

    Refuses on non-empty directories. Writes:
      - task.py (stub)
      - README.md (template)
      - CLAUDE.md (task author identity)
      - .gitignore
    Then runs `git init` + initial commit.

    After init, edit task.py to implement your task per agentkit's
    docs/AUTHORING_TASKS.md, then create a training run elsewhere with
    `agentkit init-run --task <this dir>`.
    """
    workspace = _cwd()
    if not _is_dir_empty(workspace):
        _die(
            f"Refusing to init a non-empty directory: {workspace}. "
            f"Create a fresh empty directory and run `agentkit init-task` from there."
        )

    src = _templates_dir() / "task_project"
    if not src.is_dir():
        _die(f"Task project template not found at {src}.")

    # Copy templates, renaming `gitignore` -> `.gitignore`
    for item in src.iterdir():
        if item.name == "gitignore":
            shutil.copy(item, workspace / ".gitignore")
        elif item.is_dir():
            shutil.copytree(item, workspace / item.name)
        else:
            shutil.copy(item, workspace / item.name)

    _git_init_and_commit(workspace, "agentkit init-task: scaffold task project")

    _emit({
        "ok": True,
        "task_project": str(workspace),
        "scaffolded": [
            "task.py (stub — replace with your task implementation)",
            "README.md (template)",
            "CLAUDE.md (task author identity)",
            ".gitignore",
        ],
        "next_steps": [
            "Replace task.py with your real task code (see agentkit's docs/AUTHORING_TASKS.md).",
            "Update README.md with your task description.",
            "Commit your changes.",
            f"Create a training run elsewhere: `mkdir <run-dir> && cd <run-dir> && "
            f"agentkit init-run --task {workspace}`",
        ],
    })


@main.command("init-run")
@click.option(
    "--task",
    "task_arg",
    type=str,
    required=True,
    help="Path to the task project directory (containing task.py).",
)
def init_run(task_arg: str) -> None:
    """Scaffold a fresh agentkit training run in the current directory.

    Refuses on non-empty directories. Validates that the task project at
    --task contains a working task.py with a get_task() entry point. Writes:
      - BOOTSTRAP.md
      - CLAUDE.md (learning agent identity)
      - .claude/skills/... (none in v1; skill is global)
      - .gitignore
      - .agentkit/state.json (records absolute task path + agentkit version)
    Then runs `git init` + initial commit.
    """
    workspace = _cwd()
    if not _is_dir_empty(workspace):
        _die(
            f"Refusing to init a non-empty directory: {workspace}. "
            f"Create a fresh empty directory and run `agentkit init-run --task ... ` from there."
        )

    # Validate the task project
    task_path = Path(task_arg).expanduser().resolve()
    if not task_path.exists():
        _die(f"Task project does not exist: {task_path}")
    if not task_path.is_dir():
        _die(f"Task path is not a directory: {task_path}")
    try:
        task = load_task(task_path)
    except TaskLoadError as e:
        _die(f"Task validation failed: {e}")

    # Copy training run templates
    src = _templates_dir() / "training_run"
    if not src.is_dir():
        _die(f"Training run template not found at {src}.")
    for item in src.iterdir():
        if item.name == "gitignore":
            shutil.copy(item, workspace / ".gitignore")
        elif item.is_dir():
            shutil.copytree(item, workspace / item.name)
        else:
            shutil.copy(item, workspace / item.name)

    # Write framework state
    state = FrameworkState.fresh(
        task_path=str(task_path),
        agentkit_version=agentkit.__version__,
    )
    save_state(workspace, state)

    _git_init_and_commit(workspace, "agentkit init-run: scaffold training run")

    _emit({
        "ok": True,
        "training_run": str(workspace),
        "task_path": str(task_path),
        "task_name": task.name,
        "training_pool_size": task.num_training_samples(),
        "validation_pool_size": task.num_validation_samples(),
        "scaffolded": [
            "BOOTSTRAP.md",
            "CLAUDE.md (learning agent identity)",
            ".gitignore",
            ".agentkit/state.json",
        ],
        "next_steps": [
            "Open Claude Code in this directory.",
            "The learning agent CLAUDE.md auto-loads — read BOOTSTRAP.md and start the loop when ready.",
        ],
    })


@main.command("task-info")
def task_info() -> None:
    """Print the task description and the answer-script contract."""
    workspace = _cwd()
    state = load_state(workspace)
    task = _load_task_for_run(workspace)
    _emit({
        "name": task.name,
        "description": task.description,
        "answer_format": task.answer_format,
        "answer_script_contract": (
            f"Your workspace must contain an executable file named "
            f"`{ANSWER_SCRIPT}`. It will be invoked with a task prompt on "
            f"stdin and must print an answer to stdout. The answer must "
            f"satisfy: {task.answer_format}"
        ),
        "task_path": state.task_path,
        "agentkit_version": state.agentkit_version,
        "training_pool_size": task.num_training_samples(),
        "validation_pool_size": task.num_validation_samples(),
        "consumed_training": len(state.consumed_training_ids),
        "skipped_training": len(state.skipped_training_ids),
        "pending_training_id": state.pending_training_id,
        "val_checkpoints_recorded": len(state.val_history),
    })


@main.command("next-train")
def next_train() -> None:
    """Draw the next training sample. Errors if one is already pending."""
    workspace = _cwd()
    state = load_state(workspace)
    if state.pending_training_id is not None:
        _die(
            f"A training sample is already pending: {state.pending_training_id}. "
            f"Submit or skip it before drawing another."
        )
    task = _load_task_for_run(workspace)
    idx = len(state.consumed_training_ids)
    if idx >= task.num_training_samples():
        _die("Training pool exhausted.")
    sample = task.get_training_sample(idx)
    state.pending_training_id = sample.id
    save_state(workspace, state)
    _emit({"id": sample.id, "prompt": sample.prompt})


@main.command("submit-train")
def submit_train() -> None:
    """Run ./answer on the pending training sample, score, return feedback."""
    workspace = _cwd()
    state = load_state(workspace)
    if state.pending_training_id is None:
        _die("No pending training sample. Call `next-train` first.")
    task = _load_task_for_run(workspace)
    idx = len(state.consumed_training_ids)
    sample = task.get_training_sample(idx)
    if sample.id != state.pending_training_id:
        _die(
            f"State inconsistency: pending id {state.pending_training_id} does not "
            f"match the next sample at index {idx} ({sample.id})."
        )
    answer_text, err = _run_answer_script(workspace, sample.prompt)
    if err is not None or answer_text is None:
        _die(err or "answer script produced no output")
    result = task.score_training(sample.id, answer_text)
    state.consume(sample.id)
    save_state(workspace, state)
    _emit({
        "id": sample.id,
        "answer": answer_text,
        "reward": result.reward,
        "breakdown": result.breakdown,
        "gold_answer": result.gold_answer,
        "notes": result.notes,
    })


@main.command("skip-train")
def skip_train() -> None:
    """Skip the pending training sample. Consumes it; no feedback returned."""
    workspace = _cwd()
    state = load_state(workspace)
    if state.pending_training_id is None:
        _die("No pending training sample to skip. Call `next-train` first.")
    sid = state.pending_training_id
    state.skip(sid)
    save_state(workspace, state)
    _emit({"id": sid, "skipped": True})


@main.command("val-sample")
@click.option("--n", type=int, default=10, help="Number of validation samples to return.")
def val_sample(n: int) -> None:
    """Return N validation samples (deterministic). Does not change state."""
    workspace = _cwd()
    task = _load_task_for_run(workspace)
    samples = task.get_validation_samples(n)
    _emit([{"id": s.id, "prompt": s.prompt} for s in samples])


@main.command("submit-val")
@click.option(
    "--n",
    type=int,
    default=10,
    help="Number of validation samples to score (must match val-sample).",
)
def submit_val(n: int) -> None:
    """Invoke ./answer on N val samples, score them, append a checkpoint.

    Refuses if the workspace has uncommitted changes or if the current HEAD
    sha matches the previous validation checkpoint.
    """
    workspace = _cwd()
    state = load_state(workspace)
    last_sha = state.val_history[-1].sha if state.val_history else None
    try:
        sha = assert_can_validate(workspace, last_sha)
    except GitGateError as e:
        _die(str(e))

    task = _load_task_for_run(workspace)
    samples = task.get_validation_samples(n)
    answers: dict[str, str] = {}
    for s in samples:
        answer_text, err = _run_answer_script(workspace, s.prompt)
        if err is not None or answer_text is None:
            _die(f"Failed on validation sample {s.id}: {err or 'no output'}")
        answers[s.id] = answer_text

    agg = task.score_validation(answers)
    ckpt = state.record_val(sha=sha, mean_reward=agg.mean_reward, n=agg.n)
    save_state(workspace, state)
    _emit({
        "checkpoint": asdict(ckpt),
        "checkpoint_idx": len(state.val_history) - 1,
    })


if __name__ == "__main__":
    main()
