"""Workspace task loading.

A training run's `.agentkit/state.json` records `task_path` — the absolute
path to the task project directory. The task project contains `task.py` at
its root, which must define a callable `get_task()` returning a Task
implementation.

This module imports that file and returns the Task instance, with clear
errors if anything is wrong.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from agentkit.task import Task

TASK_FILE = "task.py"
TASK_ENTRY_POINT = "get_task"


class TaskLoadError(Exception):
    """Raised when the task cannot be loaded from task_path."""


def task_file_path(task_path: str | Path) -> Path:
    """Resolve a task project path to its task.py file."""
    return Path(task_path) / TASK_FILE


def load_task(task_path: str | Path) -> Task:
    """Import the task project's task.py and return its Task instance.

    Raises TaskLoadError on any failure with an actionable message.
    """
    project_dir = Path(task_path).resolve()
    if not project_dir.exists():
        raise TaskLoadError(
            f"Task project does not exist at {project_dir}. "
            f"Was it moved or deleted? Update task_path in .agentkit/state.json "
            f"or recreate the training run with `agentkit init-run --task <new-path>`."
        )
    if not project_dir.is_dir():
        raise TaskLoadError(
            f"Task path {project_dir} is not a directory."
        )

    file = task_file_path(project_dir)
    if not file.exists():
        raise TaskLoadError(
            f"No task file at {file}. The task project must contain `{TASK_FILE}` "
            f"at its root, defining `{TASK_ENTRY_POINT}()`. See agentkit's "
            f"docs/AUTHORING_TASKS.md."
        )

    # Add the task project dir to sys.path so task.py can import siblings.
    project_str = str(project_dir)
    if project_str not in sys.path:
        sys.path.insert(0, project_str)

    spec = importlib.util.spec_from_file_location(
        "agentkit_task", str(file)
    )
    if spec is None or spec.loader is None:
        raise TaskLoadError(f"Could not build import spec for {file}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise TaskLoadError(
            f"Failed to import {file}: {type(e).__name__}: {e}"
        ) from e

    if not hasattr(module, TASK_ENTRY_POINT):
        raise TaskLoadError(
            f"{file} does not define `{TASK_ENTRY_POINT}()`. The task module "
            f"must export a callable named `{TASK_ENTRY_POINT}` that returns "
            f"a Task instance."
        )

    entry = getattr(module, TASK_ENTRY_POINT)
    if not callable(entry):
        raise TaskLoadError(
            f"`{TASK_ENTRY_POINT}` in {file} is not callable."
        )

    try:
        task = entry()
    except Exception as e:
        raise TaskLoadError(
            f"`{TASK_ENTRY_POINT}()` raised {type(e).__name__}: {e}"
        ) from e

    # Light protocol check — sanity-check the surface.
    for attr in ("name", "description", "answer_format",
                 "num_training_samples", "num_validation_samples",
                 "get_training_sample", "get_validation_samples",
                 "score_training", "score_validation"):
        if not hasattr(task, attr):
            raise TaskLoadError(
                f"Task returned by `{TASK_ENTRY_POINT}()` is missing "
                f"required attribute or method `{attr}`. See agentkit.task.Task."
            )

    return task
