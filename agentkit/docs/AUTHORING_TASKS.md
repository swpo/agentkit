# Authoring an agentkit task

A **task** in agentkit is the rules of the game for a training run: it owns the data, the prompts, and the scoring. Learning agents work *against* a task and never modify it.

This doc tells you exactly what you need to write to make a valid task. It is intentionally short. If you (or your coding assistant) follow it carefully, the framework will pick your task up automatically.

## File layout

A task lives in a workspace's `task/` subdirectory:

```
my-workspace/
  task/
    task.py        # entry point — required
    README.md      # describes the task — required
    ...            # optional helpers, data, prompts
```

`task.py` must define a callable named `get_task()` that takes no arguments and returns an object satisfying the Task protocol below. The framework imports this file and calls `get_task()` whenever it needs to load the task.

The `task/` directory is added to `sys.path` when the task module is loaded, so you can split your task across multiple files (`task/data.py`, `task/scoring.py`, etc.) and import them normally from `task.py`.

## The Task protocol

```python
from agentkit.task import Sample, TrainScoreResult, ValAggregateResult


class MyTask:
    name: str                              # short identifier
    description: str                       # what the task is, in one sentence
    answer_format: str                     # exact spec of what `answer` must output

    def num_training_samples(self) -> int: ...
    def num_validation_samples(self) -> int: ...

    def get_training_sample(self, index: int) -> Sample:
        """Return the training sample at the given index in a stable ordering.

        The framework computes `index` from its own state (the count of
        consumed training samples). Your task must produce the SAME sample
        for the SAME index across runs — i.e. the underlying ordering must
        be deterministic. Shuffle once at task construction time with a
        fixed seed and serve from a list, don't re-shuffle on every call.
        """

    def get_validation_samples(self, n: int) -> list[Sample]:
        """Return a deterministic subset of n validation samples.

        Same n must always produce the same samples (so val history across
        checkpoints is comparable). The val pool must be DISJOINT from the
        training pool — agents must never see val samples during training.
        """

    def score_training(self, sample_id: str, answer: str) -> TrainScoreResult:
        """Score a single training answer against the gold.

        Returns reward (in [0,1]), an optional breakdown dict, the gold
        answer (which IS shown to the agent for training samples), and
        free-form notes (typically a human-readable diff between prediction
        and gold).
        """

    def score_validation(self, answers: dict[str, str]) -> ValAggregateResult:
        """Score a batch of validation answers.

        Returns ONLY the aggregate (mean_reward, n). No per-example info,
        no gold answers — these never leak to the agent.
        """


def get_task() -> MyTask:
    return MyTask()
```

`Sample`, `TrainScoreResult`, and `ValAggregateResult` are simple dataclasses defined in `agentkit.task`:

```python
@dataclass(frozen=True)
class Sample:
    id: str        # stable across runs
    prompt: str    # what the agent sees

@dataclass
class TrainScoreResult:
    reward: float                     # primary signal
    breakdown: dict[str, float]       # optional sub-scores for visibility
    gold_answer: str                  # shown to the agent during training
    notes: str                        # optional human-readable diff

@dataclass
class ValAggregateResult:
    mean_reward: float
    n: int
```

## Hard requirements

Your task must:

1. **Use stable sample ids.** A sample with id `X` today must be the same sample with id `X` next week. The framework tracks `consumed_training_ids` across runs and would break if ids drifted. The simplest way is to derive ids from sample content (e.g. `hashlib.sha1(prompt.encode()).hexdigest()[:12]`).
2. **Have disjoint training and validation pools.** Use separate dataset splits, or partition deterministically. Agents must never see val items during training.
3. **Return aggregate-only val scores.** Never include per-example data in `score_validation`'s return value. The framework relies on this for val isolation.
4. **Be deterministic.** `get_training_sample(7)` and `get_validation_samples(10)` must return the same things every call. Shuffle once at construction time with a fixed seed.
5. **Cache expensive setup.** The framework imports your task on every CLI invocation. Use `functools.cached_property` (or similar) for dataset loading so per-call cost is just the cache hit.

## Soft recommendations

- **Reward in [0,1]** — easier to compare across tasks and easier for agents to interpret. F1, accuracy, recall@k, normalized similarity, etc. all fit naturally.
- **Notes should be actionable** — when `score_training` returns `notes`, write something the agent can learn from. "Predicted X, expected Y, you missed Z and added W" is more useful than "wrong".
- **Format failures should return 0 with a clear note** — don't crash. The agent can recover from a 0 with a clear error in `notes`.

## Worked example

See the `gene_perturbation_forward` task in `agentkit-runs/gpf-pilot/task/task.py` for a complete real-world example: HuggingFace dataset loading, prompt cleanup, JSON answer format, F1 scoring with diff notes, deterministic train/val pools.
