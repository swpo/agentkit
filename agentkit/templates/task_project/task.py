"""Task stub.

This file is the *rules of the game* for an agentkit training run. It must
define a callable named `get_task()` that returns an object satisfying the
agentkit.task.Task protocol.

A complete task implements:

  - name: str
  - description: str
  - answer_format: str
  - num_training_samples() -> int
  - num_validation_samples() -> int
  - get_training_sample(index: int) -> Sample
  - get_validation_samples(n: int) -> list[Sample]
  - score_training(sample_id: str, answer: str) -> TrainScoreResult
  - score_validation(answers: dict[str, str]) -> ValAggregateResult

See agentkit's AUTHORING_TASKS.md (in the agentkit package's docs/ dir) for
the full protocol with type signatures and worked examples.

Replace this stub with your real task implementation, commit it, then run
the agentkit training loop.
"""

from agentkit.task import Sample, Task, TrainScoreResult, ValAggregateResult


class StubTask:
    name = "stub"
    description = "Replace this with your real task."
    answer_format = "Replace this with your real answer format spec."

    def num_training_samples(self) -> int:
        raise NotImplementedError("Replace task.py with a real task.")

    def num_validation_samples(self) -> int:
        raise NotImplementedError("Replace task.py with a real task.")

    def get_training_sample(self, index: int) -> Sample:
        raise NotImplementedError("Replace task.py with a real task.")

    def get_validation_samples(self, n: int) -> list[Sample]:
        raise NotImplementedError("Replace task.py with a real task.")

    def score_training(self, sample_id: str, answer: str) -> TrainScoreResult:
        raise NotImplementedError("Replace task.py with a real task.")

    def score_validation(self, answers: dict[str, str]) -> ValAggregateResult:
        raise NotImplementedError("Replace task.py with a real task.")


def get_task() -> Task:
    return StubTask()
