"""Framework-owned training state.

This is the rigid part of agentkit. The agent designs its own learning
algorithm and tracks whatever *learning* state it wants in its workspace.
But a small set of fields must be tracked by the framework itself, because
they enforce contract guarantees:

  - task_path:              absolute path to the task project (sibling dir)
  - agentkit_version:       version of agentkit that initialized this state,
                            so future framework versions can detect schema drift
  - consumed_training_ids:  prevents replay of training samples
  - pending_training_id:    enforces one-pending-sample-at-a-time
  - skipped_training_ids:   tracks skips for visibility (skips still consume)
  - val_history:            the auditable progress curve

The state file lives at `.agentkit/state.json` inside the training run.
It is NOT committed to git (gitignored at init time) — the git audit trail
for "what changed between val checkpoints" lives in the agent's own commits,
and val_history records HEAD shas, so the curve is verifiable from outside
this file.

The task is referenced by absolute path. The training run and the task
project are separate directories. To run a different task, create a new
training run dir and `agentkit init-run --task <other-task>` from there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = ".agentkit"
STATE_FILE = "state.json"


@dataclass
class ValCheckpoint:
    sha: str
    mean_reward: float
    n: int
    timestamp: str
    consumed_count: int  # how many training samples had been seen at this point


@dataclass
class FrameworkState:
    task_path: str
    agentkit_version: str
    consumed_training_ids: list[str] = field(default_factory=list)
    skipped_training_ids: list[str] = field(default_factory=list)
    pending_training_id: str | None = None
    val_history: list[ValCheckpoint] = field(default_factory=list)

    @classmethod
    def fresh(cls, task_path: str, agentkit_version: str) -> "FrameworkState":
        return cls(task_path=task_path, agentkit_version=agentkit_version)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=False)

    @classmethod
    def from_json(cls, text: str) -> "FrameworkState":
        data = json.loads(text)
        history = [ValCheckpoint(**c) for c in data.pop("val_history", [])]
        state = cls(**data)
        state.val_history = history
        return state

    # ---- mutation helpers (called by CLI commands) ----

    def consume(self, sample_id: str) -> None:
        """Mark a training id as consumed and clear pending."""
        if sample_id not in self.consumed_training_ids:
            self.consumed_training_ids.append(sample_id)
        if self.pending_training_id == sample_id:
            self.pending_training_id = None

    def skip(self, sample_id: str) -> None:
        """Mark a training id as skipped (also consumes it) and clear pending."""
        self.consume(sample_id)
        if sample_id not in self.skipped_training_ids:
            self.skipped_training_ids.append(sample_id)

    def record_val(self, sha: str, mean_reward: float, n: int) -> ValCheckpoint:
        ckpt = ValCheckpoint(
            sha=sha,
            mean_reward=mean_reward,
            n=n,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            consumed_count=len(self.consumed_training_ids),
        )
        self.val_history.append(ckpt)
        return ckpt


# ---------------- file IO ----------------

def state_path(workspace: Path) -> Path:
    return workspace / STATE_DIR / STATE_FILE


def load_state(workspace: Path) -> FrameworkState:
    path = state_path(workspace)
    if not path.exists():
        raise FileNotFoundError(
            f"No agentkit state found at {path}. Run `agentkit init <task>` first."
        )
    return FrameworkState.from_json(path.read_text())


def save_state(workspace: Path, state: FrameworkState) -> None:
    path = state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.to_json())
