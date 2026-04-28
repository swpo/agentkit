"""Task protocol and shared types.

A Task is the unit a learning agent works against. It owns:
  - the training pool (samples the agent can consume one at a time)
  - the validation pool (a fixed held-out set the agent never sees gold for)
  - the scoring function (what counts as a good answer)

The framework owns sampling/state/git-gating; tasks just need to expose
the four methods on the Task protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Sample:
    """A single task sample as the agent sees it.

    `id` is stable across runs (so the framework can track which samples
    have been consumed). `prompt` is whatever question text the agent is
    being asked to answer. The gold answer is NEVER on Sample — it is only
    revealed via score_training, and never for validation samples.
    """

    id: str
    prompt: str


@dataclass
class TrainScoreResult:
    """Result of scoring a single training answer.

    The agent sees the full breakdown including the gold answer — this is
    its only feedback signal during training, so it should be informative.
    """

    reward: float
    breakdown: dict[str, float] = field(default_factory=dict)
    gold_answer: str = ""
    notes: str = ""


@dataclass
class ValAggregateResult:
    """Aggregate result of a validation pass.

    Per-design: NO per-example scores, NO gold answers — only the aggregate.
    The agent must not be able to learn to game validation, so we leak the
    minimum information needed to track a progress curve.
    """

    mean_reward: float
    n: int


class Task(Protocol):
    """The Task protocol implementations must satisfy."""

    name: str
    description: str
    answer_format: str

    def num_training_samples(self) -> int:
        """Total number of available training samples."""
        ...

    def num_validation_samples(self) -> int:
        """Total number of available validation samples."""
        ...

    def get_training_sample(self, index: int) -> Sample:
        """Return the training sample at position `index` in the (fixed) ordering.

        The framework computes `index` from its own state — tasks should
        treat this as deterministic indexing into a stable shuffle.
        """
        ...

    def get_validation_samples(self, n: int) -> list[Sample]:
        """Return a deterministic subset of `n` validation samples.

        Same n always returns the same samples (so val history across
        checkpoints is comparable).
        """
        ...

    def score_training(self, sample_id: str, answer: str) -> TrainScoreResult:
        """Score an answer against the gold for a training sample.

        Returns gold_answer in the result so the agent can reflect on the gap.
        """
        ...

    def score_validation(self, answers: dict[str, str]) -> ValAggregateResult:
        """Score a batch of validation answers and return ONLY aggregate stats.

        `answers` is a dict {sample_id: answer_string}.
        """
        ...
